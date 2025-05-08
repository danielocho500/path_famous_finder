import os
import logging
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp"
}

async def manage_image_file(image: UploadFile, folder: str) -> tuple[int, str]:
    """
    Manage the image file uploaded by the user.
    Args:
        image (UploadFile): The image file uploaded by the user.
    Returns:
        tuple: A tuple containing a boolean indicating success or failure, and the image path.
    """
    if not image:
        return [400, "No image provided"]

    if image.content_type not in ALLOWED_MIME_TYPES:
        return [400, "Invalid image type"]

    try:
        contents = await image.read()

        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            resource_type="image"
        )

        return [200, result.get("secure_url")]
    except Exception as e:
        logging.error(f"Error uploading image: {e}")
        return [500, "Server error: " + str(e)]

async def upload_image_url(image_url: str, folder: str) -> tuple[bool, str]:
    """
    Upload an image from a URL to Cloudinary.
    Args:
        image_url (str): The URL of the image to upload.
        folder (str): The folder in which to store the image.
    Returns:
        tuple: A tuple containing a boolean indicating success or failure, and the image path.
    """
    try:
        result = cloudinary.uploader.upload(
            image_url,
            folder=folder,
            resource_type="image"
        )

        return [200, result.get("secure_url")]
    except Exception as e:
        logging.error(f"Error uploading image: {e}")
        return [500, "Server error" ]
