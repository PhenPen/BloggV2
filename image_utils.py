import uuid
from io import BytesIO
# from pathlib import Path  # Stopped using Path since we are uploading globally now


from PIL import Image, ImageOps

import boto3

from mypy_boto3_s3 import S3Client

from config import settings
from starlette.concurrency import run_in_threadpool

# PROFILE_PICS_DIRECTORY = Path(r"media\profile_pics")  
# Removed Profile picture directory since we don't need that as we aren't uploading to local storage again but rather to AWS using boto3 SDK


def _get_s3_client() -> S3Client:

    return boto3.client(
        "s3",
        region_name=settings.aws_default_region,
        aws_access_key_id=settings.aws_access_key_id.get_secret_value() if settings.aws_access_key_id else None,
        aws_secret_access_key=settings.aws_secret_access_key.get_secret_value() if settings.aws_secret_access_key else None,
        endpoint_url=settings.aws_endpoint_url,
    )

def process_profile_image(content: bytes) -> tuple[bytes, str] : # content : bytes doesn't actually convert the content to bytes but is a type hint to show that we should sent byte contents
    with Image.open(BytesIO(content)) as image_content:

        # why are we not passing content directly as we have already said it to be bytes, why pass into BytesIO
        # BytesIO seems to be a module for either converting the file to bytes or sending the file content as bytes 
        # Then Image.open seems to be pillow context manager for opening and cleaning up images, what is ImageOps though ? Image operations ?
        # Transpose from matrix is rotating I think, row becomes columns and columns become row, so it would have to be something about rotating the image orientation
        # Why exif transpose though ? What is exif in images 
        img_orientation_fix = ImageOps.exif_transpose(image_content)

        # Checked an exif is a way images store things ? So basically, instead of rotating the image manually, we check if it is said to be rotated in the exif data, when Pillow handles that for us

        img_cropped = ImageOps.fit(img_orientation_fix, (300,300),method= Image.Resampling.LANCZOS)
        # Now, the .fit method is used to crop the image , while maintaining the aspect ratio without distorting the image, we pass in a tuple of the size we want it to be, which in this case, we are using a square for the profile picture of the size 300 by 300 for height and width
        # I'm not sure about the methods or LANCZOS though, sampling is measuring data discretely not sure about resampling, seems to be a photography term or image editing term


        if img_cropped.mode in ["RGBA", "LA", "P"]:
            img_cropped = img_cropped.convert("RGB")

            # The if statement above seems to be for colour mode correction , seems I would have to learn about JPEGs,PNGs, GIFs, Transparency, Palette mode

        filename = f"{uuid.uuid4().hex}.jpg"
        # Why are we adding hex at the back though? uuid.uuid4() generates a random uuid

        # file_path = PROFILE_PICS_DIRECTORY/ filename  # We aren't saving to local storage anymore

        # I think this solves the issues of having the same file name 

        # PROFILE_PICS_DIRECTORY.mkdir(parents=True, exist_ok=True) # We aren't saving to local storage anymore


        # parents in Path just tells the parent folder of the directory should be created if it doesn't exist
        # exist_ok in Path just tells Path if that filepath already exists, just ignore instead of throwing an error 


        # img_cropped.save(file_path, "JPEG",quality = 85, optimize = True)

        # Instead of saving to a file path, we would save to a bytes object

        byte_object = BytesIO()

        img_cropped.save(byte_object, "JPEG",quality = 85, optimize = True)

        # Dunno what quality and optimize does though 

        byte_object.seek(0)  # Seek is meant to tell you where the bytes would be streamed from as bytes could be read from any position but setting it to 0 tells the reading/streaming of bytes to start from the beginning

        return byte_object.read(), filename



# We would comment this whole function out because we aren't deleting from local storage again but instead would try to delete from AWS so we would create another function for that 

# def delete_profile_image(filename : str | None):
#     if filename is None:
#         return 
#
#     filepath = PROFILE_PICS_DIRECTORY / filename
#
#     if filepath.exists():
#         filepath.unlink()  #.unlink is a Path method for deleting files, note that it doesn't work on directories though and might throw an error, if directory, we user rmdir() instead


def _upload_to_s3(file_bytes: bytes, object_key : str) -> None:

    """ Takes in a byte object of the file and a object key which is used to identify the file"""

    S3 = _get_s3_client()

    S3.upload_fileobj(    # Note that there is .uploadfile and .uploadfileobj, the second one is used for uploading bytes and file like objects 
        BytesIO(file_bytes),
        settings.aws_bucket_name,
        object_key,
        ExtraArgs={"content/type" : "image/jpeg"},
    )

    # We added content/type in the Extra Args because if we don't set that, browsers can sometimes download the image instead of displaying it, but setting it to image JPEG, it behaves the way that you would expect.
    # Also note that it must not be JPEG but it should be the image format that you uploaded, so if you did for a png file, you would do image/png




def _delete_from_s3(object_key : str) -> None:

    S3 = _get_s3_client()

    S3.delete_object(Bucket=settings.aws_bucket_name, Key=object_key)


# If you notice, the most of the functions above are synchronous because they use CPU, now we can't use async for those, so we would create an async wrapper for passing it into threads, which are the functions below

## Async S3 wrappers for image_utils.py
async def upload_profile_image(file_bytes: bytes, filename: str) -> None:
    key = f"profile_pics/{filename}"  # Note that our key must match our bucket and IAM policy names
    await run_in_threadpool(_upload_to_s3, file_bytes, key)

async def delete_profile_image(filename: str | None) -> None:
    if filename is None:   # In what scenario would file name be none though ? Probably if it has been deleted from the server already ?
        return
    key = f"profile_pics/{filename}"  # Note that our key must match our bucket and IAM policy names
    await run_in_threadpool(_delete_from_s3, key)

    # Remember when I said this # Note that our key must match our bucket and IAM policy names # If you check our policy, the resource would probably look something like this "Resource": "arn:aws:s3:::fastapi-blog-uploads/profile_pics/*", where "fastapi-blog-uploads" would be the bucket name and "/profile_pics/*" would be the folder, so what this is basically saying is that , this "/profile_pics/*" should match the key, you can see that "/profile_pics/*" and f"profile_pics/{filename}" are similar