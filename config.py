"""Application configuration loaded from environment variables."""
import os

from dotenv import load_dotenv

load_dotenv()

# Absolute path to the project root (directory containing this file).
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))

# Secret used to sign session cookies. MUST be overridden in production.
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")

# SQLAlchemy database URL. Defaults to a local SQLite file in the project root.
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./survey_app.db")
