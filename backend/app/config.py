from pathlib import Path
import os

COCO_DIR = Path(os.getenv("COCO_DIR", str(Path.home() / ".coco")))
HUB_DIR = Path(os.getenv("HUB_DIR", str(Path.home() / ".hub")))

HUB_DB_PATH = HUB_DIR / "hub.db"
PLATFORM_DB_PATH = COCO_DIR / "platform.db"
BRAIN_JSON_PATH = COCO_DIR / "brain.json"
QUEUE_JSON_PATH = COCO_DIR / "queue.json"
CONFIG_JSON_PATH = COCO_DIR / "config.json"
EVENTS_JSONL_PATH = COCO_DIR / "events.jsonl"
SESSIONS_DIR = COCO_DIR / "sessions"
LOGS_DIR = COCO_DIR / "logs"

PLATFORM_PORT = int(os.getenv("PLATFORM_PORT", "8000"))
MAX_CONCURRENT_AGENTS = int(os.getenv("MAX_CONCURRENT_AGENTS", "3"))
AGENT_TIMEOUT_MINUTES = int(os.getenv("AGENT_TIMEOUT_MINUTES", "30"))
CHAT_TIMEOUT_MINUTES = int(os.getenv("CHAT_TIMEOUT_MINUTES", "5"))
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
USE_AGENT_SDK = os.getenv("USE_AGENT_SDK", "false").lower() in ("true", "1", "yes")

# Database URL — defaults to SQLite (platform.db), supports PostgreSQL for cloud
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PLATFORM_DB_PATH}")

# Security
COCO_AUTH_TOKEN = os.getenv("COCO_AUTH_TOKEN", "")
COCO_CORS_ORIGINS = os.getenv("COCO_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
COCO_RATE_LIMIT = os.getenv("COCO_RATE_LIMIT", "true").lower() in ("true", "1", "yes")
COCO_RATE_LIMIT_RPM = int(os.getenv("COCO_RATE_LIMIT_RPM", "120"))
