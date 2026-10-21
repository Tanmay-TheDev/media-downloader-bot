#!/bin/sh
# Start the BgUtils PO-token provider (YouTube bot-check bypass), then the bot.
cd /app
node /opt/pot/server/build/main.js >/tmp/pot.log 2>&1 &
echo "waiting for POT server..."
for i in $(seq 1 60); do
  if curl -sf -m 2 http://127.0.0.1:4416/ping >/dev/null 2>&1; then echo "POT server up"; break; fi
  sleep 1
done
exec python bot.py
