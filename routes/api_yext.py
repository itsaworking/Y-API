from fastapi import Request
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session
from app.schemas import yext
from app.db import get_db
from app import models
from app.settings import settings
from app.models import LocalStore
from starlette.exceptions import HTTPException as StarletteHTTPException
from slugify import slugify
from datetime import datetime
from fastapi.exceptions import RequestValidationError
from typing import Optional

app = FastAPI(docs_url=None, redoc_url=None)


@app.exception_handler(StarletteHTTPException)
@app.exception_handler(NoResultFound)
@app.exception_handler(RuntimeError)
def http_exception_handler(request, exc: NoResultFound):
    return JSONResponse({"error": {"message": "Not found"}}, 404)


@app.exception_handler(RequestValidationError)
@app.exception_handler(models.ValidationError)
def validation_exception_handler(request, exc: RequestValidationError):
    issues = []
    for err in exc.errors():
        issues.append({
            "description": err.get("msg"),
            "field": ".".join(str(s) for s in list(err.get("loc", []))[1:])
        })
    return JSONResponse({"status": "REJECTED", "issues": issues}, 409)


@app.exception_handler(Exception)
def http_exception_handler(request, exc: Exception):
    return JSONResponse({"error": {"message": str(exc)}}, 500)


def generate_local_slug(db: Session, store: LocalStore):
    base_slug = slugify(f"{store.name} {store.city} {store.zip}")
    slug = base_slug
    index = 1
    while db.query(LocalStore).filter((LocalStore.slug == slug) & (LocalStore.id != store.id)).count() > 0:
        slug = base_slug + f"-{index}"
        index += 1

    return slug


@app.post("/powerlistings/order")
def yext_listing_order(order: yext.YextListingCreate, db: Session = Depends(get_db)):

    # Check if the store already exists by yextId
    if order.yextId:
        existing_store = db.query(LocalStore).filter(LocalStore.yext_id == order.yextId).first()
        if existing_store:
            raise HTTPException(status_code=400, detail="Listing with yextId already exists.")

    yext_data = yext.YextData(
        images=order.images,
        categories=order.categories,
        payment_options=order.paymentOptions,
        emails=order.emails,
        videos=order.videos,
        special_offer=order.specialOffer,
        urls=order.urls,
        phones=order.phones
    )

    # Create a new store listing
    store = LocalStore(
        name=order.name,
        description=order.description,
        phone=yext_data.main_phone,
        yext_id=order.yextId,
        yext_canceled=False,
        yext_suppressed=False,
        address1=order.address.address,
        address2=order.address.address2,
        city=order.address.city,
        state=order.address.state,
        zip=order.address.postalCode,
        country=order.address.countryCode or "US",
        show_address=order.address.visible,
        latitude=order.geoData.displayLatitude,
        longitude=order.geoData.displayLongitude,
        yext=yext_data,
        homepage_url=yext_data.website_url,
        date_created=datetime.now(),
        date_updated=datetime.now(),
        date_deleted=None,
        hours_text=order.hoursText.display if order.hoursText else None,
        slug=generate_local_slug(db, store)
    )

    db.add(store)
    db.commit()

    return {
        "status": "LIVE",
        "id": store.id,  # This is the store ID (8coupons ID)
        "url": store.url
    }


@app.put("/powerlistings/{listing_id}")
def yext_listing_order(listing_id: int, data: yext.YextListingUpdate, db: Session = Depends(get_db)):
    store = db.query(LocalStore).filter(LocalStore.id == listing_id).one()

    yext_data = store.yext or yext.YextData()

    updated_yext_data = yext.YextData(
        images=data.images or yext_data.images,
        categories=data.categories or yext_data.categories,
        payment_options=data.paymentOptions or yext_data.payment_options,
        emails=data.emails or yext_data.emails,
        videos=data.videos or yext_data.videos,
        special_offer=data.specialOffer or yext_data.special_offer,
        urls=data.urls or yext_data.urls,
        phones=data.phones or yext_data.phones
    )

    store.name = data.name or store.name
    store.description = data.description or store.description
    store.yext_id = data.yextId or store.yext_id

    if data.address:
        store.address1 = data.address.address
        store.address2 = data.address.address2
        store.city = data.address.city
        store.state = data.address.state
        store.zip = data.address.postalCode
        store.country = data.address.countryCode or "US"
        store.show_address = data.address.visible

    if data.geoData:
        store.latitude = data.geoData.displayLatitude
        store.longitude = data.geoData.displayLongitude

    store.yext = updated_yext_data
    store.phone = updated_yext_data.main_phone
    store.homepage_url = updated_yext_data.website_url or store.homepage_url
    store.date_updated = datetime.now()
    store.date_deleted = None

    if data.hoursText:
        store.hours_text = data.hoursText.display

    store.slug = generate_local_slug(db, store)

    db.add(store)
    db.commit()

    return {
        "status": "LIVE",
        "id": store.id,
        "url": store.url
    }


@app.delete("/powerlistings/{listing_id}")
def delete_listing(listing_id: int, db: Session = Depends(get_db)):
    store = db.query(LocalStore).filter(LocalStore.id == listing_id).one()
    store.date_deleted = datetime.now()
    store.yext_canceled = True
    db.commit()

    return {
        "ok": True
    }


@app.post("/powerlistings/suppress")
def suppress_listing(payload: yext.YextListingSuppress, db: Session = Depends(get_db)):
    store = db.query(LocalStore).filter(LocalStore.id == payload.listingId).one()
    store.date_deleted = datetime.now() if payload.suppress else None
    store.yext_suppressed = payload.suppress
    store.canonical_id = payload.canonicalListingId if payload.suppress else None
    db.commit()

    return {
        "ok": True
    }


def get_store_details(store: models.LocalStore):
    return {
        "id": store.id,
        "status": store.status,
        "name": store.name,
        "address": store.address1,
        "address2": store.address2,
        "city": store.city,
        "state": store.state,
        "zip": store.zip,
        "countryCode": store.country,
        "latitude": store.latitude,
        "longitude": store.longitude,
        "phone": store.phone,
        "url": store.url,
        "categories": store.categories,
        "websiteUrl": store.homepage_url,
        "description": store.description,
        "type": "Location"
    }


@app.get("/details")
def details_listing(storeID: str, db: Session = Depends(get_db)):
    store = models.LocalStore.get_by(db, id=storeID, include_deleted=True)
    return get_store_details(store)


@app.get("/search")
def details_listing(phone=None, country_code=None, name=None, latlng: str = None, db: Session = Depends(get_db)):
    stores = []
    filters = []
    if phone:
        filters.append(LocalStore.phone == phone)

    if country_code:
        filters.append(LocalStore.country == country_code)

    if name:
        filters.append(LocalStore.name.startswith(name))

    if latlng:
        lat, lng = latlng.split(",")
        filters.append(LocalStore.within_radius(float(lat), float(lng), 10))

    if filters:
        stores = db.query(LocalStore).filter(*filters).limit(30).all()

    return [get_store_details(store) for store in stores]


@app.get("/health_check")
def health_check(request: Request):
    headers = request.headers if request.query_params.get("_debug") else None
    return {
        "status": "ok",
        "headers": headers
    }
