#!/bin/sh
# Free Cloudflare WARP tunnel (userspace, no root) used only for YouTube.
cd /app
if [ ! -f wgcf-profile.conf ]; then
  ./wgcf register --accept-tos >/dev/null 2>&1 && ./wgcf generate >/dev/null 2>&1
fi
if [ -f wgcf-profile.conf ]; then
  cp wgcf-profile.conf wp.conf
  printf '\n[Socks5]\nBindAddress = 127.0.0.1:1080\n' >> wp.conf
  ./wireproxy -c wp.conf >/tmp/wireproxy.log 2>&1 &
  sleep 3
  export YT_PROXY=socks5://127.0.0.1:1080
  echo "WARP exit IP: $(curl -s -m 15 -x socks5h://127.0.0.1:1080 https://ifconfig.me)"
else
  echo "WARP registration failed; YouTube uses direct only"
fi
exec python bot.py
