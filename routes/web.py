from fastapi import FastAPI, Request, Depends, HTTPException, APIRouter
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from app.db import SessionLocal, get_db
from app import models
from fastapi.templating import Jinja2Templates
from app.settings import settings
from urllib.parse import unquote, urlparse
from datetime import datetime
from app.geo import GeoLocation, get_geo
import hashlib
from fastapi.responses import RedirectResponse


CSS_HASH = hashlib.md5(open('static/main.css', 'rb').read()).hexdigest()


app = FastAPI(docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=settings.template_dir)


def get_page(db: Session, path: str):
    return db.query(models.Page).filter(models.Page.path == path).one()


def query_city(db: Session, city_slug: str = None):
    q = db.query(models.City)
    if city_slug:
        q = q.filter(models.City.slug == city_slug)

    return q


def render_string(template_string, context: dict, throw_errors=False):
    try:
        template = templates.env.from_string(template_string)
        return template.render(context)
    except Exception as e:
        if throw_errors:
            raise e
        return template_string


def render_page(page: models.Page, context: dict, status_code=200, template_name="page.html"):
    if page.title:
        page.title = render_string(page.title, context)

    if page.content:
        page.content = render_string(page.content, context)

    context['page'] = page

    return templates.TemplateResponse(template_name, context, status_code=status_code)


def get_context(request: Request, db: Session = None, city: models.City = None):
    return {
        "now": datetime.now(),
        "request": request,
        "request_url": urlparse(str(request.url)),
        "cities": db.query(models.City) if db else None,
        "geo": get_geo(request, city=city),
        "css_hash": CSS_HASH if not settings.debug else str(datetime.now())
    }


@app.exception_handler(StarletteHTTPException)
@app.exception_handler(NoResultFound)
@app.exception_handler(RuntimeError)
def http_exception_handler(request, exc):
    return templates.TemplateResponse("404.html", get_context(request), status_code=404)


@app.exception_handler(Exception)
def http_exception_handler(request, exc: Exception):
    return templates.TemplateResponse("500.html", get_context(request), status_code=500)


@app.get("/stores/local/{slug}")
def get_local_store(request: Request, slug: str, db: Session = Depends(get_db)):
    store = db.query(models.LocalStore).filter(models.LocalStore.slug == slug).first()

    if not store:
        return RedirectResponse(url="/", status_code=302)

    page = get_page(db, "/stores/local/{slug}")
    context = get_context(request)
    context['store'] = store

    return render_page(page, context, template_name="pages/store_listing.html")


@app.get("/discounts/{slug}")
def get_discounts(request: Request, slug: str, db: Session = Depends(get_db)):
    return get_local_store(request, slug, db)


@app.get("/stores/online/{slug}")
def get_online_store(request: Request, slug: str, db: Session = Depends(get_db)):
    store = db.query(models.OnlineStore).filter(models.OnlineStore.slug == slug).first()

    if not store:
        return RedirectResponse(url="/", status_code=302)

    page = get_page(db, "/stores/online/{slug}")
    context = get_context(request)
    context['store'] = store

    return render_page(page, context, template_name="pages/store_listing.html")


@app.get("/stores/chain/{slug}")
def get_chain_store(request: Request, slug: str, db: Session = Depends(get_db)):
    store = db.query(models.Chain).filter(models.Chain.slug == slug).first()

    if not store:
        return RedirectResponse(url="/", status_code=302)

    page = get_page(db, "/stores/chain/{slug}")
    context = get_context(request)
    context['store'] = store

    return render_page(page, context, template_name="pages/store_listing.html")


@app.get("/coupons/{chain_name}")
def get_online_store(request: Request, chain_name: str, db: Session = Depends(get_db)):
    page = get_page(db, "/stores/chain/{slug}")
    context = get_context(request)
    context['store'] = db.query(models.Chain).filter(models.Chain.name == chain_name.replace("_", " ")).one()

    return render_page(page, context, template_name="pages/store_listing.html")


@app.get("/city/{city_slug}")
def get_city(request: Request, city_slug: str, db: Session = Depends(get_db)):
    city_slug = city_slug.replace("_", "-")
    city = db.query(models.City).filter(models.City.slug == city_slug).one()
    page = get_page(db, "/city/{slug}")
    context = get_context(request, city=city)
    context["city"] = city

    return render_page(page, context, template_name="pages/home.html")


@app.get("/cities/{state_code}")
def get_city(request: Request, state_code: str, db: Session = Depends(get_db)):
    cities = db.query(models.City).filter(models.City.state_code == state_code).all()

    if len(cities) == 0:
        raise HTTPException(status_code=404)

    page = get_page(db, "/cities/{state_code}")
    context = get_context(request)
    context["state_cities"] = cities
    context["state"] = cities[0].state

    return render_page(page, context)


@app.get("/deals/{category_slug}")
def get_deals(request: Request, category_slug: str, db: Session = Depends(get_db), city=None):
    page = get_page(db, f"/deals/{category_slug}")
    context = get_context(request, city=city)

    return render_page(page, context, template_name="pages/deals.html")


@app.get("/deals/{category_slug}/{city_slug}")
def get_deals_city(request: Request, category_slug: str, city_slug: str, db: Session = Depends(get_db)):
    city = query_city(db, city_slug).one()
    return get_deals(request, category_slug, db, city=city)


@app.get("/coupons")
def get_coupons(request: Request, db: Session = Depends(get_db)):
    page = get_page(db, f"/coupons")
    context = get_context(request)

    return render_page(page, context, template_name="pages/deals.html")


@app.get("/events")
def get_events(request: Request, db: Session = Depends(get_db), city=None):
    page = get_page(db, f"/events")
    context = get_context(request, city=city)

    return render_page(page, context, template_name="pages/deals.html")


@app.get("/events/{city_slug}")
def get_events_city(request: Request, city_slug: str, db: Session = Depends(get_db)):
    city = query_city(db, city_slug).one()
    return get_events(request, db, city=city)


@app.get("/holidays/{slug}")
def get_holidays(request: Request, slug: str, db: Session = Depends(get_db)):
    page = get_page(db, f"/holidays/{slug}")
    context = get_context(request)

    return render_page(page, context, template_name="pages/deals.html")


@app.get("/search")
def get_index(request: Request, db: Session = Depends(get_db)):
    page = get_page(db, "/")
    context = get_context(request)
    context['keywords'] = request.query_params.get("keywords", "")

    return render_page(page, context, template_name="pages/search.html")


@app.get("/api/terms")
def get_index(request: Request, db: Session = Depends(get_db)):
    page = get_page(db, "/terms-and-conditions")
    context = get_context(request)

    return render_page(page, context)


@app.get("/")
def get_index(request: Request, db: Session = Depends(get_db)):
    page = get_page(db, "/")
    context = get_context(request)

    return render_page(page, context, template_name="pages/home.html")


@app.get("/partner/{partner}")
def get_partner(request: Request, partner: str, db: Session = Depends(get_db)):
    page = get_page(db, "/update-business-listing")
    context = get_context(request)
    if partner == "localsaver":
        context['redirect_url'] = "http://ls.localsaver.com/8coupons/"
    elif partner == "yext":
        context['redirect_url'] = "https://www.yext.com/pl/8coupons-listing/index.html?ref=253426"
    else:
        raise HTTPException(404)

    return render_page(page, context, template_name="pages/redirect.html")


@app.get("/{full_path:path}")
def catch_all_pages(full_path: str, request: Request, db: Session = Depends(get_db)):
    city = db.query(models.City).filter(models.City.slug == full_path).first()
    template_name = "page.html"
    context = get_context(request, db, city=city)
    context["city"] = city

    if city:
        template_name = "pages/home.html"
        full_path = ""

    page = db.query(models.Page).filter(models.Page.path == "/" + full_path).first()

    if not page:
        return FileResponse(f"resources/public/{full_path}")

    return render_page(page, context, template_name=template_name)
