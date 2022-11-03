import os
import boto3
import pandas as pd
import json
from io import StringIO
from datetime import datetime
from botocore.exceptions import ClientError

session = boto3.Session()
s3 = session.resource('s3')

def write_csv_to_s3(df, bucket, k):
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.Bucket(bucket).put_object(Key= k, Body=csv_buffer.getvalue())     

def summary():
    df= pd.DataFrame()
    #setup resources
    summarybucket = os.environ['SUMMARY_BUCKET']
    today = datetime.today().strftime('%Y-%m-%d')
    k = "data/" + today + ".csv"
    write_csv_to_s3(df, summarybucket, k)        

    # Extract column names into a list
    names = [x for x in df.columns]
    
    # Create empty DataFrame with those column names
    master_df_schema = pd.DataFrame(columns=names)
    k = "data/" + "schema_sample.csv"
    write_csv_to_s3(master_df_schema, summarybucket, k)

    # Printing the Information That the File Is Copied.
    print('summary done')

def lambda_handler(event, context):
    print('summary called')
    try:
        summary()
    except Exception as e: 
        print('summary exception: '+ str(e))
    print('summary complete')
    return {
        'statusCode': 200,
        'body': json.dumps('summary complete!')
    }
    
summary()