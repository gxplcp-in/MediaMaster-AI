"""
messages.py — bot ke saare user-facing messages (Hinglish).
Plain text use hota hai (parse_mode nahi) taaki special characters se error na aaye.
"""
from __future__ import annotations

import config as C


def tick(ok: bool) -> str:
    """Task status icon."""
    return "✅" if ok else "⬜"


# ---------------------------------------------------------------------------
# Static messages
# ---------------------------------------------------------------------------
HELP = (
    "ℹ️ MediaMaster AI — Madad\n\n"
    "🎬 Mujhe apni Reel/Shorts video bhejo, main viral report bana dunga "
    "(Instagram, Facebook, YouTube Shorts, Snapchat/Moj/LinkedIn + best posting time).\n"
    "💳 Har video analysis me 1 credit lagta hai.\n\n"
    "Commands:\n"
    "/start — bot shuru karo\n"
    "/tasks — 3 tasks ka status dekho\n"
    "/credits — apna balance dekho\n"
    "/bonus — sponsor link se free credit kamao\n"
    f"/refer — dosto ko invite karo (+{C.REFERRAL_BONUS} credits har dost par)\n"
    "/help — ye madad message"
)

BANNED = "🚫 Tumhara account block hai. Zyada jaankari ke liye admin se sampark karo."

MEMBERSHIP_CHECK_FAILED = (
    "⚠️ Abhi Telegram channel check nahi ho pa raha hai. Thodi der baad dobara try karo."
)

TECH_ERROR = "😔 Kuch technical dikkat aa gayi hai. Thodi der baad dobara try karo."
TECH_ERROR_SHORT = "😔 Technical dikkat aayi, dobara try karo."

CHANNEL_LEFT = (
    "⚠️ Lagta hai tumne hamara Telegram channel leave kar diya hai.\n\n"
    "Bot use karne ke liye channel wapas join karo, phir 'Verify Karo' dabao."
)

TASKS_ALL_DONE = "✅ Tumhare saare tasks complete hain! Ab apni video bhejo 🎬"

NOT_VIDEO = "⚠️ Sirf video file bhejo (MP4 / MOV). Photo ya dusri file analyse nahi hoti."

BUSY = "⏳ Tumhari pichhli video abhi process ho rahi hai. Thoda ruko, phir nayi video bhejo."

PROCESSING = "🔄 Video analyse ho rahi hai... Isme 1-2 minute lag sakte hain. Please wait karo ⏳"

SEND_VIDEO = "🎬 Analysis ke liye mujhe ek video bhejo (MP4 / Reel / Shorts clip)."

NO_CREDITS = (
    "😕 Tumhare credits khatam ho gaye hain!\n\n"
    "Free credits paane ke 2 tareeke:\n"
    f"1️⃣ Sponsor link dekho (/bonus) — roz {C.BONUS_DAILY_CAP} baar, har baar +{C.BONUS_CREDITS} credit\n"
    f"2️⃣ Dosto ko refer karo (/refer) — har dost par +{C.REFERRAL_BONUS} credits"
)

NO_ACCESS = "⚠️ Pehle saare 3 tasks complete karo (/tasks)."

NOT_STARTED = "⚠️ Pehle upar ka link kholne wala button dabao, phir 'Done' dabao."

ADDCREDITS_USAGE = "ℹ️ Use karo: /addcredits <user_id> <amount>\nJaise: /addcredits 123456789 5"

BONUS_CAP = (
    f"⏳ Aaj ke {C.BONUS_DAILY_CAP} bonus credits tum le chuke ho. "
    "Kal wapas aana, ya /refer se dosto ko invite karo!"
)


# ---------------------------------------------------------------------------
# Dynamic messages
# ---------------------------------------------------------------------------
def tasks_screen(tg_ok: bool, yt_ok: bool, sp_ok: bool, tg_error: bool = False) -> str:
    text = (
        "🔒 Bot unlock karne ke liye ye 3 tasks poore karo:\n\n"
        f"{tick(tg_ok)} Task 1: Telegram channel join karo\n"
        f"{tick(yt_ok)} Task 2: YouTube channel subscribe karo\n"
        f"{tick(sp_ok)} Task 3: Sponsor link dekho\n\n"
        f"🎁 Teeno complete hone par tumhe {C.START_CREDITS} FREE credits milenge!\n"
        "Sab karne ke baad 'Verify Karo' dabao."
    )
    if tg_error:
        text += "\n\n⚠️ Telegram channel check abhi nahi ho paya, thodi der baad dobara try karo."
    return text


def task_open(key: str) -> str:
    """Task 2 / Task 3 ka instruction screen."""
    if key == "yt":
        return (
            "▶️ Task 2: YouTube Channel Subscribe\n\n"
            "1️⃣ Neeche 'YouTube Channel Kholo' button dabao\n"
            "2️⃣ Channel ko Subscribe karo 🔔\n"
            "3️⃣ Wapas aakar 'Maine Subscribe Kar Liya' dabao\n\n"
            f"⏳ Link kholne ke kam se kam {C.YT_MIN_SECONDS} second baad hi 'Done' kaam karega."
        )
    return (
        "🎁 Task 3: Sponsor Link Dekho\n\n"
        "1️⃣ Neeche 'Sponsor Link Kholo' button dabao\n"
        "2️⃣ Page ko kuch second dekho\n"
        "3️⃣ Wapas aakar 'Maine Dekh Liya' dabao\n\n"
        f"⏳ Link kholne ke kam se kam {C.SPONSOR_MIN_SECONDS} second baad hi 'Done' kaam karega."
    )


def bonus_open(claims_today: int) -> str:
    return (
        "🎁 Free Credit Kamao\n\n"
        "1️⃣ Neeche 'Sponsor Link Kholo' button dabao\n"
        "2️⃣ Page ko kuch second dekho\n"
        "3️⃣ Wapas aakar 'Maine Dekh Liya' dabao\n\n"
        f"💳 Har baar +{C.BONUS_CREDITS} credit | Aaj: {claims_today}/{C.BONUS_DAILY_CAP}\n"
        f"⏳ Link kholne ke kam se kam {C.BONUS_MIN_SECONDS} second baad hi 'Done' kaam karega."
    )


def too_fast(seconds: int) -> str:
    return f"⏳ Thoda jaldi ho gaya! Link kholkar kam se kam {seconds} second ruko, phir 'Done' dabao."


def pending_alert(tg_ok: bool, yt_ok: bool, sp_ok: bool) -> str:
    """Verify dabane par kaun se tasks baaki hain."""
    pending = []
    if not tg_ok:
        pending.append("Telegram channel join")
    if not yt_ok:
        pending.append("YouTube subscribe")
    if not sp_ok:
        pending.append("Sponsor link")
    if not pending:
        return "✅ Sab tasks complete!"
    return "❌ Ye tasks abhi baaki hain: " + ", ".join(pending)


def unlocked() -> str:
    return (
        "🎉 Badhai ho! Saare 3 tasks complete ho gaye.\n\n"
        f"🎁 Tumhe {C.START_CREDITS} FREE credits mil gaye hain.\n\n"
        "Ab apni Reel/Shorts video bhejo, main viral report bana dunga! 🎬"
    )


def welcome(first_name: str, credits: int) -> str:
    name = first_name or "dost"
    return (
        f"🙏 Namaste {name}! Main MediaMaster AI hoon.\n\n"
        "🎬 Mujhe apni Reel/Shorts video bhejo, main viral report bana dunga:\n"
        "• Instagram Reels\n• Facebook Page/Reels\n• YouTube Shorts\n"
        "• Snapchat, Moj, LinkedIn\n• Best posting time ⏰\n\n"
        f"💳 Tumhare paas abhi {credits} credits hain (1 video = 1 credit).\n\n"
        "/credits — balance | /bonus — free credit | /refer — dosto ko invite karo | /help — madad"
    )


def credits_info(row: dict) -> str:
    return (
        f"💳 Credits: {row.get('credits', 0)}\n"
        f"🤝 Referrals: {row.get('referral_count', 0)}\n"
        f"🎬 Videos analyse hui: {row.get('total_requests', 0)}"
    )


def refer_text(link: str) -> str:
    return (
        "🤝 Apna referral link dosto ko bhejo:\n\n"
        f"{link}\n\n"
        f"Jab tumhara dost is link se bot start karke saare 3 tasks complete karega, "
        f"tumhe +{C.REFERRAL_BONUS} credits milenge! 🎁"
    )


def referral_reward() -> str:
    return f"🎉 Tumhare referral se ek dost ne saare tasks complete kiye! +{C.REFERRAL_BONUS} credits mile."


def bonus_success(credits: int) -> str:
    return f"🎉 +{C.BONUS_CREDITS} credit mil gaya!\n💳 Ab tumhare paas {credits} credits hain. Video bhejo 🎬"


def too_big(max_mb: int) -> str:
    return f"⚠️ Video {max_mb} MB se badi hai. Chhoti ya compress ki hui video bhejo."


def analysis_failed(refunded: bool) -> str:
    if refunded:
        return "❌ Video analyse nahi ho paayi. Tumhara 1 credit wapas add kar diya gaya hai. Dobara try karo."
    return (
        "❌ Video analyse nahi ho paayi. Credit wapas karne me dikkat aayi — "
        "admin se sampark karo, tumhara credit wapas mil jayega."
    )


def report_footer(credits: int) -> str:
    return f"✅ Report ready! Bache hue credits: {credits}"


def addcredits_done(uid: int, amount: int, new_balance: int) -> str:
    return f"✅ User {uid} ko {amount} credits diye. Naya balance: {new_balance}"


def credits_added_notice(amount: int, new_balance: int) -> str:
    return f"🎁 Admin ne tumhe {amount} credits diye hain! Naya balance: {new_balance}"


def stats_text(stats: dict) -> str:
    return (
        "📊 MediaMaster AI Stats\n\n"
        f"👥 Total users: {stats.get('total_users', 0)}\n"
        f"✅ Verified users: {stats.get('verified_users', 0)}\n"
        f"🎬 Total video requests: {stats.get('total_requests', 0)}"
    )
