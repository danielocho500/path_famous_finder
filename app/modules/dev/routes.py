import logging
from fastapi import APIRouter

dev_router = APIRouter()

@dev_router.get("/healthCheck")
def health_check():
    """
    Health check endpoint
    """
    logging.info("Health check endpoint called")
    return {"status": "up"}
