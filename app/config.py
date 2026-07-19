import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _mysql_uri() -> str:
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "app_review_insights")
    return (
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
        f"?charset=utf8mb4"
    )


def _database_uri() -> str:
    """Primary: MySQL 8. Optional: DATABASE_URL or USE_SQLITE=1 for local smoke tests."""
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    if os.getenv("USE_SQLITE", "0") == "1":
        db_path = BASE_DIR / "data" / "local_dev.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path.as_posix()}"
    return _mysql_uri()


def _normalize_openai_base_url(url: str) -> str:
    """Accept either .../v1 or full .../v1/chat/completions."""
    url = (url or "").strip().rstrip("/")
    if url.endswith("/chat/completions"):
        url = url[: -len("/chat/completions")]
    return url or "https://api.openai.com/v1"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 28000,
    }

    AI_ENABLED = os.getenv("AI_ENABLED", "1") == "1"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = _normalize_openai_base_url(
        os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
    OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "3000"))

    ALLOW_CACHED_FALLBACK = os.getenv("ALLOW_CACHED_FALLBACK", "1") == "1"
    MAX_REVIEW_PAGES = int(os.getenv("MAX_REVIEW_PAGES", "10"))

    DATA_DIR = BASE_DIR / "data"
    CACHE_DIR = DATA_DIR / "cached_analysis"
    SAMPLE_REVIEWS_PATH = DATA_DIR / "sample_reviews.json"
