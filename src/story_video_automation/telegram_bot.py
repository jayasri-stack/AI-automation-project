"""Telegram approval notifications and a chat-authorized approve/reject bot."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os

from story_video_automation.config import get_settings
from story_video_automation.db import list_jobs
from story_video_automation.options import Options
from story_video_automation.state import get_made_for_kids, get_upload_privacy
logger = logging.getLogger(__name__)


def _preview_token(path: str | None) -> str:
    return hashlib.sha256((path or "").encode("utf-8")).hexdigest()[:10]


def _credentials() -> tuple[str, int]:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable Telegram")
    try:
        chat_id = int(settings.telegram_chat_id)
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_CHAT_ID must be a numeric Telegram chat ID") from exc
    return settings.telegram_bot_token, chat_id


async def _send_approval(job_id: int) -> None:
    try:
        from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError as exc:
        raise RuntimeError('Install the "telegram" extra to send Telegram approvals') from exc

    token, chat_id = _credentials()
    job = next((item for item in list_jobs() if item["id"] == job_id), None)
    if job is None or job["status"] != "awaiting_approval":
        raise ValueError("Only jobs awaiting approval can be sent to Telegram")
    made_for_kids = get_made_for_kids(job_id)
    token_id = f"{job_id}:{_preview_token(job.get('preview_path'))}"
    buttons = []
    if made_for_kids is not None:
        buttons.append([
            InlineKeyboardButton("Approve and upload", callback_data=f"approve:{token_id}"),
            InlineKeyboardButton("Reject", callback_data=f"reject:{token_id}"),
        ])
    buttons.append([InlineKeyboardButton(
        "Open preview dashboard",
        url=f"{os.getenv('DASHBOARD_URL', 'http://localhost:8501').rstrip('/')}/?job_id={job_id}",
    )])
    markup = InlineKeyboardMarkup(buttons)
    audience = (
        "Made for kids" if made_for_kids is True else
        "Not made for kids" if made_for_kids is False else
        "Audience choice required in dashboard"
    )
    bot = Bot(token=token)
    await bot.initialize()
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"Video ready for review\nJob #{job_id}: {job['title']}\n"
                f"Upload visibility: {get_upload_privacy(job_id)}\n"
                f"Audience: {audience}\n"
                "Open the local Streamlit dashboard to preview it."
            ),
            reply_markup=markup,
        )
    finally:
        await bot.shutdown()


def send_approval_notification(job_id: int) -> None:
    """Send one inline approval message to the configured private chat."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_send_approval(job_id))
    else:
        loop.create_task(_send_approval(job_id))


async def _on_start(update: object, context: object) -> None:
    _, chat_id = _credentials()
    chat = getattr(update, "effective_chat", None)
    message = getattr(update, "effective_message", None)
    if chat is None or message is None:
        return
    if int(chat.id) != chat_id:
        await message.reply_text("This bot is restricted to its configured approval chat.")
        return
    await message.reply_text("Approval bot connected. New completed previews will appear here.")


async def _on_decision(update: object, context: object) -> None:
    from story_video_automation.approval import decide

    query = getattr(update, "callback_query", None)
    if query is None:
        return
    await query.answer()
    _, allowed_chat = _credentials()
    chat = getattr(update, "effective_chat", None)
    if chat is None or int(chat.id) != allowed_chat:
        await query.edit_message_text("This approval action is not authorized for this chat.")
        return
    payload = str(query.data or "")
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] not in {"approve", "reject"} or not parts[1].isdigit():
        await query.edit_message_text("This approval action is invalid.")
        return
    action, raw_job_id, sent_token = parts
    current_job = next((item for item in list_jobs() if item["id"] == int(raw_job_id)), None)
    if current_job is None or sent_token != _preview_token(current_job.get("preview_path")):
        await query.edit_message_text(
            "This preview has changed since this message was sent. Open the dashboard and review the latest version."
        )
        return
    decision = "approved" if action == "approve" else "rejected"
    user = getattr(update, "effective_user", None)
    reviewer = f"telegram:{getattr(user, 'id', 'unknown')}"
    try:
        # OAuth and upload work can be slow; keep Telegram's asyncio event loop responsive.
        result = await asyncio.to_thread(decide, int(raw_job_id), decision, reviewer)
        if decision == "rejected":
            message = f"Job #{raw_job_id} rejected. No upload will occur."
        elif result:
            message = f"Job #{raw_job_id} approved and uploaded. YouTube ID: {result}"
        else:
            message = f"Job #{raw_job_id} approved. Upload is ready to run."
        await query.edit_message_text(message)
    except Exception as exc:
        logger.exception("Telegram approval action failed for job %s", raw_job_id)
        from story_video_automation.db import list_jobs

        job = next((item for item in list_jobs() if item["id"] == int(raw_job_id)), None)
        if job and job["status"] == "uploading":
            message = (
                f"Approval was recorded, but upload outcome is uncertain: {exc}. "
                "Check YouTube Studio before resetting or retrying."
            )
        else:
            message = (
                f"Approval was recorded, but upload could not start: {exc}. "
                "Fix OAuth credentials, then use Retry upload in the dashboard."
            )
        await query.edit_message_text(message)


def run_bot() -> None:
    """Run long polling for the one configured Telegram approval chat."""
    token, _ = _credentials()
    try:
        from telegram.ext import Application, CallbackQueryHandler, CommandHandler
    except ImportError as exc:
        raise RuntimeError('Install the "telegram" extra to run the bot') from exc
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", _on_start))
    app.add_handler(CallbackQueryHandler(_on_decision, pattern=r"^(approve|reject):\d+:[a-f0-9]{10}$"))
    app.run_polling(
        poll_interval=Options.from_env().telegram_poll_seconds,
        allowed_updates=["message", "callback_query"],
    )


async def _read_chat_ids() -> list[tuple[int, str]]:
    from telegram import Bot

    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN first")
    bot = Bot(token=settings.telegram_bot_token)
    await bot.initialize()
    try:
        updates = await bot.get_updates(timeout=0, allowed_updates=["message"])
        unique = {
            int(update.effective_chat.id): str(
                getattr(update.effective_chat, "title", None)
                or getattr(update.effective_chat, "username", None)
                or getattr(update.effective_chat, "first_name", "Telegram chat")
            )
            for update in updates
            if update.effective_chat is not None
        }
        for chat_id in unique:
            await bot.send_message(chat_id, f"AI Automation approval chat ID: {chat_id}")
        return list(unique.items())
    finally:
        await bot.shutdown()


def print_chat_ids() -> None:
    """Read pending Telegram messages to discover this bot's numeric chat ID."""
    chats = asyncio.run(_read_chat_ids())
    if not chats:
        print("No messages found. Send /start to the bot, then run this command again.")
        return
    for chat_id, title in chats:
        print(f"{chat_id}\t{title}")
