from datetime import date
from typing import Optional
from pydantic import BaseModel

class PostFamous(BaseModel):
    """PostFamous model for creating a new famous person."""
    real_name: str
    best_known_for: Optional[str] = ""
    profile_sumary_description: Optional[str] = ""
    principal_occupation: str
    other_occupations: Optional[list[str]] = []
    country_code: str
    city_born: str
    date_born: date
    date_died: Optional[date] = None
    nicknames: Optional[list[str]] = []
    image_url: Optional[str] = None
    more_info_url: Optional[str] = None
