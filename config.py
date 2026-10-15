"""
config.py — MediaMaster AI ki saari settings ek hi jagah.

Secrets (token / keys) SIRF environment variables se aate hain.
Code ya GitHub me kabhi secrets mat likho.
"""
from __future__ import annotations

import os
import re


def _str(name: str, default: str = "") -> str:
    """Environment variable ko string me padho (extra spaces hata kar)."""
    return os.environ.get(name, default).strip()


def _int(name: str, default: int) -> int:
    """Environment variable ko int me padho; galat value par default use karo."""
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _id_set(name: str) -> frozenset:
    """Comma separated Telegram IDs ko set me badlo (jaise '123,456')."""
    out = set()
    for part in os.environ.get(name, "").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.add(int(part))
    return frozenset(out)


# ---------------------------------------------------------------------------
# Secrets (REQUIRED)
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = _str("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = _str("GEMINI_API_KEY")
SUPABASE_URL = _str("SUPABASE_URL")
SUPABASE_KEY = _str("SUPABASE_KEY")  # service_role / secret key (anon key NAHI)

# ---------------------------------------------------------------------------
# AI model
# ---------------------------------------------------------------------------
GEMINI_MODEL = _str("GEMINI_MODEL", "gemini-2.5-flash")
# Gemini video ko process karne me kitne second tak wait karna hai
GEMINI_PROCESS_TIMEOUT = _int("GEMINI_PROCESS_TIMEOUT", 180)

# ---------------------------------------------------------------------------
# Tasks / links
# ---------------------------------------------------------------------------
CHANNEL_USERNAME = _str("CHANNEL_USERNAME", "@MediaAIOfficial")
if not CHANNEL_USERNAME.startswith("@"):
    CHANNEL_USERNAME = "@" + CHANNEL_USERNAME
CHANNEL_URL = f"https://t.me/{CHANNEL_USERNAME[1:]}"

YOUTUBE_URL = _str("YOUTUBE_URL", "https://youtube.com/@mediamasterai-s?si=B6OVbfSe6YYx6S4B")
SPONSOR_URL = _str("SPONSOR_URL", "https://asiafilm.org/4/3bef082467f69324d6f8ce5cd326ded5")

# Task button dabane ke kam se kam itne second baad hi "Done" chalega (friction)
YT_MIN_SECONDS = _int("YT_MIN_SECONDS", 10)
SPONSOR_MIN_SECONDS = _int("SPONSOR_MIN_SECONDS", 15)
BONUS_MIN_SECONDS = _int("BONUS_MIN_SECONDS", 15)

# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------
START_CREDITS = _int("START_CREDITS", 3)        # 3 tasks poore hone par
REFERRAL_BONUS = _int("REFERRAL_BONUS", 2)      # referrer ko, jab dost 3 tasks poore kare
BONUS_CREDITS = _int("BONUS_CREDITS", 1)        # sponsor link ek baar dekhne par
BONUS_DAILY_CAP = _int("BONUS_DAILY_CAP", 3)    # roz maximum itni baar bonus

# ---------------------------------------------------------------------------
# Limits / runtime
# ---------------------------------------------------------------------------
# Telegram Bot API 20 MB se badi file download nahi karne deta
MAX_VIDEO_MB = min(_int("MAX_VIDEO_MB", 20), 20)
# Ek saath kitni videos analyse hongi (free host par RAM bachane ke liye)
MAX_CONCURRENT_ANALYSES = max(_int("MAX_CONCURRENT_ANALYSES", 2), 1)
ADMIN_IDS = _id_set("ADMIN_IDS")
PORT = _int("PORT", 8000)

# Optional webhook mode (Koyeb free instance ko sone ke baad jagane ke liye)
WEBHOOK_URL = _str("WEBHOOK_URL")        # jaise https://my-app.koyeb.app
WEBHOOK_SECRET = _str("WEBHOOK_SECRET")  # 16+ chars: A-Z a-z 0-9 _ -


def missing_env() -> list:
    """Jo required environment variables set nahi hain unki list."""
    required = {
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
    }
    return [name for name, value in required.items() if not value]


def webhook_config_error() -> str:
    """Webhook mode ki settings galat ho to error text, warna khali string."""
    if not WEBHOOK_URL:
        return ""
    if not WEBHOOK_URL.startswith("https://"):
        return "WEBHOOK_URL https:// se shuru hona chahiye."
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", WEBHOOK_SECRET):
        return "WEBHOOK_SECRET 16-256 characters ka hona chahiye (sirf A-Z a-z 0-9 _ -)."
    return ""
