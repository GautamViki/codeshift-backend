import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from app.aws_configs.secret_manager import get_aws_secret

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
ENV = os.getenv("ENVIRONMENT", "development")  # default to dev locally

# Load environment file based on ENVIRONMENT
env_file = BASE_DIR / f".env.{ENV}"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv(BASE_DIR / ".env")  # fallback

class Config:
    ENVIRONMENT = ENV
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or get_aws_secret("transpiler_ai_key")


config = Config()