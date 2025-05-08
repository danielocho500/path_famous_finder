from urllib.parse import urlparse
import re
import pycountry

def get_country_by_code(country: str) -> str:
    """
    Get country by code
    Args:
        country (str): The country code
    Returns:
        str: The country code
    """
    try:
        country = pycountry.countries.search_fuzzy(country)
    except LookupError:
        return None

    return country[0].alpha_2

def is_valid_url(url: str) -> bool:
    """
    Enhanced URL validation with optional scheme restriction.
    
    Args:
        url (str): The URL to validate
        allowed_schemes (set): Set of allowed URL schemes (default: {'http', 'https', 'ftp'})
        
    Returns:
        bool: True if valid URL, False otherwise
    """
    allowed_schemes: set = {'http', 'https'}
    try:
        result = urlparse(url)

        if result.scheme not in allowed_schemes:
            return False

        if not result.netloc:
            return False

        domain_pattern = re.compile(
            r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$',
            re.IGNORECASE
        )

        if not re.match(domain_pattern, result.netloc.split(':')[0]):
            return False

        return True
    except Exception:
        return False

def is_image_url(url: str) -> bool:
    """
    Valida si una URL es de una imagen, verificando esquema, dominio y extensión.
    
    Args:
        url (str): La URL a validar
        allowed_schemes (set): Esquemas permitidos (default: {'http', 'https'})
        
    Returns:
        bool: True si es una URL válida de imagen, False en caso contrario
    """
    allowed_schemes: set = {'http', 'https'}

    IMAGE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.webp',
        '.bmp', '.tiff', '.svg', '.ico', '.jfif'
    }

    try:
        result = urlparse(url)

        if result.scheme not in allowed_schemes:
            return False

        if not result.netloc:
            return False

        domain_pattern = re.compile(
            r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$',
            re.IGNORECASE
        )

        if not re.match(domain_pattern, result.netloc.split(':')[0]):
            return False

        path = result.path.lower()
        if not any(path.endswith(ext) for ext in IMAGE_EXTENSIONS):
            return False

        return True

    except Exception:
        return False
