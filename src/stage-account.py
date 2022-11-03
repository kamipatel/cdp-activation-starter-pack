import os
import boto3
import pandas as pd
import json
from io import StringIO
from datetime import datetime
from botocore.exceptions import ClientError
import numpy as np

session = boto3.Session()
s3 = session.resource('s3')

def read_s3_contents_with_download(bucket, k):
    response = s3.Object(bucket, k).get()
    return response['Body']

def write_csv_to_s3(df, bucket, k):
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.Bucket(bucket).put_object(Key= k, Body=csv_buffer.getvalue())     

def stage(event):
    print("Satge account called")
    print(event)
    #print(event.data)

    in_bucket_name = os.environ['IN_BUCKET']
    data_bucket_name = in_bucket_name

    existing_bucket_name = os.environ['EXISTING_BUCKET'] 
    stage_bucket_name = os.environ['STAGE_BUCKET']
    print("In bucket=" + in_bucket_name)
    print("Existing Bucket=" + existing_bucket_name) # If you passed during cloudformatin stack creation
    print("stage_bucket=" + stage_bucket_name)    
    
    if(existing_bucket_name and existing_bucket_name != ""):
        print("*** Data bucket existing selected =" + existing_bucket_name)
        data_bucket_name = existing_bucket_name

    if 'fake' in event and event['fake'] == True:    
        print("*** Using fake Data bucket")
        data_bucket_name = os.environ['FAKE_BUCKET']

    print("*** Data bucket=" + data_bucket_name)

    data_bucket = s3.Bucket(data_bucket_name)

    account = event['account']
    latest_date = event['dt']

    print(event['data']["unique_accounts"])
    print('Processing account->' + str(account))
    print('Processing latest_date->' + str(latest_date))

    datepath = latest_date + '/'
    date_account_path = datepath + account + "/"         
    
    account_df = pd.DataFrame() #account data
    seg_df = pd.DataFrame() # Segment data
    unique_segments = []

    metadata_processed = False

    print("***Process account path->" + date_account_path)
    for bin_object in data_bucket.objects.filter(Prefix= date_account_path):
        df = pd.DataFrame()
        
        k = bin_object.key.split('/')

        # Get segments
        if len(k) > 3 and k[3] == "metadata.json" and metadata_processed == False:
            meta_json = read_s3_contents_with_download(data_bucket_name, bin_object.key).read().decode('utf-8')
            mj = json.loads(meta_json)
            #bu = mj["metadata"]['Business Unit']
            for seg in mj["segments"]:
                each_seg = {}
                each_seg["segmentId"] = seg["segmentId"]
                each_seg["segmentName"] = seg["segmentName"]            
                #each_seg["BU"] = bu                    
                each_seg_df = pd.DataFrame([each_seg])
                seg_df = pd.concat([seg_df, each_seg_df], axis=0, ignore_index=True)      
            
            segments_unique = seg_df["segmentId"].unique()
            metadata_processed = True
    print("Account segment complete")
    print("date_account_path=" + date_account_path)

    for bin_object in data_bucket.objects.filter(Prefix= date_account_path):
        df = pd.DataFrame()
        
        k = bin_object.key.split('/')        

        # get activation records for all files of an account       
        if len(k) == 5 and k[4] != '':
            typeVal = ""
            if len(k) > 3 and "type=" in k[3]:
                t = k[3].split('=')
                typeVal = t[1]

            #print("Process file=" + bin_object.key)
            f = read_s3_contents_with_download(data_bucket_name, bin_object.key)
            #print("*** Read the file")
            df = pd.read_csv(
                    f,
                    compression='gzip'
                )
            df["dt"] = latest_date
            df["account"] = k[1]
            df["Activation-Run-ID"] = k[2]
            df["ID-Type"] = typeVal
            df.rename(columns={"id": "IFA-Value"}, inplace=True)

            # Add it to account dataframe
            account_df = pd.concat([account_df, df], axis=0, ignore_index=True)        

    print("For account=" + account + ", got total records=" + str(len(account_df)))
    
    # Let's process comma delmited segments as per the doc https://help.salesforce.com/s/articleView?id=sf.c360_a_package_external_activation_platform_find_metadata_reference.htm&type=5
    # and create a seperate row for eaach segment
    print("Before segment seperation, for account=" + account + ", got total records=" + str(len(account_df)))      
    account_df['adds'] = account_df['adds'].str.replace('"','') # Replace quotes with space
    account_df['adds'] = account_df['adds'].str.split(',') # Split comma delmited 
    account_df = account_df.explode('adds') # Create seperate rows   

    print("After segment seperation, for account=" + account + ", got total records=" + str(len(account_df)))
    print(seg_df.head())
    
    # merge activations and segments
    #account_df = pd.merge(account_df, seg_df, left_on='adds', right_on='segmentId')
    account_df = pd.merge(account_df, seg_df, left_on='adds', right_on='segmentId', indicator = True, how='left')
    
    account_df["Id"] = account_df["IFA-Value"] + account_df["segmentId"]
    account_df = account_df.replace(np.nan, '', regex=True)

    unique_segments = account_df["segmentId"].unique()

    # -- Start Write a stage csv file per account per segment. 
    # Store in latest this is needed only if you wish to process activation as 2 step process i.e. stage, activation        
    # Write a stage csv file per account per segment.         
    for seg in unique_segments:
        if(seg == ""):
            print("Empty segment")
            continue
        act_seg_df = account_df.loc[account_df['segmentId'] == seg] 
        k = "stage/latest/peraccountsegment/" + account + "/" + seg + "/" + latest_date + ".csv"
        print(k)
        write_csv_to_s3(act_seg_df, stage_bucket_name, k)        

    # -- End Store in latest this is needed only if you wish to process activation as 2 step process i.e. stage, activation

    ####### If you need 1 step process call your partner API here ####### 
    # One account at a time
    print("Start prcessing account=" + account + ", total records=" + str(len(account_df)))
    is_success = False

    # *** Start Call API with the data from account_df ***

    # Partner TODO here

    is_success = True # API call outcome was success or failure? Setting True just as a placeholder
    # *** End Call API with the data from account_df ***

    # Log the processing status
    if is_success:
        activationstatus = "SUCCESS"
        account_df.insert(1, "activationstatus", activationstatus)
    else:
        activationstatus = "FAIL"
        account_df.insert(1, "activationstatus", activationstatus)

    # -- Start writing activation processing result to csv file per account
    # Write a activation results csv file per account per segment.         
    for seg in unique_segments:
        if(seg == ""):
            print("Empty segment")
            continue
        act_seg_df = account_df.loc[account_df['segmentId'] == seg] 
        k = "activation/"+ latest_date + "/peraccountsegment/" + account + "/" + seg  + "-" + activationstatus + ".csv"
        write_csv_to_s3(act_seg_df, stage_bucket_name, k)        

    # If you want to write a activation results csv file per account.         
    '''
    k = "activation/"+ today + "/peraccount/" + account + "/" + today + "-" + status + ".csv"
    print(k)
    write_csv_to_s3(account_df, stage_bucket_name, k)      
    '''

    # -- End write activation processing results                 
    print("Completed processing of account->" +  account)
    
    print(datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }

def lambda_handler(event, context):
    print("Stage account called")
    print(event)
    #print(event.data)

    stage(event)

    print("Stage complete")

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }


# Test only
event = {}
event['dt'] = '2022-08-11'
event['account'] = 'isvscdptest1aid'
event['data'] = {}
event['data']['unique_accounts'] = ['isvscdptest1aid']
stage(event)
