FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN curl -sL -o wgcf https://github.com/ViRb3/wgcf/releases/download/v2.2.22/wgcf_2.2.22_linux_amd64 && chmod +x wgcf \
 && curl -sL https://github.com/pufferffish/wireproxy/releases/latest/download/wireproxy_linux_amd64.tar.gz | tar xz && chmod +x wireproxy
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py downloader.py start.sh ./
RUN chmod +x start.sh
CMD ["./start.sh"]
