"""
gemini_service.py — video ko Gemini 2.5 Flash se analyse karna.

Flow: video upload (Gemini File API) -> ACTIVE hone tak wait -> report generate
      -> remote file DELETE (hamesha, error aaye tab bhi).
Local temp file delete karna handlers.py ka kaam hai (download wahi karta hai).
"""
from __future__ import annotations

import logging
import threading
import time

from google import genai
from google.genai import types

import config

log = logging.getLogger(__name__)


class AnalysisError(RuntimeError):
    """Video analysis fail hone par raise hota hai."""


ANALYSIS_PROMPT = """
Tum ek expert social media growth strategist ho. Is video ke VISUALS aur AUDIO dono ko dhyan se dekho aur suno.
Phir Hinglish (Hindi ko English alphabets me, simple language) me ek structured, copy-paste-ready viral report banao.

STRICT RULES:
- Sirf plain text do. Markdown symbols jaise **, #, ` bilkul use mat karo.
- Emojis use karo.
- Neeche diye format ko EXACTLY follow karo. Har section ka heading same rakho.
- Video me jo asli content hai usi par report banao (kuch mann se mat gadho).

🎬 VIDEO SUMMARY
(2 line me video kis baare me hai)

📸 INSTAGRAM REELS
Viral Hook Title: ...
Caption: ... (engaging, end me CTA ke saath)
Trending Hashtags: (15-20 hashtags, ek hi line me)
Best Quality Upload Settings: (1080x1920, 9:16, 30fps, MP4 H.264, "Upload at highest quality" ON, cover frame ka tip)

📘 FACEBOOK PAGE / REELS
Title: ...
Detailed Description: ... (3-5 lines)
Public Settings: (Public, Reels sharing ON, remix allowed jaisi settings)

▶️ YOUTUBE SHORTS
High-SEO Title: ... (60 characters se kam)
Description: ... (2-3 lines + #Shorts)
Keywords: (comma se alag kiye hue 10-15 keywords)
Settings: (Public, "Not made for kids", 9:16, 60 sec se kam)

🌐 OTHER APPS
Snapchat Caption: ...
Moj Caption: ...
LinkedIn Caption: ... (professional tone)
Tags: ...

⏰ BEST POSTING TIME
(Aaj ke liye IST me 3 time slots, har slot ke saath chhota sa reason)

💡 PRO TIP
(Video ko aur behtar banane ka 1 line suggestion)
""".strip()

_client = None
_client_lock = threading.Lock()


def _get_client() -> genai.Client:
    """Gemini client ek baar banao (lazy) aur reuse karo."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = genai.Client(
                    api_key=config.GEMINI_API_KEY,
                    http_options=types.HttpOptions(timeout=300_000),  # milliseconds
                )
    return _client


def _state_name(remote_file) -> str:
    """File ki state ka naam (PROCESSING / ACTIVE / FAILED). None ko ACTIVE maano."""
    state = getattr(remote_file, "state", None)
    if state is None:
        return "ACTIVE"
    return getattr(state, "name", str(state))


def analyze_video_blocking(path: str, mime_type: str) -> str:
    """
    BLOCKING function — asyncio.to_thread ke andar chalao.

    path       : local video file ka path
    mime_type  : jaise 'video/mp4'
    return     : Hinglish report (plain text)
    raise      : AnalysisError (ya SDK ka exception) fail hone par
    """
    client = _get_client()
    remote = None
    try:
        remote = client.files.upload(file=path, config=types.UploadFileConfig(mime_type=mime_type))

        # Video asynchronously process hoti hai — ACTIVE hone tak poll karo.
        waited = 0
        while _state_name(remote) == "PROCESSING":
            if waited >= config.GEMINI_PROCESS_TIMEOUT:
                raise AnalysisError("Gemini video processing timeout")
            time.sleep(3)
            waited += 3
            remote = client.files.get(name=remote.name)

        if _state_name(remote) != "ACTIVE":
            raise AnalysisError(f"Gemini file state: {_state_name(remote)}")

        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[remote, ANALYSIS_PROMPT],
        )
        text = (response.text or "").strip()
        if not text:
            raise AnalysisError("Gemini ne khali response diya (content block ho sakta hai)")
        return text
    finally:
        # Remote file hamesha delete karo (storage + privacy).
        if remote is not None and getattr(remote, "name", None):
            try:
                client.files.delete(name=remote.name)
            except Exception as exc:  # noqa: BLE001
                log.warning("Gemini remote file delete nahi hui: %s", exc)
