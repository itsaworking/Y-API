from pydantic import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    debug = False
    template_loader = "local"
    template_dir = "resources/templates"
    database_url: str
    app_url = "http://localhost:8000"

    class Config:
        env_file = ".env"


settings = Settings()
