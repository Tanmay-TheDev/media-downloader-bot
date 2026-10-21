"""Download helpers built on yt-dlp."""
import os, re, glob, tempfile, shutil, asyncio
import yt_dlp

MAX_BYTES = 49 * 1024 * 1024  # Telegram bot upload limit is 50 MB

URL_RE = re.compile(r"https?://[^\s<>]+")


def find_url(text: str):
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(").,]") if m else None


# PO-token-supported clients (BgUtils POT provider). android/ios have no POT support
# and hard-fail from datacenter IPs, so they are not tried.
YT_CLIENTS = ["web", "mweb", "tv", "web_embedded", "tv_embedded", "web_safari"]


def is_yt(url):
    return any(x in url.lower() for x in ("youtube.com", "youtu.be"))


def with_clients(url, fn):
    """Run fn(extra_opts); for YouTube try several PO-token-capable player clients until one works."""
    if not is_yt(url):
        return fn({})
    last = None
    for c in YT_CLIENTS:
        try:
            x = {"extractor_args": {
                "youtube": {"player_client": [c]},
                # fallback POT script provider if the HTTP server is down
                "youtubepot-bgutilscript": {"server_home": ["/opt/pot/server"]},
            }}
            return fn(x)
        except Exception as e:
            last = e
            print("yt", c, "failed:", str(e)[:120], flush=True)
    raise last


def _base_opts():
    o = {"quiet": True, "no_warnings": True, "noplaylist": True,
         "socket_timeout": 30, "retries": 3, "nocheckcertificate": False,
         "impersonate": None}
    o.pop("impersonate")
    cookies = os.environ.get("COOKIES_FILE")
    if cookies and os.path.exists(cookies):
        o["cookiefile"] = cookies
    proxy = os.environ.get("PROXY_URL")
    if proxy:
        o["proxy"] = proxy
    return o


def get_info(url: str) -> dict:
    def go(x):
        with yt_dlp.YoutubeDL({**_base_opts(), **x, "skip_download": True}) as y:
            return y.extract_info(url, download=False)
    return with_clients(url, go)


def video_heights(info: dict):
    hs = set()
    for f in info.get("formats") or []:
        h = f.get("height")
        if h and f.get("vcodec") not in (None, "none"):
            hs.add(int(h))
    return sorted(hs, reverse=True)


def pick_heights(info: dict):
    """Return a short list of offered heights (max 5)."""
    hs = video_heights(info)
    wanted = [1080, 720, 480, 360, 240, 144]
    out = []
    for w in wanted:
        cands = [h for h in hs if h <= w]
        if cands and cands[0] not in out and (cands[0] >= w * 0.6):
            out.append(cands[0])
    if hs and hs[0] > 1080 and hs[0] not in out:
        out.insert(0, hs[0]) if hs[0] <= 2160 else None
    return out[:5]


def has_video(info: dict) -> bool:
    return bool(video_heights(info)) or bool(info.get("url") and info.get("ext") in ("mp4", "webm", "mov"))


def download(url: str, kind: str, quality, outdir: str) -> str:
    """kind: 'video' or 'audio'. quality: height int for video, kbps int for audio.
    Returns path of the file."""
    opts = {**_base_opts(), "outtmpl": os.path.join(outdir, "%(title).80B [%(id)s].%(ext)s"),
            "restrictfilenames": False, "windowsfilenames": True,
            "concurrent_fragment_downloads": 4}
    if kind == "audio":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                                   "preferredquality": str(quality)}]
    else:
        if quality in ("best", "worst"):
            opts["format"] = "b/bv*+ba" if quality == "best" else "w/wv*+wa"
            opts["merge_output_format"] = "mp4"
            h = None
        else:
            h = int(quality)
    if kind != "audio" and h is not None:
        opts["format"] = (f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/bv*[height<={h}]+ba/"
                          f"b[height<={h}]/b")
        opts["merge_output_format"] = "mp4"
    def go(x):
        with yt_dlp.YoutubeDL({**opts, **x}) as y:
            y.extract_info(url, download=True)
    with_clients(url, go)
    files = [f for f in glob.glob(os.path.join(outdir, "*")) if not f.endswith((".part", ".ytdl"))]
    if not files:
        raise RuntimeError("Nothing was downloaded")
    return max(files, key=os.path.getsize)


def direct_link(url: str, kind: str, quality):
    """Best-effort direct media URL (for files too big for Telegram)."""
    try:
        h = int(quality) if (kind == "video" and str(quality).isdigit()) else 9999
        fmt = (f"b[height<={h}][protocol^=http]/b[protocol^=http]" if kind == "video"
               else "ba[protocol^=http]/b[protocol^=http]")
        with yt_dlp.YoutubeDL({**_base_opts(), "skip_download": True, "format": fmt}) as y:
            i = y.extract_info(url, download=False)
        return i.get("url")
    except Exception:
        return None
