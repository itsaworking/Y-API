from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import NoResultFound
from fastapi.staticfiles import StaticFiles
from app.routes import web, api_yext
import anyio

API_PREFIX = "/api"
THREADS_LIMIT = 100


class CustomStaticFiles(StaticFiles):
    def file_response(
        self,
        full_path,
        stat_result,
        scope,
        status_code: int = 200,
    ):
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers['cache-control'] = "public, max-age=86400"
        return response


app = FastAPI(docs_url=None, redoc_url=None)

app.mount("/static", CustomStaticFiles(directory="static"), name="static")
app.mount("/api/yext", api_yext.app, name="api_yext")
app.mount("/", web.app, name="web")


# @app.on_event("startup")
# def startup():
#     limiter = anyio.to_thread.current_default_thread_limiter()
#     limiter.total_tokens = THREADS_LIMIT
