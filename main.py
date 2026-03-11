import requests
import json
import time
import os
from datetime import datetime

# ========== CẤU HÌNH ==========
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8243204723:AAHYnvEoYdT7WRm6CjN0tohw1qtXIaDZoN0")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6850792800")

ISOD_USERNAME = os.environ.get("ISOD_USERNAME", "nghiabaophuc.ho")
ISOD_API_KEY = os.environ.get("ISOD_API_KEY", "odoaVcuhIdEDvPVmHPWCqA")
ISOD_BASE_URL = "https://isod.ee.pw.edu.pl/isod-portal/wapi?"

CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "120"))

# Upstash Redis REST API
UPSTASH_REDIS_REST_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

REDIS_KEY_FINGERPRINT = "isod:fingerprint"
REDIS_KEY_SEEN_HASHES = "isod:seen_hashes"

# ========== REDIS ==========
def _redis_headers():
    return {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}

def redis_get(key):
    """Lấy giá trị string từ Redis"""
    try:
        r = requests.get(
            f"{UPSTASH_REDIS_REST_URL}/get/{key}",
            headers=_redis_headers(),
            timeout=5
        )
        return r.json().get("result")  # None nếu key chưa tồn tại
    except Exception as e:
        print(f"❌ Redis GET lỗi: {e}")
        return None

def redis_set(key, value):
    """Lưu giá trị string vào Redis"""
    try:
        requests.get(
            f"{UPSTASH_REDIS_REST_URL}/set/{key}/{value}",
            headers=_redis_headers(),
            timeout=5
        )
    except Exception as e:
        print(f"❌ Redis SET lỗi: {e}")

def redis_sismember(key, member):
    """Kiểm tra member có trong set không"""
    try:
        r = requests.get(
            f"{UPSTASH_REDIS_REST_URL}/sismember/{key}/{member}",
            headers=_redis_headers(),
            timeout=5
        )
        return r.json().get("result") == 1
    except Exception as e:
        print(f"❌ Redis SISMEMBER lỗi: {e}")
        return False  # Nếu lỗi, coi như chưa thấy để tránh bỏ sót

def redis_sadd(key, member):
    """Thêm member vào set"""
    try:
        requests.get(
            f"{UPSTASH_REDIS_REST_URL}/sadd/{key}/{member}",
            headers=_redis_headers(),
            timeout=5
        )
    except Exception as e:
        print(f"❌ Redis SADD lỗi: {e}")

# ========== FINGERPRINT & SEEN HASHES ==========
def load_last_fingerprint():
    return redis_get(REDIS_KEY_FINGERPRINT)

def save_fingerprint(fingerprint):
    redis_set(REDIS_KEY_FINGERPRINT, fingerprint)

def is_hash_seen(hash_id):
    return redis_sismember(REDIS_KEY_SEEN_HASHES, hash_id)

def mark_hash_seen(hash_id):
    redis_sadd(REDIS_KEY_SEEN_HASHES, hash_id)

# ========== TELEGRAM ==========
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Đã gửi thông báo qua Telegram")
        else:
            print(f"❌ Lỗi gửi Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Lỗi kết nối Telegram: {e}")

# ========== ISOD ==========
def get_isod_fingerprint():
    params = {
        "q": "mynewsfingerprint",
        "username": ISOD_USERNAME,
        "apikey": ISOD_API_KEY
    }
    try:
        response = requests.get(ISOD_BASE_URL, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("fingerprint")
        else:
            print(f"❌ Lỗi lấy fingerprint: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Lỗi kết nối ISOD: {e}")
        return None

def get_isod_headers():
    params = {
        "q": "mynewsheaders",
        "username": ISOD_USERNAME,
        "apikey": ISOD_API_KEY
    }
    try:
        response = requests.get(ISOD_BASE_URL, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Lỗi lấy headers: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Lỗi kết nối ISOD: {e}")
        return None

# ========== LOGIC CHÍNH ==========
def check_isod_notifications():
    # Bước 1: Lấy fingerprint hiện tại
    current_fingerprint = get_isod_fingerprint()
    if not current_fingerprint:
        print("❌ Không lấy được fingerprint")
        return

    last_fingerprint = load_last_fingerprint()

    print(f"🔍 Fingerprint hiện tại : {current_fingerprint}")
    print(f"🔍 Fingerprint trước đó : {last_fingerprint}")

    if current_fingerprint == last_fingerprint:
        print(f"✅ Không có thông báo mới ({datetime.now().strftime('%H:%M:%S')})")
        return

    print("🆕 Fingerprint thay đổi! Đang lấy danh sách thông báo...")

    # Bước 2: Lấy headers
    data = get_isod_headers()
    if not data or "items" not in data:
        print("❌ Không lấy được danh sách thông báo")
        return

    items = data["items"]
    new_items = []

    for item in items:
        hash_id = item.get("hash")
        if hash_id and not is_hash_seen(hash_id):
            new_items.append(item)

    if new_items:
        print(f"🎉 Tìm thấy {len(new_items)} thông báo mới!")

        type_map = {
            "1000": "📢 Ogłoszenie",
            "1001": "📝 Sprawdzian",
            "1002": "⚠️ Ważne",
            "1003": "📊 Stan projektu",
            "1004": "🔄 Zmiana grupy",
            "1005": "✍️ Zapisy"
        }

        for item in new_items:
            type_text = type_map.get(item.get("type", ""), "📌")

            message = f"{type_text}\n\n"
            message += f"<b>{item.get('subject', 'Brak tytułu')}</b>\n\n"
            message += f"👤 {item.get('modifiedBy', 'Unknown')}\n"
            message += f"📅 {item.get('modifiedDate', 'Unknown')}\n"

            if item.get("noAttachments", 0) > 0:
                message += f"📎 Załączniki: {item['noAttachments']}\n"

            message += f"\n🔗 <a href='https://isod.ee.pw.edu.pl'>Xem trên ISOD</a>"

            send_telegram_message(message)

            # Lưu hash vào Redis ngay sau khi gửi
            # (tránh gửi lại nếu bot crash giữa chừng)
            mark_hash_seen(item.get("hash"))
    else:
        print("ℹ️ Fingerprint đổi nhưng không có hash mới (có thể thông báo đã thấy trước đó)")

    # Lưu fingerprint mới vào Redis
    save_fingerprint(current_fingerprint)

# ========== MAIN ==========
def check_redis_config():
    if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
        print("⚠️  CẢNH BÁO: Chưa set UPSTASH_REDIS_REST_URL hoặc UPSTASH_REDIS_REST_TOKEN!")
        print("⚠️  Bot sẽ mất trạng thái mỗi khi restart. Hãy thêm vào environment variables.")
        return False
    return True

def main():
    print("🚀 ISOD Telegram Bot đã khởi động!")
    print(f"👤 Username  : {ISOD_USERNAME}")
    print(f"⏰ Interval  : {CHECK_INTERVAL}s")

    redis_ok = check_redis_config()
    if redis_ok:
        print("✅ Redis đã được cấu hình — trạng thái sẽ được persist qua restart")

    send_telegram_message(
        f"✅ ISOD Bot đã khởi động!\n\n"
        f"⏰ Kiểm tra mỗi {CHECK_INTERVAL} giây\n"
        f"💾 Redis persist: {'✅' if redis_ok else '❌ Chưa cấu hình'}"
    )

    while True:
        try:
            check_isod_notifications()
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\n👋 Đang tắt bot...")
            send_telegram_message("👋 ISOD Bot đã tắt.")
            break
        except Exception as e:
            print(f"❌ Lỗi không mong muốn: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()