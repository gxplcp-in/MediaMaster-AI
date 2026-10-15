"""
bot.py — MediaMaster AI (@MediaMaster_AIBot) ka entry point.

Run:  python bot.py

Modules:
  config.py          settings + env vars
  database.py        Supabase (PostgreSQL) layer      <- schema.sql
  gemini_service.py  Gemini 2.5 Flash video analysis
  handlers.py        Telegram commands / buttons / video flow
  messages.py        Hinglish texts
  keyboards.py       inline buttons
  health.py          health-check server (polling mode)

Modes:
  Polling (default)  -> health server + run_polling
  Webhook            -> WEBHOOK_URL + WEBHOOK_SECRET set karo (Koyeb free instance ke liye behtar)
"""
from __future__ import annotations

import logging
import sys

import config


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        level=logging.INFO,
    )
    # httpx har request log karta hai — usme bot token dikh sakta hai, isliye chup karao
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    missing = config.missing_env()
    if missing:
        sys.exit("❌ Ye environment variables set karo: " + ", ".join(missing))
    webhook_error = config.webhook_config_error()
    if webhook_error:
        sys.exit("❌ " + webhook_error)

    # Heavy imports validation ke baad (jaldi error dikhane ke liye)
    from telegram.ext import Application

    import handlers
    from health import start_health_server

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(15)
        .pool_timeout(15)
        .post_init(handlers.post_init)
        .build()
    )
    handlers.register(app)

    log = logging.getLogger("mediamaster")
    if config.WEBHOOK_URL:
        log.info("Webhook mode (port %s, model=%s)", config.PORT, config.GEMINI_MODEL)
        app.run_webhook(
            listen="0.0.0.0",
            port=config.PORT,
            url_path=config.WEBHOOK_SECRET,
            webhook_url=f"{config.WEBHOOK_URL.rstrip('/')}/{config.WEBHOOK_SECRET}",
            secret_token=config.WEBHOOK_SECRET,
        )
    else:
        log.info("Polling mode (port %s, model=%s)", config.PORT, config.GEMINI_MODEL)
        start_health_server(config.PORT)
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
