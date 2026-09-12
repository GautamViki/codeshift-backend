import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV = os.getenv("ENVIRONMENT", "development")  # default to dev locally

env_file = BASE_DIR / f".env.{ENV}"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv(BASE_DIR / ".env")  # fallback


class Config:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    ENVIRONMENT = ENV


config = Config()