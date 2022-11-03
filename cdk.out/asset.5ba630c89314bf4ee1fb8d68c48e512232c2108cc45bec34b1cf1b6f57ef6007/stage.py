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

def stage():
    #setup resources
    
    print("***stack in bucket")
    bucket = os.environ['IN_BUCKET']
    print("***existing in bucket")
    print(os.environ['EXISTING_BUCKET'])

    existingBucket = os.environ['EXISTING_BUCKET']
    # For testing you can uncomment following and add your existing bucket
    # existingBucket = 'partner-kam-data-in-csv-1-s'

    if(existingBucket and existingBucket != ""):
        print("*** bucket selected =" + existingBucket)
        bucket = existingBucket


    bin = s3.Bucket(bucket)

    ####### Go through each folder, find unique and latest dates in the bucket ####### 
    unique_dates = set()
    unique_dates_obj = set()
    latest_date = ""
    meta_map = {}
    seg_df = pd.DataFrame()

    for bin_object in bin.objects.all():
        #print(bin_object.key)
        k = bin_object.key.split('/')
        if(len(k) < 2):
            continue
        dt = k[0]
        if k[1] == "_SUCCESS" and (dt not in unique_dates):
            unique_dates.add(dt)
            unique_dates_obj.add(datetime.strptime(dt, '%Y-%m-%d').date())
    
    #Store the latest date
    if len(unique_dates_obj) == 0:
        print('CDP no files to process')
        return

    latest_date = max(unique_dates_obj).strftime('%Y-%m-%d')
    datepath = latest_date + '/'

    ####### Let's get the data for latest date folder only ####### 
    master_df = pd.DataFrame()
    for bin_object in bin.objects.filter(Prefix= datepath):
        #print(bin_object.key)
        k = bin_object.key.split('/')

        # Get segments
        if len(k) > 3 and k[3] == "metadata.json":
            meta_json = read_s3_contents_with_download(bucket, bin_object.key).read().decode('utf-8')
            #print(meta_json)
            mj = json.loads(meta_json)
            acct_id = mj["metadata"]['AccountId']
            #bu = mj["metadata"]['Business Unit']

            meta_map[k[2]] = mj
            
            acct_id = mj["metadata"]["AccountId"]
            for seg in mj["segments"]:
                each_seg = {}
                each_seg["segmentId"] = seg["segmentId"]
                each_seg["segmentName"] = seg["segmentName"]            
                #each_seg["BU"] = bu
                #print(each_seg)    
                
                #seg_df = seg_df.append(each_seg, ignore_index=True)    
                each_seg_df = pd.DataFrame([each_seg])
                seg_df = pd.concat([seg_df, each_seg_df], axis=0, ignore_index=True)                


        #print( k)
        #print("*** before get activation records, key=" + bin_object.key)

        # get activation records for all files        
        if len(k) == 5 and k[4] != '':
            typeVal = ""
            if len(k) > 3 and "type=" in k[3]:
                t = k[3].split('=')
                typeVal = t[1]

            print("Process file=" + bin_object.key)
            f = read_s3_contents_with_download(bucket, bin_object.key)
            #print("*** Read the file")
            df = pd.read_csv(
                    f,
                    compression='gzip'
                )
            df["dt"] = dt
            df["account"] = k[1]
            df["Activation-Run-ID"] = k[2]
            df["ID-Type"] = typeVal
            df.rename(columns={"id": "IFA-Value"}, inplace=True)
            
            master_df = pd.concat([master_df, df], axis=0, ignore_index=True)        
    
    df = pd.merge(master_df, seg_df, left_on='adds', right_on='segmentId')
    df["Id"] = df["IFA-Value"] + df["segmentId"]
    df = df.replace(np.nan, '', regex=True)

    ####### Time to write the stage files ####### 
    print("Starting store, length=" )
    print(len(df))
    print(datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))

    # Printing the Information That the File Is Copied.
    stagebucket = os.environ['STAGE_BUCKET']
    today = datetime.today().strftime('%Y-%m-%d')
    k = "stage/" + today + ".csv"
    write_csv_to_s3(df, stagebucket, k)        
    k = "stage/" + "current.csv"
    write_csv_to_s3(df, stagebucket, k)        

    print('CDP In processing done')

def lambda_handler(event, context):
    print('Stage called')

    try:
        stage()
    except Exception as e: 
        print('Stage exception: '+ str(e))
    print('Stage complete')
    return {
        'statusCode': 200,
        'body': json.dumps('Staging complete!')
    }
    

# uncomment this for testing on local machine only
stage()