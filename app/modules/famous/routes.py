import logging
from fastapi import APIRouter
from modules.famous.models import PostFamous
from modules.shared.validators import get_country_by_code
from modules.shared.response import create_json_response
from services.famous import save_new_famous

famous_router = APIRouter()

@famous_router.post("",
    description="Register a new famous person",
    name="register_famous",
    operation_id="register_famous")
def register_famous(famous: PostFamous):
    """
    Register a new famous person
    Args:
        famous (PostFamous): The famous person to register
    
    Returns:
        dict: The registered famous person
    """
    logging.info(f"Registering famous person: {famous.real_name}")

    # Validaciones
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

    # Llamar al controlador con parámetros seguros
    status_code, message = save_new_famous(famous, country_code)

    if status_code != 200:
        return 1

    return 1
