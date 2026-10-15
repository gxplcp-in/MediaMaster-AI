"""
handlers.py — saare Telegram handlers (commands, buttons, video).

Flow:
  /start -> gate() -> (3 tasks pending?) tasks screen  |  (sab ok?) welcome
  video  -> gate() -> credit kaato -> download -> Gemini -> report -> temp file delete
            (fail hua to credit refund)
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from telegram import BotCommand, Update
from telegram.constants import ChatMemberStatus
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config as C
import keyboards as K
import messages as M
from database import db
from gemini_service import analyze_video_blocking

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# Ek saath ek hi user ki ek hi video process ho (spam rokne ke liye)
_BUSY_USERS: set = set()
# Poore bot me ek saath kitni videos analyse hongi (RAM bachane ke liye)
_ANALYSIS_SEMAPHORE = asyncio.Semaphore(C.MAX_CONCURRENT_ANALYSES)

# Telegram membership ka chhota cache (sirf "member hai" wale result, 60 second)
_MEMBER_OK_UNTIL: dict = {}
_MEMBER_TTL = 60.0
# Admin ko "bot channel ka admin nahi hai" alert baar-baar na jaye
_last_admin_alert = 0.0


# ===========================================================================
# Helpers
# ===========================================================================
def split_text(text: str, limit: int = 4000) -> list:
    """Lambe text ko Telegram ki 4096 character limit ke andar tukdo me todo."""
    chunks: list = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:  # ek hi line bahut lambi ho to hard split
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current.strip():
        chunks.append(current)
    return chunks


def clean_report(text: str) -> str:
    """Gemini kabhi markdown bhej de to usse plain text bana do."""
    lines = []
    for line in text.replace("**", "").replace("`", "").splitlines():
        line = re.sub(r"^\s*#{1,6}\s+", "", line)  # markdown heading ("## Title"); #hashtag safe rehta hai
        stripped = line.lstrip()
        if stripped.startswith("* "):
            line = line[: len(line) - len(stripped)] + "• " + stripped[2:]
        lines.append(line)
    return "\n".join(lines).strip()


def claims_today(row: dict) -> int:
    """Aaj (IST) kitne sponsor bonus claim ho chuke hain."""
    today = datetime.now(IST).date().isoformat()
    if str(row.get("bonus_day") or "") == today:
        return int(row.get("bonus_claims") or 0)
    return 0


def _is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in C.ADMIN_IDS)


async def _safe_edit(query, text: str, markup=None) -> None:
    """Message edit karo; 'not modified' ignore, edit na ho sake to naya message bhejo."""
    try:
        await query.edit_message_text(text, reply_markup=markup, disable_web_page_preview=True)
    except BadRequest as exc:
        if "not modified" in str(exc).lower():
            return
        log.info("Edit nahi hua (%s), naya message bhej raha hoon", exc)
        if query.message:
            await query.message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)


async def _alert_admins(bot, text: str) -> None:
    """Admins ko DM (max 1 ghante me ek baar)."""
    global _last_admin_alert
    if time.monotonic() - _last_admin_alert < 3600 and _last_admin_alert:
        return
    _last_admin_alert = time.monotonic()
    for admin_id in C.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except TelegramError:
            pass


# ===========================================================================
# Telegram channel membership (Task 1) — getChatMember
# ===========================================================================
async def is_member(bot, user_id: int, force: bool = False) -> Optional[bool]:
    """
    True  = channel ka member hai
    False = member nahi hai
    None  = check hi nahi ho paya (bot admin nahi / network issue)
    """
    now = time.monotonic()
    if not force and _MEMBER_OK_UNTIL.get(user_id, 0.0) > now:
        return True
    try:
        member = await bot.get_chat_member(chat_id=C.CHANNEL_USERNAME, user_id=user_id)
    except (BadRequest, Forbidden) as exc:
        log.error("getChatMember fail (bot channel ka admin hai?): %s", exc)
        await _alert_admins(
            bot,
            f"⚠️ Membership check fail ho raha hai: {exc}\n"
            f"Bot ko {C.CHANNEL_USERNAME} ka Admin banao.",
        )
        return None
    except TelegramError as exc:
        log.warning("getChatMember network error: %s", exc)
        return None

    ok = member.status in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    ) or (member.status == ChatMemberStatus.RESTRICTED and bool(getattr(member, "is_member", False)))

    if ok:
        if len(_MEMBER_OK_UNTIL) > 10000:  # memory leak se bachao
            for uid in [u for u, t in _MEMBER_OK_UNTIL.items() if t <= now]:
                _MEMBER_OK_UNTIL.pop(uid, None)
        _MEMBER_OK_UNTIL[user_id] = now + _MEMBER_TTL
    else:
        _MEMBER_OK_UNTIL.pop(user_id, None)
    return ok


# ===========================================================================
# Users + tasks + gate
# ===========================================================================
async def _ensure_user(tg_user) -> dict:
    """User row lao; na mile to bana do."""
    row = await db.get_user(tg_user.id)
    if row is None:
        await db.upsert_user(tg_user.id, tg_user.username, tg_user.first_name, None)
        row = await db.get_user(tg_user.id)
    if row is None:
        raise RuntimeError("User row ban nahi paayi")
    return row


def _tasks_view(row: dict, member: Optional[bool]):
    """Tasks screen ka (text, keyboard) — user ki halat ke hisaab se."""
    if row["tasks_done"]:
        if member:
            return M.TASKS_ALL_DONE, None
        return M.CHANNEL_LEFT, K.rejoin_keyboard()
    tg_ok = bool(member)
    return (
        M.tasks_screen(tg_ok, row["yt_done"], row["sponsor_done"], tg_error=member is None),
        K.tasks_keyboard(tg_ok, row["yt_done"], row["sponsor_done"]),
    )


async def _notify_referrer(context: ContextTypes.DEFAULT_TYPE, referrer: Optional[int]) -> None:
    if not referrer:
        return
    try:
        await context.bot.send_message(referrer, M.referral_reward())
    except TelegramError:
        pass  # referrer ne bot block kar diya ho sakta hai


async def _maybe_finalize(context: ContextTypes.DEFAULT_TYPE, row: dict, member: Optional[bool]) -> bool:
    """Teeno tasks poore hain to EK baar credits do. True = abhi unlock hua."""
    if not (member and not row["tasks_done"] and row["yt_done"] and row["sponsor_done"]):
        return False
    res = await db.finalize_tasks(row["user_id"], C.START_CREDITS, C.REFERRAL_BONUS)
    if not res.get("granted"):
        return False
    await _notify_referrer(context, res.get("referrer"))
    return True


async def gate(update: Update, context: ContextTypes.DEFAULT_TYPE, row: Optional[dict] = None) -> Optional[dict]:
    """
    Har feature ke upar lagta hai. User row return karta hai agar access hai,
    warna user ko sahi message bhej kar None return karta hai.
    """
    tg_user = update.effective_user
    msg = update.effective_message
    if tg_user is None or msg is None:
        return None
    if row is None:
        row = await _ensure_user(tg_user)

    if row.get("is_banned"):
        await msg.reply_text(M.BANNED)
        return None

    member = await is_member(context.bot, tg_user.id)
    if member is None:
        await msg.reply_text(M.MEMBERSHIP_CHECK_FAILED)
        return None

    if await _maybe_finalize(context, row, member):
        await msg.reply_text(M.unlocked())
        return await db.get_user(tg_user.id)

    if not row["tasks_done"] or not member:
        text, markup = _tasks_view(row, member)
        await msg.reply_text(text, reply_markup=markup, disable_web_page_preview=True)
        return None
    return row


async def _refresh_tasks_message(query, context: ContextTypes.DEFAULT_TYPE, uid: int) -> None:
    """Tasks screen naye status ke saath edit karo; sab complete ho to unlock karo."""
    row = await db.get_user(uid)
    if row is None:
        return
    member = await is_member(context.bot, uid, force=True)
    if await _maybe_finalize(context, row, member):
        await _safe_edit(query, M.unlocked(), None)
        return
    text, markup = _tasks_view(row, member)
    await _safe_edit(query, text, markup)


# ===========================================================================
# Commands
# ===========================================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message
    ref = None
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_") and arg[4:].isdigit():
            ref = int(arg[4:])  # deep link: t.me/<bot>?start=ref_<user_id>
    await db.upsert_user(user.id, user.username, user.first_name, ref)
    row = await db.get_user(user.id)
    if row is None:
        await msg.reply_text(M.TECH_ERROR)
        return
    row = await gate(update, context, row)
    if row:
        await msg.reply_text(M.welcome(user.first_name, row["credits"]))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(M.HELP)


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message
    row = await _ensure_user(user)
    member = await is_member(context.bot, user.id, force=True)
    if await _maybe_finalize(context, row, member):
        await msg.reply_text(M.unlocked())
        return
    text, markup = _tasks_view(row, member)
    await msg.reply_text(text, reply_markup=markup, disable_web_page_preview=True)


async def cmd_credits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = await gate(update, context)
    if row:
        await update.effective_message.reply_text(M.credits_info(row))


async def cmd_refer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = await gate(update, context)
    if row:
        link = f"https://t.me/{context.bot.username}?start=ref_{row['user_id']}"
        await update.effective_message.reply_text(M.refer_text(link), disable_web_page_preview=True)


async def cmd_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = await gate(update, context)
    if not row:
        return
    if claims_today(row) >= C.BONUS_DAILY_CAP:
        await update.effective_message.reply_text(M.BONUS_CAP)
        return
    await update.effective_message.reply_text(
        M.bonus_open(claims_today(row)), reply_markup=K.bonus_keyboard()
    )


# ----- admin ----------------------------------------------------------------
async def cmd_addcredits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/addcredits <user_id> <amount> — sirf admin."""
    if not _is_admin(update):
        return
    msg = update.effective_message
    try:
        uid, amount = int(context.args[0]), int(context.args[1])
    except (IndexError, ValueError):
        await msg.reply_text(M.ADDCREDITS_USAGE)
        return
    if abs(amount) > 100000:
        await msg.reply_text("⚠️ Amount bahut bada hai (max 100000).")
        return
    new_balance = await db.add_credits(uid, amount)
    if new_balance is None:
        await msg.reply_text("⚠️ Ye user nahi mila (usne bot start nahi kiya hoga).")
        return
    await msg.reply_text(M.addcredits_done(uid, amount, new_balance))
    if amount > 0:
        try:
            await context.bot.send_message(uid, M.credits_added_notice(amount, new_balance))
        except TelegramError:
            pass


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats — sirf admin."""
    if not _is_admin(update):
        return
    stats = await db.get_stats()
    await update.effective_message.reply_text(M.stats_text(stats))


# ===========================================================================
# Inline buttons
# ===========================================================================
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    uid = query.from_user.id

    if data == "noop":
        await query.answer()
        return

    row = await _ensure_user(query.from_user)
    if row.get("is_banned"):
        await query.answer(M.BANNED, show_alert=True)
        return

    # ----- tasks screen / verify -------------------------------------------
    if data in ("tasks", "verify"):
        member = await is_member(context.bot, uid, force=True)
        if data == "verify" and not row["tasks_done"] and not (
            member and row["yt_done"] and row["sponsor_done"]
        ):
            await query.answer(
                M.pending_alert(bool(member), row["yt_done"], row["sponsor_done"]), show_alert=True
            )
        elif data == "verify" and row["tasks_done"] and not member:
            await query.answer("❌ Channel abhi join nahi kiya.", show_alert=True)
        else:
            await query.answer()
        await _refresh_tasks_message(query, context, uid)
        return

    # ----- referral link ----------------------------------------------------
    if data == "refer":
        await query.answer()
        if row["tasks_done"]:
            link = f"https://t.me/{context.bot.username}?start=ref_{uid}"
            await query.message.reply_text(M.refer_text(link), disable_web_page_preview=True)
        return

    # ----- open:<key> / done:<key> -----------------------------------------
    action, _, key = data.partition(":")
    if action not in ("open", "done") or key not in ("yt", "sponsor", "bonus"):
        await query.answer()
        return

    if action == "open":
        if key == "bonus":
            if not row["tasks_done"]:
                await query.answer(M.NO_ACCESS, show_alert=True)
                return
            if claims_today(row) >= C.BONUS_DAILY_CAP:
                await query.answer(M.BONUS_CAP, show_alert=True)
                return
            await db.arm_task(uid, "bonus")
            await query.answer()
            await _safe_edit(query, M.bonus_open(claims_today(row)), K.bonus_open_keyboard())
            return
        if row[f"{key}_done"]:
            await query.answer("✅ Ye task pehle hi complete hai.")
            await _refresh_tasks_message(query, context, uid)
            return
        await db.arm_task(uid, key)
        await query.answer()
        await _safe_edit(query, M.task_open(key), K.task_open_keyboard(key))
        return

    # action == "done"
    if key == "bonus":
        res = await db.claim_bonus(uid, C.BONUS_MIN_SECONDS, C.BONUS_DAILY_CAP, C.BONUS_CREDITS)
        if res == "ok":
            fresh = await db.get_user(uid)
            await query.answer("🎉 Credit mil gaya!")
            await _safe_edit(query, M.bonus_success(fresh["credits"] if fresh else 0), None)
        elif res == "too_fast":
            await query.answer(M.too_fast(C.BONUS_MIN_SECONDS), show_alert=True)
        elif res == "cap_reached":
            await query.answer(M.BONUS_CAP, show_alert=True)
        elif res == "not_started":
            await query.answer(M.NOT_STARTED, show_alert=True)
        else:
            await query.answer(M.NO_ACCESS, show_alert=True)
        return

    min_seconds = C.YT_MIN_SECONDS if key == "yt" else C.SPONSOR_MIN_SECONDS
    res = await db.complete_task(uid, key, min_seconds)
    if res in ("ok", "already"):
        await query.answer("✅ Task complete mark ho gaya!")
        await _refresh_tasks_message(query, context, uid)
    elif res == "too_fast":
        await query.answer(M.too_fast(min_seconds), show_alert=True)
    elif res == "not_started":
        await query.answer(M.NOT_STARTED, show_alert=True)
    else:
        await query.answer(M.TECH_ERROR_SHORT, show_alert=True)


# ===========================================================================
# Video analysis (core feature)
# ===========================================================================
def _remove_file(path: Optional[str]) -> None:
    """Temp file turant delete karo (error ignore, sirf log)."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError as exc:
            log.warning("Temp file delete nahi hui (%s): %s", path, exc)


async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = await gate(update, context)
    if not row:
        return

    msg = update.effective_message
    uid = update.effective_user.id
    media = msg.video or msg.document
    if media is None:
        return
    mime = media.mime_type or "video/mp4"

    if msg.document and not mime.startswith("video/"):
        await msg.reply_text(M.NOT_VIDEO)
        return
    if media.file_size and media.file_size > C.MAX_VIDEO_MB * 1024 * 1024:
        await msg.reply_text(M.too_big(C.MAX_VIDEO_MB))
        return
    if int(row.get("credits") or 0) <= 0:
        await msg.reply_text(M.NO_CREDITS, reply_markup=K.no_credits_keyboard())
        return
    if uid in _BUSY_USERS:
        await msg.reply_text(M.BUSY)
        return

    _BUSY_USERS.add(uid)
    status_msg = None
    try:
        # Credit pehle hi atomically kat'ta hai (race condition nahi).
        if not await db.spend_credit(uid):
            await msg.reply_text(M.NO_CREDITS, reply_markup=K.no_credits_keyboard())
            return

        delivered = False
        too_big_error = False
        try:
            status_msg = await msg.reply_text(M.PROCESSING)
            tmp_path: Optional[str] = None
            try:
                fd, tmp_path = tempfile.mkstemp(prefix="mm_", suffix=".mp4")
                os.close(fd)
                tg_file = await media.get_file()
                await tg_file.download_to_drive(custom_path=tmp_path)
                async with _ANALYSIS_SEMAPHORE:
                    report = await asyncio.to_thread(analyze_video_blocking, tmp_path, mime)
            finally:
                _remove_file(tmp_path)  # analysis ke turant baad local file delete

            for chunk in split_text(clean_report(report)):
                await msg.reply_text(chunk)
            delivered = True
        except BadRequest as exc:
            if "too big" in str(exc).lower():
                too_big_error = True
            log.exception("Telegram BadRequest (user %s)", uid)
        except Exception:  # noqa: BLE001
            log.exception("Video analysis fail (user %s)", uid)

        if delivered:
            fresh = await db.get_user(uid)
            await msg.reply_text(M.report_footer(fresh["credits"] if fresh else 0))
            return

        # Fail hua -> credit refund
        refunded = True
        try:
            await db.refund_credit(uid)
        except Exception:  # noqa: BLE001
            refunded = False
            log.exception("REFUND FAIL user=%s — manually 1 credit add karo", uid)
            await _alert_admins(context.bot, f"⚠️ Refund fail hua: user {uid}. /addcredits {uid} 1 chalao.")
        await msg.reply_text(M.too_big(C.MAX_VIDEO_MB) if too_big_error else M.analysis_failed(refunded))
    finally:
        _BUSY_USERS.discard(uid)
        if status_msg is not None:
            try:
                await status_msg.delete()
            except TelegramError:
                pass


async def on_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Text/photo/etc. — video maango (pehle gate se guzro)."""
    row = await gate(update, context)
    if row:
        await update.effective_message.reply_text(M.SEND_VIDEO)


# ===========================================================================
# Errors + registration
# ===========================================================================
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Unhandled exception", exc_info=context.error)
    if not isinstance(update, Update):
        return
    try:
        if update.callback_query:
            await update.callback_query.answer(M.TECH_ERROR_SHORT, show_alert=True)
        elif update.effective_chat and update.effective_chat.type == "private":
            await context.bot.send_message(update.effective_chat.id, M.TECH_ERROR)
    except TelegramError:
        pass


async def post_init(app: Application) -> None:
    """Bot start hote hi command menu set karo."""
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Bot shuru karo"),
            BotCommand("tasks", "3 tasks ka status"),
            BotCommand("credits", "Apna balance dekho"),
            BotCommand("bonus", "Sponsor link se free credit"),
            BotCommand("refer", "Dosto ko invite karo"),
            BotCommand("help", "Madad"),
        ]
    )


def register(app: Application) -> None:
    """Saare handlers Application me jodo (sirf private chat)."""
    private = filters.ChatType.PRIVATE
    video = filters.VIDEO | filters.Document.VIDEO

    app.add_handler(CommandHandler("start", cmd_start, filters=private))
    app.add_handler(CommandHandler("help", cmd_help, filters=private))
    app.add_handler(CommandHandler("tasks", cmd_tasks, filters=private))
    app.add_handler(CommandHandler("credits", cmd_credits, filters=private))
    app.add_handler(CommandHandler("refer", cmd_refer, filters=private))
    app.add_handler(CommandHandler("bonus", cmd_bonus, filters=private))
    app.add_handler(CommandHandler("addcredits", cmd_addcredits, filters=private))
    app.add_handler(CommandHandler("stats", cmd_stats, filters=private))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(private & video, on_video))
    app.add_handler(MessageHandler(private & ~filters.COMMAND & ~video, on_other))
    app.add_error_handler(on_error)
