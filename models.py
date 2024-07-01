from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Float, DECIMAL, BigInteger, JSON
from sqlalchemy.orm import relationship, Session
from .db import Base
import sqlalchemy.types as types
from sqlalchemy import func
from sqlalchemy.orm import validates
from pydantic.dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import pydantic
from . import util
from urllib.parse import urlparse
from app.schemas.yext import YextData
from app.settings import settings
from sqlalchemy.ext.hybrid import hybrid_method
import math


class ValidationError(Exception):
    def __init__(self, field: str, message: str):
        super().__init__("Validation error")
        self.field = field
        self.message = message

    def errors(self):
        return [{"loc": ["body", self.field], "msg": self.message}]


class Point(types.UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "POINT"

    def bind_expression(self, bindvalue):
        return func.ST_GeomFromText(bindvalue)

    def column_expression(self, col):
        return func.ST_AsText(col)


class BaseModel:
    def fill(self, **kwargs):
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise Exception(f"Unknown model atribute '{key}'")
            setattr(self, key, value)


class HasGeo:
    _latitude = Column("latitude", DECIMAL(8, 6))
    _longitude = Column("longitude", DECIMAL(9, 6))
    _geo = Column("geo", Point)

    @property
    def latitude(self):
        return self._latitude

    @latitude.setter
    def latitude(self, value):
        self._latitude = value
        if self._latitude and self._longitude:
            self._geo = "POINT(%s %s)" % (self._latitude, self._longitude)

    @property
    def longitude(self):
        return self._longitude

    @longitude.setter
    def longitude(self, value):
        self._longitude = value
        if self._latitude and self._longitude:
            self._geo = "POINT(%s %s)" % (self._latitude, self._longitude)

    @property
    def geo(self):
        return (self._latitude, self._longitude)

    @geo.setter
    def geo(self, value):
        self._latitude = value[0]
        self._longitude = value[1]
        if self._latitude and self._longitude:
            self._geo = "POINT(%s %s)" % (self._latitude, self._longitude)

    def get_bounding_box(lat, lng, miles):
        return {
            "min_lat": lat - miles / 69.172,
            "max_lat": lat + miles / 69.172,
            "min_lng": lng - miles / 69.172 / math.cos(math.radians(lat)),
            "max_lng": lng + miles / 69.172 / math.cos(math.radians(lat))
        }

    @hybrid_method
    def within_radius(self, lat, lng, radius_miles):
        bbox = self.get_bounding_box(lat, lng, radius_miles)
        polygon = 'POLYGON((%s %s,%s %s,%s %s,%s %s,%s %s))' % (
            bbox['min_lat'], bbox['min_lng'],
            bbox['min_lat'], bbox['max_lng'],
            bbox['max_lat'], bbox['max_lng'],
            bbox['max_lat'], bbox['min_lng'],
            bbox['min_lat'], bbox['min_lng'],
        )
        return func.ST_CONTAINS(func.st_GeomFromText(polygon), self._geo)


class HasTimestamps:
    date_created = Column(DateTime)
    date_updated = Column(DateTime)


class Page(BaseModel, Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, index=True)
    title = Column(String, unique=False, index=False)
    meta_keywords = Column(String, unique=False, index=False)
    meta_description = Column(String, unique=False, index=False)
    content = Column(String, unique=False, index=False)
    canonical_url = Column(String, unique=False, index=False)


class City(BaseModel, HasTimestamps, Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)
    name = Column(String, unique=False, index=False)
    state = Column(String, unique=False, index=False)
    zip = Column(String, unique=False, index=False)
    county = Column(String, unique=False, index=False)
    state_code = Column(String, unique=False, index=False)
    country_code = Column(String, unique=False, index=False)
    latitude = Column(Float, unique=False, index=False)
    longitude = Column(Float, unique=False, index=False)


class BaseStore:
    @property
    def categories(self):
        return []

    @property
    def emails(self):
        return []

    @property
    def payment_options(self):
        return []

    @property
    def gallery_images(self):
        return []

    @property
    def homepage_url_hostname(self):
        if not self.homepage_url:
            return None
        u = urlparse(self.homepage_url)

        return u.hostname


class LocalStore(BaseModel, HasGeo, HasTimestamps, BaseStore, Base):
    __tablename__ = "local_stores"

    id = Column(Integer, primary_key=True, index=True)
    canonical_id = Column(Integer, primary_key=False, index=True)
    name = Column(String, unique=False, index=True)
    description = Column(String, unique=False, index=False)
    slug = Column(String, unique=True, index=True)
    address1 = Column(String, unique=False, index=False)
    address2 = Column(String, unique=False, index=False)
    city = Column(String, unique=False, index=False)
    state = Column(String, unique=False, index=False)
    zip = Column(String, unique=False, index=False)
    phone = Column(String, unique=False, index=False)
    country = Column(String, unique=False, index=False)
    homepage_url = Column(String, unique=False, index=False)
    facebook_url = Column(String, unique=False, index=False)
    twitter_handle = Column(String, unique=False, index=False)
    hours_text = Column(String, unique=False, index=False)
    yext_id = Column(BigInteger, unique=False, index=False)
    yext_canceled = Column(Boolean, unique=False, index=True)
    yext_suppressed = Column(Boolean, unique=False, index=True)
    show_address = Column(Boolean, default=False)
    date_deleted = Column(DateTime)

    _image_url = Column("image_url", String, unique=False, index=False)
    _yext_data = Column("yext_data", JSON, unique=False, index=False)
    _yext_data_obj = None

    @validates("name", "address1", "city", "state", "zip", "phone")
    def validate_not_empty(self, key, value):
        if not value or not isinstance(value, str) or len(value) == 0:
            raise ValidationError(key, f"{key} is required")
        return value

    @staticmethod
    def get_by(db: Session, include_deleted=False, **kwargs,):
        filter = kwargs
        if not include_deleted:
            filter['date_deleted'] = None

        return db.query(LocalStore).filter_by(**filter).one()

    @staticmethod
    def find_by(db: Session, include_deleted=False, **kwargs,):
        filter = kwargs
        if not include_deleted:
            filter['date_deleted'] = None

        return db.query(LocalStore).filter_by(**filter).all()

    @property
    def status(self):
        if self.yext_id and not self.yext_canceled and not self.yext_suppressed:
            return "ACTIVE"

        if self.yext_suppressed:
            return "SUPPRESSED"

        return "AVAILABLE"

    @property
    def yext(self) -> Optional[YextData]:
        if self._yext_data_obj:
            return self._yext_data_obj

        if not self._yext_data:
            return None

        self._yext_data_obj = YextData(
            suppressed=self.yext_suppressed, canceled=self.yext_canceled, id=self.yext_id, **self._yext_data)
        return self._yext_data_obj

    @yext.setter
    def yext(self, yext_data: YextData):
        if yext_data:
            self._yext_data_obj = yext_data
            self._yext_data = yext_data.dict()
        else:
            self._yext_data_obj = None
            self._yext_data = None

    @property
    def image_url(self):
        if self.yext and self.yext.logo_url:
            return self.yext.logo_url

        return self._image_url

    @property
    def phone_formatted(self):
        if self.phone:
            return util.phone_format(self.phone)

    @property
    def address_text(self):
        if not self.address1:
            return None

    @property
    def canonical_path(self):
        return f"/stores/local/{self.slug}"

    @property
    def categories(self):
        if self.yext and self.yext.categories:
            return self.yext.categories
        return []

    @property
    def emails(self):
        if self.yext and self.yext.emails:
            return self.yext.emails
        return []

    @property
    def payment_options(self):
        if self.yext and self.yext.payment_options:
            return self.yext.payment_options
        return []

    @property
    def gallery_images(self):
        if self.yext and self.yext.gallery_images:
            return self.yext.gallery_images
        return []

    @property
    def videos(self):
        if self.yext and self.yext.videos:
            return self.yext.videos
        return []

    @property
    def url(self):
        return f"{settings.app_url}/stores/local/{self.slug}"


class OnlineStore(BaseModel, HasTimestamps, BaseStore, Base):
    __tablename__ = "online_stores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=False, index=True)
    description = Column(String, unique=False, index=False)
    slug = Column(String, unique=True, index=True)

    homepage_url = Column("homepage_url", String, unique=False, index=False)
    affiliate_homepage_url = Column(String, unique=False, index=False)

    @property
    def canonical_path(self):
        return f"/stores/online/{self.slug}"


class Chain(BaseModel, HasTimestamps, BaseStore, Base):
    __tablename__ = "chains"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=False, index=True)
    description = Column(String, unique=False, index=False)
    slug = Column(String, unique=True, index=True)

    homepage_url = Column("homepage_url", String, unique=False, index=False)

    @property
    def canonical_path(self):
        return f"/stores/chain/{self.slug}"
