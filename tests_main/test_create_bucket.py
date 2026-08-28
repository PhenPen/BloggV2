from image_utils import _get_s3_client



s3_client = _get_s3_client()

# Create the bucket first
try:
    s3_client.create_bucket(Bucket="fastapi_bucket")
    print("Bucket created successfully!")
except s3_client.exceptions.BucketAlreadyOwnedByYou:
    print("Bucket already exists.")
