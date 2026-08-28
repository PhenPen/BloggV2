import os

import boto3
from dotenv import load_dotenv

load_dotenv()

# Instantiate client using environment settings
s3 = boto3.client(
    's3',
    endpoint_url=os.getenv('AWS_ENDPOINT_URL'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_DEFAULT_REGION')
)

# Test bucket creation & file upload
bucket_name = "my-test-bucket"
s3.create_bucket(Bucket=bucket_name)
s3.put_object(Bucket=bucket_name, Key="hello.txt", Body=b"Hello from Moto!")

# Verify
response = s3.list_objects_v2(Bucket=bucket_name)
print("Files in bucket:")
for obj in response.get('Contents', []):
    print(f" - {obj['Key']}")