"""Where Quorum runs, which Gemini sits in which seat, and what the desk may do alone."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    """Read KEY=value lines from .env without overriding the real environment."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}


PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT") or ""
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def gemini_mode() -> str:
    """enterprise (Gemini Enterprise Agent Platform), api-key (AI Studio), or none."""
    if _flag("GOOGLE_GENAI_USE_ENTERPRISE") or _flag("GOOGLE_GENAI_USE_VERTEXAI"):
        return "enterprise" if PROJECT else "none"
    if API_KEY:
        return "api-key"
    return "none"


def configure_gemini() -> str:
    """Point google-genai at the right backend before any agent is built."""
    mode = gemini_mode()
    if mode == "enterprise":
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    elif mode == "api-key":
        os.environ.setdefault("GOOGLE_API_KEY", API_KEY)
        os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "false"
    return mode


# Seats that gather and argue run on Flash. The magistrate runs on the strongest
# model the backend offers; the AI Studio free tier does not serve Argon.
SEAT_MODEL = os.environ.get("QUORUM_MODEL", "gemini-3.8-flash")
JUDGE_MODEL = os.environ.get(
    "QUORUM_JUDGE_MODEL",
    "gemini-4-argon" if gemini_mode() == "enterprise" else SEAT_MODEL,
)
FAST_MODEL = os.environ.get("QUORUM_FAST_MODEL", "gemini-3.5-flash-lite")
# Where a seat goes when its model is out of quota or down, in order.
FALLBACK_MODELS = [
    name.strip()
    for name in os.environ.get("QUORUM_FALLBACK_MODELS", "gemini-3.6-flash,gemini-3.5-flash-lite").split(",")
    if name.strip()
]
THINKING = os.environ.get("QUORUM_THINKING", "on").lower() not in {"0", "off", "false", "no"}
SEAT_TIMEOUT_S = float(os.environ.get("QUORUM_SEAT_TIMEOUT", "75"))

BQ_DATASET = os.environ.get("QUORUM_BQ_DATASET", "quorum_mart")
BQ_LOCATION = os.environ.get("QUORUM_BQ_LOCATION", "US")
USE_BIGQUERY = _flag("QUORUM_USE_BIGQUERY")
USE_FIRESTORE = os.environ.get("QUORUM_USE_FIRESTORE", "auto")

# A public demo URL spends real tokens. These caps keep a stray script from
# convening a thousand hearings.
MAX_CONCURRENT_HEARINGS = int(os.environ.get("QUORUM_MAX_HEARINGS", "4"))
HEARINGS_PER_IP_PER_MINUTE = int(os.environ.get("QUORUM_IP_RATE", "6"))
# The per-IP limit trusts X-Forwarded-For, which a client can forge; this one it cannot.
HEARINGS_PER_MINUTE = int(os.environ.get("QUORUM_GLOBAL_RATE", "30"))
UPLOADS_PER_FILE = int(os.environ.get("QUORUM_UPLOADS_PER_FILE", "5"))
STREAM_MAX_PER_BURST = int(os.environ.get("QUORUM_STREAM_MAX", "160"))
