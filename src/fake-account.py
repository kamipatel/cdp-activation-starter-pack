'''
data-part.csv
id,adds,removes
02574cfc3b85290c91d775669ab149193bc2ba899da438875736471fa4c5ec88,1sg8c000000XZJ4,""

2022-08-11/
account1/
xyz4a4ab-9e74-4fe4-9273-336516cafxyz/
type=HEM_SHA256/
part-00006-06d7f2b7-cda8-4bf3-be37-2942a663558b.c000.csv.gz

metadata.json
{"metadata":{"AccountId":"isvscdptest2aid"},"segments":[{"segmentId":"1sg8c000000XZJ4","segmentName":"test1"},{"segmentId":"1sg8c000000XZTY","segmentName":"New Loyalty Members 2"}]}
'''

import os
import boto3
import pandas as pd
import json
from io import StringIO
from io import BytesIO
from datetime import datetime
from botocore.exceptions import ClientError
import numpy as np

session = boto3.Session()
s3 = session.resource('s3')

def read_s3_contents_with_download(bucket, k):
    response = s3.Object(bucket, k).get()
    return response['Body']

def chunker(seq, size):
        for pos in range(0, len(seq), size):
            yield seq.iloc[pos:pos + size] 

def write_csv_to_s3(df, bucket, k):
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.Bucket(bucket).put_object(Key= k, Body=csv_buffer.getvalue())     

def fake(account, total_segments, total_activations, chunk_size):    
    print("Initiating fake for an account->"  + account)    

    print(datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
    fake_bucket_name = os.environ['FAKE_BUCKET']
    print("fake_bucket_name=" + fake_bucket_name)  
    fake_bucket = s3.Bucket(fake_bucket_name) 

    print("Start processing faking of Account ->" + account)       

    today = datetime.today().strftime('%Y-%m-%d')

    jsondata = {}
    metadata={}
    segments={}
    segment_list=[]
    metadata['AccountId'] = account
    for seg in range(total_segments):
        a_segment={
            "segmentId": "seg-" + str(seg+1),
            "segmentName": "segment " + str(seg+1)
        }
        segment_list.append(a_segment)
    segments = segment_list

    jsondata['metadata'] = metadata
    jsondata['segments'] = segments
    print('*** metadata.json done')

    # -- Start fake

    # Copy _SUCCESS file first "2022-08-11/account1/"
    source = {
        'Bucket': 'cdp-pub-us-east-1',
        'Key': '_SUCCESS'
    }
    k= today + "/_SUCCESS"
    s3.Bucket(fake_bucket_name).put_object(Key= k, Body='')    

    print("k=" + k)       
    print("Start activation files")            

    # Copy metadata.json file "2022-08-11/account1/xyz4a4ab-9e74-4fe4-9273-336516cafxyz/metadata-account-1.json"
    accountsubpath = "xyz4a4ab-9e74-4fe4-9273-336516cafxyz"
    path256 = "type=HEM_SHA256"
    
    k= today + "/" + account + "/" + accountsubpath + "/metadata.json"
    s3.Bucket(fake_bucket_name).put_object(Key= k, Body=json.dumps(jsondata))    
    print("Stored json for Account-" + account + ', k=' + k)            

    print("Begin Segment")            
    # Create activations        
    for seg in range(total_segments):                    
        print("Inside Segment " + str(seg+1))            
        df = pd.DataFrame() #activation data
        activations = []
        for a in range(total_activations):  
            each_activation = {}
            each_activation["id"] = "02574cfc3b85290c91d775669ab149193bc2ba899da438875736471fa4c5ec88" + str(a)
            each_activation["adds"] = "seg-" + str(seg+1)
            each_activation["removes"] = ""
            activations.append(each_activation)

        each_activation_df = pd.DataFrame(activations)
        df = pd.concat([df, each_activation_df], axis=0, ignore_index=True)                  

        #print(df.head())
        #print(len(df))
        print("Begin Chuck")            
        i = 0
        for odf in chunker(df, chunk_size):
            #print(odf.head())
            #print(len(odf))
            i = i + 1                
            csv_buffer = BytesIO()
            odf.to_csv(csv_buffer, index=False, compression="gzip")
            k = today + "/" + account + "/" + accountsubpath + "/" + path256 + "/" + "part-00000-06d7f2b7-cda8-4bf3-be37-2942a663558b.c000" + str(seg+1) + str(i) + ".csv.gz"
            s3.Bucket(fake_bucket_name).put_object(Key= k, Body=csv_buffer.getvalue())    
            print("gzip stored") 

    # -- End fake
    print(datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
    print('CDP data faking complete!')

def lambda_handler(event, context):
    print('fake data called')

    try:        
        #setup resources
        # How many accounts, segments in each account and activations in each segment?    
        account = event['account']
        total_segments= event['total_segments']
        total_activations= event['total_activations']
        chunk_size = event['chunk_size']
            
        fake(account,total_segments, total_activations, chunk_size)
        print('Fake data generation complete')
    except Exception as e: 
        print('fake data exception: '+ str(e))    
    return {
        'statusCode': 200,
        'body': json.dumps('fake complete!')
    }
    

# uncomment this for testing on local machine only
#fake()