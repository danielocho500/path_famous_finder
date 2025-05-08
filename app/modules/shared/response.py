import logging
from fastapi.responses import JSONResponse

def create_json_response(status_code: int, content: dict) -> JSONResponse:
    """
    Create a JSON response with the given status code and content.
    
    Args:
        status_code (int): The HTTP status code.
        content (dict): The content of the response.
    
    Returns:
        JSONResponse: The JSON response object.
    """
    logging.info(f"Response: {status_code}")
    return JSONResponse(status_code=status_code, content=content)
