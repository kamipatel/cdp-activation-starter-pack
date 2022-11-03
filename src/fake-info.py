import os
import boto3
from datetime import datetime

'''
{
	"total_accounts": 3,
	"total_segments" : 3,
    "total_activations" : 6,
    "chunk_size": 4
}

{
	"total_accounts": 100,
	"total_segments" : 5,
    "total_activations" : 100000,
    "chunk_size": 10000
}

{
    "fake": "fake"
}
'''

session = boto3.Session()
s3 = session.resource('s3')

def lambda_handler(event, context):
    print('Info called')

    accounts = []
    data = {}
    
    try:

        #delete existing fake data    
        print("Initiating fake for an account" )    

        print(datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
        fake_bucket_name = os.environ['FAKE_BUCKET']
        print("fake_bucket_name=" + fake_bucket_name)  
        fake_bucket = s3.Bucket(fake_bucket_name) 

        today = datetime.today().strftime('%Y-%m-%d')
        for obj in fake_bucket.objects.all():
            s3.Object(fake_bucket.name,obj.key).delete()

        total_accounts = event['total_accounts']
        for i in range(total_accounts):
            accounts.append("account-" + str(i +1))        

        data["accounts"] = accounts
        data["total_segments"] = event['total_segments']
        data["total_activations"] = event['total_activations']
        data["chunk_size"] = event['chunk_size']

    except Exception as e: 
        print(e)
    print('Fake Info complete')
    return {
        'statusCode': 200,
        'body': data
    }
    
