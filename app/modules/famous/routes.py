from fastapi import APIRouter
from models import PostFamous

famous_router = APIRouter()

@famous_router.post("/famous",
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
    pass
