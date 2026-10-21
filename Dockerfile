FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl git unzip xz-utils && rm -rf /var/lib/apt/lists/*
# Node 22 - runs the PO token provider server
RUN curl -fsSL https://nodejs.org/dist/v22.23.3/node-v22.23.3-linux-x64.tar.xz | tar -xJ -C /opt \
 && ln -s /opt/node-v22.23.3-linux-x64/bin/node /usr/local/bin/node \
 && ln -s /opt/node-v22.23.3-linux-x64/bin/npm /usr/local/bin/npm \
 && ln -s /opt/node-v22.23.3-linux-x64/bin/npx /usr/local/bin/npx
# Deno - yt-dlp's JS challenge solver (EJS) for YouTube
RUN curl -fsSL -o /tmp/deno.zip https://github.com/denoland/deno/releases/download/v2.9.7/deno-x86_64-unknown-linux-gnu.zip \
 && unzip -q /tmp/deno.zip -d /opt/deno && ln -s /opt/deno/deno /usr/local/bin/deno && rm /tmp/deno.zip
# BgUtils PO token provider (grqz/Brainicism) - generates YouTube proof-of-origin tokens
RUN git clone --single-branch --branch 2.0.2 --depth 1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/pot \
 && cd /opt/pot/server && npm ci --no-audit --no-fund && npx tsc
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py downloader.py start.sh ./
RUN chmod +x start.sh
CMD ["./start.sh"]
