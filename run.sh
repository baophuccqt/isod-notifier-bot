#!/usr/bin/env bash
# Chạy bot ISOD đúng 1 lần — dùng cho cron (mỗi 5 phút).
# Cron có môi trường tối giản nên script tự cd + tự chỉ định python trong venv.
cd "$(dirname "$0")" || exit 1

LOG="bot.log"

# Cắt log nếu vượt 1MB để khỏi đầy ổ đĩa (chỉ giữ 500 dòng cuối).
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 1048576 ]; then
  tail -n 500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> "$LOG"
exec ./venv/bin/python main.py --once >> "$LOG" 2>&1
