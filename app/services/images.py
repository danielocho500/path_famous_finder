import logging
from io import BytesIO
import requests
from database import cloudinary

def upload_image_url(image_url: str, folder: str, object_id: str) -> tuple[int, str]:
    """
    Upload an image from a URL to Cloudinary.
    Args:
        image_url (str): The URL of the image to upload.
        folder (str): The folder in which to store the image.
    Returns:
        tuple: Status code and the uploaded image URL.
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


        secure_url = result.get("secure_url")
        if not secure_url:
            delete_image(folder, object_id)
            return 500, "Server error"

        return 200, secure_url
    except Exception as e:
        logging.error(f"Error uploading image: {e}")
        return 500, "Server error"


def delete_image(folder: str, object_id: str) -> bool:
    """Remove an uploaded image when its database record cannot be created."""
    try:
        result = cloudinary.uploader.destroy(f"{folder}/{object_id}")
        if result.get("result") in ("ok", "not found"):
            return True
        logging.error(f"Could not remove image {folder}/{object_id}: {result}")
    except Exception as e:
        logging.error(f"Error removing image {folder}/{object_id}: {e}")
    return False
