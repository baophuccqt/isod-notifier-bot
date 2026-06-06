# Deploy ISOD Bot lên server PW (cron mỗi 5 phút)

Bot chạy theo cơ chế **cron one-shot**: cứ mỗi 5 phút cron gọi `main.py --once`,
script kiểm tra ISOD 1 lần rồi thoát. Trạng thái (fingerprint + hash đã xem) lưu
trên Upstash Redis nên không bị gửi trùng giữa các lần chạy.

> Đặt sẵn biến cho gọn (chạy trên **máy Mac** của bạn). Thay bằng thông tin thật:
> ```bash
> SERVER="username@hostname.ee.pw.edu.pl"   # tài khoản SSH của PW
> APPDIR="~/isodBot"                          # thư mục đặt bot trên server
> ```

---

## Bước 1 — Thử đăng nhập SSH (trên Mac)

```bash
ssh "$SERVER"
```
- Nếu cần SSH key thì thêm `-i ~/.ssh/your_key`.
- Nếu trường yêu cầu VPN hoặc máy trung gian (jump host) mới vào được, báo mình
  để thêm `-J jumphost`.

Đăng nhập được rồi thì **gõ `exit`** để quay lại Mac, làm tiếp Bước 2.

## Bước 2 — Kiểm tra môi trường server (gõ trên server)

```bash
ssh "$SERVER"          # vào server
python3 --version       # cần Python 3.8+
```

Kiểm tra server có ra Internet được không (quan trọng nhất). Dùng Python stdlib —
**không cần curl/wget**:

```bash
python3 - <<'EOF'
import urllib.request, urllib.error, ssl
ctx = ssl.create_default_context()
targets = [
    ("telegram", "https://api.telegram.org"),
    ("isod",     "https://isod.ee.pw.edu.pl/isod-portal/wapi?"),
    ("upstash",  "https://novel-gibbon-68100.upstash.io"),
]
for name, url in targets:
    try:
        r = urllib.request.urlopen(url, timeout=10, context=ctx)
        print(f"{name}: {r.getcode()}  -> KET NOI OK")
    except urllib.error.HTTPError as e:
        print(f"{name}: HTTP {e.code} -> KET NOI OK (server tra loi la duoc)")
    except Exception as e:
        print(f"{name}: LOI -> {e}")
EOF
exit
```
- Mong đợi: telegram + isod hiện `KET NOI OK` (kể cả HTTP 404/302 đều OK).
- Nếu hiện `LOI -> ...` (timeout / Network unreachable / Name resolution) = bị chặn
  outbound → báo mình, ta chuyển sang lưu trạng thái bằng file local thay Upstash,
  hoặc tính phương án khác.

> Cách dự phòng chỉ cần `bash` (không cần Python/curl):
> ```bash
> for hp in api.telegram.org:443 isod.ee.pw.edu.pl:443 novel-gibbon-68100.upstash.io:443; do
>   timeout 5 bash -c "cat < /dev/null > /dev/tcp/${hp/:/\/}" && echo "$hp: OK" || echo "$hp: FAIL"
> done
> ```

## Bước 3 — Copy code lên server (trên Mac)

```bash
rsync -avz \
  --exclude venv --exclude .git --exclude __pycache__ \
  --exclude '*.pyc' --exclude .DS_Store --exclude bot.log \
  ~/Documents/isodBot/ "$SERVER:$APPDIR/"
```
> Lưu ý: `.env` **được** copy (chứa secrets, cần cho Redis). Đừng đưa `.env` lên
> git/public repo.

## Bước 4 — Tạo virtualenv + cài thư viện (trên server)

```bash
ssh "$SERVER"
cd ~/isodBot
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```
- Nếu `pip install` lỗi mạng (không ra được pypi.org), thử thêm proxy của trường,
  hoặc báo mình.

## Bước 5 — Chạy thử 1 lần (trên server)

```bash
cd ~/isodBot
chmod +x run.sh
./venv/bin/python main.py --once     # chạy trực tiếp, xem log ngay trên màn hình
```
- Xem có dòng `🔍 Fingerprint hiện tại ...`. Lần đầu thường sẽ thấy "fingerprint
  thay đổi" và có thể bắn vài thông báo cũ về Telegram (bình thường — sau đó các
  hash được đánh dấu đã xem, lần sau im).
- Chạy thử qua wrapper (giống hệt cron sẽ gọi):
  ```bash
  ./run.sh
  cat bot.log
  ```

## Bước 6 — Cài cron mỗi 5 phút (trên server)

```bash
crontab -e
```
Thêm dòng sau (sửa lại đường dẫn tuyệt đối cho đúng — KHÔNG dùng `~` trong cron):

```cron
*/5 * * * * /home/USERNAME/isodBot/run.sh
```
> Lấy đường dẫn tuyệt đối bằng `cd ~/isodBot && pwd`.

Lưu & thoát. Kiểm tra đã lưu:
```bash
crontab -l
```

## Bước 7 — Theo dõi hoạt động

```bash
tail -f ~/isodBot/bot.log     # xem log chạy real-time (Ctrl+C để thoát)
```
- Mỗi 5 phút sẽ có 1 block log mới `===== thời gian =====`.

---

## Bảo trì

- **Tạm dừng bot:** `crontab -e` rồi xoá dòng `*/5 ...` (hoặc thêm `#` đầu dòng).
- **Cập nhật code:** chạy lại lệnh `rsync` ở Bước 3 từ máy Mac. Không cần cài lại venv
  trừ khi đổi `requirements.txt`.
- **Xem bot có lỗi không:** `grep ❌ ~/isodBot/bot.log`.
- **Đổi tần suất:** sửa `*/5` (vd `*/10` = 10 phút).

## Bảo mật (nên làm sau khi chạy ổn)

Token Telegram, API key ISOD, token Upstash đang hardcode trong `main.py` (đã commit
git) và trong `.env`. Nên:
1. Tạo lại (rotate) Telegram bot token qua @BotFather, tạo lại Upstash token, đổi
   ISOD API key nếu portal cho phép.
2. Xoá các giá trị hardcode trong `main.py`, chỉ đọc từ `.env`.
3. `.gitignore` đã chặn `.env` khỏi git từ giờ.
