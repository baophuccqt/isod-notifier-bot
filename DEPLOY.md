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

## Bước 4 — Cài thư viện (trên server)

> Server dùng **Python 3.6.9** nên `requirements.txt` đã ghim `requests==2.27.1`
> (bản cuối còn hỗ trợ 3.6) và bỏ `python-dotenv` (code tự đọc `.env`).

```bash
ssh "$SERVER"
cd ~/isodBot
python3 -m venv venv
./venv/bin/pip install --upgrade "pip<22"     # pip mới đã bỏ Python 3.6
./venv/bin/pip install -r requirements.txt
```

- Nếu `python3 -m venv venv` báo lỗi (thiếu gói `python3-venv`, không có sudo) →
  bỏ qua venv, cài vào thư mục home của bạn:
  ```bash
  python3 -m pip install --user -r requirements.txt
  ```
  `run.sh` đã tự nhận biết: không có venv thì dùng `python3` hệ thống.
- Nếu `pip install` lỗi mạng (không ra được pypi.org) → thử proxy của trường hoặc báo mình.

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

## Cách 2 — Deploy bằng GitHub Actions (không cần server riêng)

Thay vì cron trên server PW, có thể để **GitHub tự dựng máy ảo Ubuntu mỗi 5 phút**,
chạy `main.py --once` rồi tắt. Miễn phí, không cần SSH/VPN. Trạng thái vẫn lưu trên
Upstash Redis — máy ảo bị xoá sau mỗi lần chạy nên **bắt buộc** dùng Redis (file
`last_fingerprint.txt` / `seen_hashes.json` sẽ không được giữ lại).

Đã có sẵn 2 workflow trong `.github/workflows/`:
- `check.yml` — chạy bot mỗi 5 phút (và bấm chạy tay được).
- `keepalive.yml` — tạo 1 commit rỗng mỗi tháng. GitHub tự tắt scheduled workflow nếu
  repo **không có commit nào trong 60 ngày** (workflow chạy KHÔNG tính là hoạt động,
  chỉ commit mới tính), nên file này giữ cho bot chạy mãi mà không phải tự đụng tay.

### B1 — Khai báo Secrets (KHÔNG để token trong code)

Trên GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
Tạo đúng 6 cái tên dưới đây (giá trị lấy từ `.env`):

| Secret | Nội dung |
|---|---|
| `ISOD_USERNAME` | username ISOD |
| `ISOD_API_KEY` | API key ISOD |
| `TELEGRAM_BOT_TOKEN` | token bot Telegram |
| `TELEGRAM_CHAT_ID` | chat ID Telegram |
| `UPSTASH_REDIS_REST_URL` | URL Upstash Redis |
| `UPSTASH_REDIS_REST_TOKEN` | token Upstash Redis |

> Tên secret phải khớp y hệt — đây là tên `main.py` đọc qua `os.environ.get(...)`.

### B2 — Bật quyền ghi cho keepalive

**Settings → Actions → General → Workflow permissions** → chọn
**"Read and write permissions"** → Save. (Để `keepalive.yml` push được commit rỗng;
nếu không, keepalive sẽ lỗi 403.)

### B3 — Push code lên GitHub

```bash
git add main.py .github/workflows/
git commit -m "deploy qua github actions"
git push
```

### B4 — Chạy thử

Tab **Actions** → workflow **"ISOD Notifier"** → **Run workflow**. Mở log step
"Run checker (one-shot)" xem có lỗi không. Sau đó cứ mỗi ~5 phút nó tự chạy.

> Cron của GitHub **không đúng giờ tuyệt đối**, lúc tải cao có thể trễ 5–15 phút —
> đây là giới hạn của GitHub, không phải lỗi bot.

---

## Bảo trì

- **Tạm dừng bot:** `crontab -e` rồi xoá dòng `*/5 ...` (hoặc thêm `#` đầu dòng).
- **Cập nhật code:** chạy lại lệnh `rsync` ở Bước 3 từ máy Mac. Không cần cài lại venv
  trừ khi đổi `requirements.txt`.
- **Xem bot có lỗi không:** `grep ❌ ~/isodBot/bot.log`.
- **Đổi tần suất:** sửa `*/5` (vd `*/10` = 10 phút).

## Bảo mật

### Sự cố đã xảy ra (04/09/2026)

Token Telegram bị hardcode trong `isod_bot.py` từ commit đầu tiên và trong `main.py`
tới `28f3b7c`. Repo để **public** → bot quét GitHub nhặt được token và chiếm bot: chúng
gọi `setMyName` / `setMyDescription` / `setMyPhoto` để biến bot thành quảng cáo cho một
bot VPN (có lúc đổi tên thành "AI PORN", có lúc thành "#FREEVPN … @vpn38_bot"). Username
`IsodNotifier_bot` không bị đổi vì việc đó chỉ làm được qua BotFather.

Đã xử lý xong:
1. ✅ Revoke token qua `@BotFather` — token cũ giờ trả `401 Unauthorized`.
2. ✅ Tạo lại ISOD API key trên portal.
3. ✅ Khôi phục tên / mô tả / ảnh đại diện của bot.
4. ✅ Cập nhật secret mới vào `.env` và GitHub Secrets.
5. ✅ Xoá hẳn `isod_bot.py` — bản cũ trùng lặp, không ai chạy mà vẫn ôm secret
   (`main.py` đã gỡ hardcode từ `28f3b7c`). `Procfile` chuyển sang `main.py`.

### Quy tắc từ giờ

- Secret **chỉ** đọc từ biến môi trường: `.env` khi chạy local, GitHub Secrets khi chạy
  Actions. `main.py` có `check_required_env()` — thiếu biến thì thoát ngay kèm thông báo
  rõ, chứ không im lặng chạy sai.
- Chỉ giữ **một** entry point là `main.py`. Đừng nhân bản script ra file thứ hai: mỗi bản
  sao là thêm một chỗ có thể lọt secret.
- `.env` nằm trong `.gitignore`. Cần thêm biến mới thì khai báo tên (không kèm giá trị)
  trong `.env.example`.
- Token Upstash chưa từng bị commit → không cần rotate.

⚠️ Lịch sử git vẫn còn token cũ (`git log -p` moi ra được) và GitHub vẫn giữ commit cũ
truy cập qua SHA kể cả sau khi rewrite. Vì đã rotate nên các giá trị đó thành vô hại;
nếu muốn sạch hẳn thì để repo private hoặc xoá rồi tạo lại repo.
