import logging
from uuid import uuid4
from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool
from modules.famous.models import PostFamous
from modules.shared.validators import get_country_by_code, is_image_url
from modules.shared.response import create_json_response
from services.famous import save_new_famous
from services.images import delete_image, upload_image_url

famous_router = APIRouter()

@famous_router.post("",
    description="Register a new famous person",
    name="register_famous",
    operation_id="register_famous")
async def register_famous(famous: PostFamous):
    """
    Register a new famous person
    Args:
        famous (PostFamous): The famous person to register
    
    Returns:
        dict: The registered famous person
    """
    logging.info(f"Registering famous person: {famous.real_name}")

    if famous.real_name == famous.best_known_for:
        return create_json_response(400, {"message": "real_name and best_known_for must be different"})

    country_code = get_country_by_code(famous.country)
    if country_code is None:
        return create_json_response(400, {"message": "country is not valid"})

    # Validar fecha de muerte posterior a fecha de nacimiento
    if famous.date_died and famous.date_died < famous.date_born:
        return create_json_response(400, {"message": "date_died must be after date_born"})

    if famous.principal_occupation in (famous.other_occupations or []):
        return create_json_response(
            400,
            {"message": "principal_occupation and other_occupations must be different"},
        )

    if not is_image_url(famous.image_url):
        return create_json_response(400, {"message": "image_url is not valid"})

    image_id = uuid4().hex
    image_status, uploaded_image_url = await run_in_threadpool(
        upload_image_url, famous.image_url, "famous", image_id
    )
    if image_status != 200:
        return create_json_response(502, {"error": "image upload failed"})

    famous_with_image = famous.model_copy(update={"image_url": uploaded_image_url})
    status_code, _ = await run_in_threadpool(
        save_new_famous, famous_with_image, country_code
    )

    if status_code != 201:
        await run_in_threadpool(delete_image, "famous", image_id)
        return create_json_response(status_code, {"error": "server error"})

    return create_json_response(status_code, {"message":"famoso registrado"})
