import requests
import json
import time
from datetime import datetime

# ========== CẤU HÌNH ==========
TELEGRAM_BOT_TOKEN = "8243204723:AAHYnvEoYdT7WRm6CjN0tohw1qtXIaDZoN0"  # Thay bằng token của bạn
TELEGRAM_CHAT_ID = "6850792800"  # Thay bằng chat_id của bạn

ISOD_USERNAME = "nghiabaophuc.ho"
ISOD_API_KEY = "odoaVcuhIdEDvPVmHPWCqA"
ISOD_BASE_URL = "https://isod.ee.pw.edu.pl/isod-portal/wapi?"

CHECK_INTERVAL = 600  # 10 phút
FINGERPRINT_FILE = "last_fingerprint.txt"
SEEN_HASHES_FILE = "seen_hashes.json"

# ========== HÀM TELEGRAM ==========
def send_telegram_message(message):
    """Gửi tin nhắn qua Telegram"""
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

# ========== HÀM ISOD ==========
def get_isod_fingerprint():
    """Lấy fingerprint từ ISOD"""
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
    """Lấy danh sách thông báo (headers only)"""
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

def get_isod_full_content(hash_id):
    """Lấy nội dung đầy đủ của một thông báo"""
    params = {
        "q": "mynewsfull",
        "username": ISOD_USERNAME,
        "apikey": ISOD_API_KEY,
        "hash": hash_id
    }
    
    try:
        response = requests.get(ISOD_BASE_URL, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("items"):
                return data["items"][0]
        return None
    except Exception as e:
        print(f"❌ Lỗi lấy full content: {e}")
        return None

# ========== HÀM LƯU TRỮ ==========
def load_last_fingerprint():
    """Đọc fingerprint cuối"""
    try:
        with open(FINGERPRINT_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def save_fingerprint(fingerprint):
    """Lưu fingerprint"""
    with open(FINGERPRINT_FILE, 'w') as f:
        f.write(fingerprint)

def load_seen_hashes():
    """Đọc danh sách hash đã xem"""
    try:
        with open(SEEN_HASHES_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_seen_hashes(hashes):
    """Lưu danh sách hash đã xem"""
    with open(SEEN_HASHES_FILE, 'w') as f:
        json.dump(hashes, f)

# ========== HÀM CHÍNH ==========
def check_isod_notifications():
    """Kiểm tra thông báo mới từ ISOD"""
    
    # Bước 1: Check fingerprint
    current_fingerprint = get_isod_fingerprint()
    
    if not current_fingerprint:
        print("❌ Không lấy được fingerprint")
        return
    
    last_fingerprint = load_last_fingerprint()
    
    print(f"🔍 Fingerprint hiện tại: {current_fingerprint}")
    print(f"🔍 Fingerprint trước đó: {last_fingerprint}")
    
    # Nếu fingerprint không đổi → không có gì mới
    if current_fingerprint == last_fingerprint:
        print(f"✅ Không có thông báo mới ({datetime.now().strftime('%H:%M:%S')})")
        return
    
    print("🆕 Fingerprint thay đổi! Đang check thông báo mới...")
    
    # Bước 2: Lấy headers
    data = get_isod_headers()
    
    if not data or "items" not in data:
        print("❌ Không lấy được danh sách thông báo")
        return
    
    items = data["items"]
    seen_hashes = load_seen_hashes()
    
    new_items = []
    
    # Tìm thông báo mới
    for item in items:
        hash_id = item.get("hash")
        if hash_id and hash_id not in seen_hashes:
            new_items.append(item)
            seen_hashes.append(hash_id)
    
    # Nếu có thông báo mới
    if new_items:
        print(f"🎉 Tìm thấy {len(new_items)} thông báo mới!")
        
        for item in new_items:
            # Map type số sang text
            type_map = {
                "1000": "📢 Ogłoszenie",
                "1001": "📝 Sprawdzian",
                "1002": "⚠️ Ważne",
                "1003": "📊 Stan projektu",
                "1004": "🔄 Zmiana grupy",
                "1005": "✍️ Zapisy"
            }
            
            type_text = type_map.get(item.get("type", ""), "📌")
            
            message = f"{type_text}\n\n"
            message += f"<b>{item.get('subject', 'Brak tytułu')}</b>\n\n"
            message += f"👤 {item.get('modifiedBy', 'Unknown')}\n"
            message += f"📅 {item.get('modifiedDate', 'Unknown')}\n"
            
            # Nếu có attachments
            if item.get("noAttachments", 0) > 0:
                message += f"📎 Załączniki: {item['noAttachments']}\n"
            
            message += f"\n🔗 <a href='https://isod.ee.pw.edu.pl'>Xem trên ISOD</a>"
            
            # Gửi qua Telegram
            send_telegram_message(message)
        
        # Lưu danh sách hash đã xem
        save_seen_hashes(seen_hashes)
    
    # Lưu fingerprint mới
    save_fingerprint(current_fingerprint)

# ========== MAIN LOOP ==========
def main():
    """Hàm chính - chạy vòng lặp kiểm tra"""
    print("🚀 ISOD Telegram Bot đã khởi động!")
    print(f"👤 Username: {ISOD_USERNAME}")
    print(f"⏰ Kiểm tra mỗi {CHECK_INTERVAL} giây")
    
    # Gửi tin nhắn test
    send_telegram_message("✅ ISOD Bot đã sẵn sàng!\n\nBot sẽ thông báo khi có tin mới từ ISOD.")
    
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
