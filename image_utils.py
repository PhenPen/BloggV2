import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

PROFILE_PICS_DIRECTORY = Path(r"media\profile_pics")

def process_profile_image(content: bytes) -> str : # content : bytes doesn't actually convert the content to bytes but is a type hint to show that we should sent byte contents
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

        file_path = PROFILE_PICS_DIRECTORY/ filename

        # I think this solves the issues of having the same file name 

        PROFILE_PICS_DIRECTORY.mkdir(parents=True, exist_ok=True)
        # parents in Path just tells the parent folder of the directory should be created if it doesn't exist
        # exist_ok in Path just tells Path if that filepath already exists, just ignore instead of throwing an error 

        img_cropped.save(file_path, "JPEG",quality = 85, optimize = True)

        # Dunno what quality and optimize does though 

        return filename


def delete_profile_image(filename : str | None):
    if filename is None:
        return 

    filepath = PROFILE_PICS_DIRECTORY / filename

    if filepath.exists():
        filepath.unlink()  #.unlink is a Path method for deleting files, note that it doesn't work on directories though and might throw an error, if directory, we user rmdir() instead

