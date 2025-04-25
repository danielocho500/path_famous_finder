from datetime import date
from typing import Optional
from pydantic import BaseModel

class Famous(BaseModel):
    """Famous person model to use with neo4j"""
    uid: str = None
    real_name: str = None
    best_known_for: str = None
    profile_sumary_description: str = None
    principal_occupation: str = None
    other_occupations: Optional[list[str]] = None
    country_code: str = None
    city_born: str = None
    visited_times : int = 0
    date_born: date = None
    date_died: Optional[date] = None
    nicknames: Optional[list[str]] = None
    image_url: str = None
    image_url_small: str = None
    more_info_url: str = None
