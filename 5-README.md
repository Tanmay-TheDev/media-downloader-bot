# Media Downloader Telegram Bot

Telegram bot (Python, python-telegram-bot + yt-dlp + ffmpeg). Send a link, pick a quality, get the video or MP3.

Sites: YouTube, Instagram, Facebook, TikTok, Pinterest, X/Twitter, Reddit and anything else yt-dlp supports.
Not supported: TeraBox (needs a captcha/app check).

Telegram bots can upload up to 50 MB. Bigger results get a direct link when available.

## Run
    BOT_TOKEN=... python bot.py                      # long polling
    BOT_TOKEN=... PUBLIC_URL=https://host python bot.py   # webhook mode (used on Render)

Needs ffmpeg. Only download content you have the right to download.
