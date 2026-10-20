import os, asyncio, logging, shutil, tempfile, secrets
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (Application, CommandHandler, MessageHandler, CallbackQueryHandler,
                          ContextTypes, filters)
import downloader as dl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")
TOKEN = os.environ["BOT_TOKEN"]
BASE_URL = os.environ.get("PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", "8080"))
SEM = asyncio.Semaphore(int(os.environ.get("MAX_JOBS", "2")))
PENDING = {}  # id -> (url, info summary)

HELP = ("Send me a link from YouTube, Instagram, Facebook, TikTok, Pinterest, "
        "X/Twitter, Reddit and many other sites. I will ask which quality you want "
        "(video 144p-1080p or audio MP3) and send the file.\n\n"
        "Limit: Telegram bots can send files up to 50 MB. For bigger files I give a direct "
        "download link when the site allows it, or offer a lower quality.\n"
        "Only download content you have the right to download.")


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! " + HELP)


def kb_for(key, info):
    rows = []
    heights = dl.pick_heights(info)
    vids = [InlineKeyboardButton(f"🎬 {h}p", callback_data=f"{key}|v|{h}") for h in heights]
    if not vids and dl.has_video(info):
        vids = [InlineKeyboardButton("🎬 Best", callback_data=f"{key}|v|best"),
                InlineKeyboardButton("🎬 Smaller", callback_data=f"{key}|v|worst")]
    for i in range(0, len(vids), 3):
        rows.append(vids[i:i + 3])
    rows.append([InlineKeyboardButton("🎵 MP3 128k", callback_data=f"{key}|a|128"),
                 InlineKeyboardButton("🎵 MP3 192k", callback_data=f"{key}|a|192"),
                 InlineKeyboardButton("🎵 MP3 320k", callback_data=f"{key}|a|320")])
    return InlineKeyboardMarkup(rows)


def fmt_dur(s):
    if not s: return ""
    s = int(s); h, r = divmod(s, 3600); m, sec = divmod(r, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = dl.find_url(update.message.text)
    if not url:
        await update.message.reply_text("Send me a video link.")
        return
    if any(x in url.lower() for x in ("terabox", "1024tera", "teraboxapp", "4funbox", "mirrobox", "nephobox", "momerybox")):
        await update.message.reply_text("TeraBox links are not supported. TeraBox asks for a captcha/app check that "
                                        "a free server cannot pass. Download it in the TeraBox app instead.")
        return
    note = await update.message.reply_text("🔎 Checking link...")
    try:
        info = await asyncio.to_thread(dl.get_info, url)
    except Exception as e:
        log.warning("info failed %s: %s", url, e)
        await note.edit_text(explain_error(e))
        return
    if info.get("_type") == "playlist" and info.get("entries"):
        entries = [x for x in info["entries"] if x]
        if entries:
            info = entries[0]
    key = secrets.token_hex(4)
    PENDING[key] = url
    if len(PENDING) > 500:
        PENDING.pop(next(iter(PENDING)))
    title = (info.get("title") or "Video")[:120]
    dur = fmt_dur(info.get("duration"))
    await note.edit_text(f"{title}\n{('Duration ' + dur) if dur else ''}\nChoose quality:",
                         reply_markup=kb_for(key, info))


def explain_error(e):
    m = str(e)
    low = m.lower()
    if "sign in" in low or "confirm you" in low and "bot" in low:
        return "YouTube blocked this server for this video (it asks for a sign in). Try another video or try again later."
    if "login" in low or "private" in low or "cookies" in low or "empty media response" in low:
        return "This post needs a login or is private, so I cannot download it."
    if "unsupported url" in low:
        return "This site or link type is not supported."
    if "no video formats" in low:
        return "No downloadable video found in this link (it may be an image pin)."
    return "Could not read this link: " + m.replace("ERROR: ", "")[:200]


async def on_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        key, kind, quality = q.data.split("|")
    except ValueError:
        return
    url = PENDING.get(key)
    if not url:
        await q.edit_message_text("This choice expired. Send the link again.")
        return
    kind = "video" if kind == "v" else "audio"
    await q.edit_message_text("⏳ Downloading... (queued)" if SEM.locked() else "⏳ Downloading...")
    chat_id = q.message.chat_id
    workdir = tempfile.mkdtemp(prefix="dl_")
    try:
        async with SEM:
            path = await asyncio.wait_for(asyncio.to_thread(dl.download, url, kind, quality, workdir), 900)
            size = os.path.getsize(path)
            if size > dl.MAX_BYTES:
                link = await asyncio.to_thread(dl.direct_link, url, kind, quality)
                msg = f"File is {size/1048576:.0f} MB, above Telegram's 50 MB bot limit. "
                if link:
                    msg += "Direct link (may expire):\n" + link
                else:
                    msg += "Try a lower quality."
                await q.edit_message_text(msg)
                return
            await q.edit_message_text("📤 Uploading...")
            await ctx.bot.send_chat_action(chat_id, ChatAction.UPLOAD_VIDEO if kind == "video" else ChatAction.UPLOAD_VOICE)
            with open(path, "rb") as f:
                if kind == "video":
                    await ctx.bot.send_video(chat_id, f, supports_streaming=True, filename=os.path.basename(path),
                                             read_timeout=300, write_timeout=300)
                else:
                    await ctx.bot.send_audio(chat_id, f, filename=os.path.basename(path),
                                             read_timeout=300, write_timeout=300)
            await q.edit_message_text("✅ Done.")
    except asyncio.TimeoutError:
        await q.edit_message_text("Took too long, try a lower quality.")
    except Exception as e:
        log.exception("download failed")
        await q.edit_message_text(explain_error(e))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CallbackQueryHandler(on_choice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    if BASE_URL:
        import hashlib
        hook = hashlib.sha256(("hook" + TOKEN).encode()).hexdigest()[:32]
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path=hook,
                        webhook_url=f"{BASE_URL.rstrip('/')}/{hook}",
                        drop_pending_updates=False)
    else:
        app.run_polling()


if __name__ == "__main__":
    main()
