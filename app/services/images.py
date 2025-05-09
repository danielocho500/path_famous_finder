import logging
from io import BytesIO
import requests
from database import cloudinary

async def upload_image_url(image_url: str, folder: str, object_id: str) -> tuple[bool, str]:
    """
    Upload an image from a URL to Cloudinary.
    Args:
        image_url (str): The URL of the image to upload.
        folder (str): The folder in which to store the image.
    Returns:
        tuple: A tuple containing a boolean indicating success or failure, and the image path.
    """

    object_id = object_id.replace(":", "_")

    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        logging.debug(f"public_id: {folder}/{object_id}")
        result = cloudinary.uploader.upload(
            BytesIO(response.content),
            folder=folder,
            public_id=object_id,
            overwrite=True,
            resource_type="image",
            unique_filename=False,
            filename_override=object_id
        )


        return [200, result.get("secure_url")]
    except Exception as e:
        logging.error(f"Error uploading image: {e}")
        return [500, "Server error" ]
