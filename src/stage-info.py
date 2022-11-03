import os
import boto3
import json
from datetime import datetime
from botocore.exceptions import ClientError

session = boto3.Session()
s3 = session.resource('s3')

def read_s3_contents_with_download(bucket, k):
    response = s3.Object(bucket, k).get()
    return response['Body']

def info(event):
    #setup resources    
    is_fake = False
    
    print("***Stage Info called")
    print(datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
    
    in_bucket_name = os.environ['IN_BUCKET']
    data_bucket_name = in_bucket_name

    existing_bucket_name = os.environ['EXISTING_BUCKET'] 
    stage_bucket_name = os.environ['STAGE_BUCKET']
    print("In bucket=" + in_bucket_name)
    print("Existing Bucket=" + existing_bucket_name) # If you passed during cloudformatin stack creation
    
    if(existing_bucket_name and existing_bucket_name != ""):
        print("*** Data bucket selected =" + existing_bucket_name)
        data_bucket_name = existing_bucket_name

    print(event)

    if 'fake' in event:    
        print("*** Using fake Data bucket")
        is_fake = True
        data_bucket_name = os.environ['FAKE_BUCKET']

    print("*** Data bucket name =" + data_bucket_name)    
    data_bucket = s3.Bucket(data_bucket_name)
    stage_bucket = s3.Bucket(stage_bucket_name) 
    
    #delete existing stage data    
    for obj in stage_bucket.objects.filter(Prefix='stage/latest/'):
        s3.Object(stage_bucket.name,obj.key).delete()

    ####### Go through the incoming data bucket's each folder, find unique and latest dates ####### 
    unique_accounts = set()
    unique_dates = set()
    unique_dates_obj = set()
    latest_date = ""

    for bin_object in data_bucket.objects.all():
        k = bin_object.key.split('/')
        if(len(k) < 2):
            continue
        dt = k[0]
        if k[1] == "_SUCCESS" and (dt not in unique_dates):
            unique_dates.add(dt)
            unique_dates_obj.add(datetime.strptime(dt, '%Y-%m-%d').date())
    
    #Store the latest date
    if len(unique_dates_obj) == 0 :
        print('CDP no data to process')
        return

    latest_date = max(unique_dates_obj).strftime('%Y-%m-%d')
    datepath = latest_date + '/'

    ####### Let's get the data for latest date folder only #######     
    # For the latest date get unique accounts 
    for bin_object in data_bucket.objects.filter(Prefix= datepath):
        k = bin_object.key.split('/')
        if k[1] != "_SUCCESS":
            unique_accounts.add(k[1])

    print(unique_accounts)

    latest_data = {}
    latest_data["latest_date"] = latest_date
    latest_data["unique_accounts"] = list(unique_accounts)
    latest_data["fake"] = is_fake

    # -- End write activation processing results                 
    print("Completed getting latest date and accounts")
    return latest_data

def lambda_handler(event, context):
    print('Info called')
    latest_data = {}
    try:
        latest_data = info(event)
        print("latest data")
        print(latest_data)
    except Exception as e: 
        print('Stage exception')
        print(e)
    print('Stage complete')
    return {
        'statusCode': 200,
        'body': latest_data
    }
    
# uncomment this for testing on local machine only
#info()