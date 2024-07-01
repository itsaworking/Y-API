from pydantic import BaseModel
from app.models import City
from sqlalchemy.orm import Session
from fastapi import Request

GEO_COOKIE = "geolocation"

class GeoLocation(BaseModel):
    city: str = "New York"
    state_code: str = "NY"
    zip: str = "10010"


def get_geo_from_city(city: City):
    return GeoLocation(city=city.name, state_code=city.state_code, state=city.zip)


def get_geo(request: Request, city: City = None) -> GeoLocation:

    if city:
        return get_geo_from_city(city)
    
    # return default
    return GeoLocation()


