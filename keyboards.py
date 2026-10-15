"""
keyboards.py — saare inline keyboards (button labels Hinglish me).

callback_data ke naam:
  noop            -> kuch nahi (sirf toast)
  tasks / verify  -> tasks screen refresh / verify
  open:<key>      -> task khola (key = yt | sponsor | bonus)
  done:<key>      -> task done
  refer           -> referral link bhejo
"""
from __future__ import annotations

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

import config as C


def tasks_keyboard(tg_ok: bool, yt_ok: bool, sp_ok: bool) -> Markup:
    rows = []
    if tg_ok:
        rows.append([Btn("✅ Task 1: Telegram Channel Joined", callback_data="noop")])
    else:
        rows.append([Btn("📢 Task 1: Telegram Channel Join Karo", url=C.CHANNEL_URL)])
    rows.append(
        [Btn("✅ Task 2: YouTube Subscribed", callback_data="noop")]
        if yt_ok
        else [Btn("▶️ Task 2: YouTube Subscribe Karo", callback_data="open:yt")]
    )
    rows.append(
        [Btn("✅ Task 3: Sponsor Link Dekha", callback_data="noop")]
        if sp_ok
        else [Btn("🎁 Task 3: Sponsor Link Dekho", callback_data="open:sponsor")]
    )
    rows.append([Btn("🔄 Verify Karo", callback_data="verify")])
    return Markup(rows)


def rejoin_keyboard() -> Markup:
    """Channel leave karne waalon ke liye."""
    return Markup(
        [
            [Btn("📢 Channel Join Karo", url=C.CHANNEL_URL)],
            [Btn("🔄 Verify Karo", callback_data="verify")],
        ]
    )


def task_open_keyboard(key: str) -> Markup:
    """Task 2 (yt) / Task 3 (sponsor) ka instruction screen."""
    if key == "yt":
        link = Btn("▶️ YouTube Channel Kholo", url=C.YOUTUBE_URL)
        done = Btn("✅ Maine Subscribe Kar Liya", callback_data="done:yt")
    else:
        link = Btn("🎁 Sponsor Link Kholo", url=C.SPONSOR_URL)
        done = Btn("✅ Maine Dekh Liya", callback_data="done:sponsor")
    return Markup([[link], [done], [Btn("⬅️ Wapas", callback_data="tasks")]])


def bonus_open_keyboard() -> Markup:
    return Markup(
        [
            [Btn("🎁 Sponsor Link Kholo", url=C.SPONSOR_URL)],
            [Btn("✅ Maine Dekh Liya", callback_data="done:bonus")],
        ]
    )


def bonus_keyboard() -> Markup:
    """/bonus ka pehla screen."""
    return Markup([[Btn("🎁 Sponsor Link Se Credit Kamao", callback_data="open:bonus")]])


def no_credits_keyboard() -> Markup:
    """Credits 0 hone par."""
    return Markup(
        [
            [Btn("🎁 Sponsor Link Se Credit Kamao", callback_data="open:bonus")],
            [Btn("🤝 Dosto Ko Refer Karo", callback_data="refer")],
        ]
    )
