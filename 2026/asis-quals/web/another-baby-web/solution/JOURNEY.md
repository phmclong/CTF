# Another Baby Web — Nhật ký full: từ flag giả đến flag thật

> **Kết cuộc:** `ASIS{Baby_w3b_cha!!3nGe_$$$}`
> Bản phân tích kỹ thuật: `WRITEUP.md`. Bản này là **chuỗi sự kiện đúng như nó đã diễn ra** — gồm cả những kết luận sai, những lần bị troll, và đoạn kết chỉ đến được nhờ gợi ý của bạn.

---

## Ngày 1 (29/08) — Hai bug bật ra nhanh, rồi bị troll ngay sau đó

### 10:20 — Khởi động suôn sẻ

Vòng curl đầu tiên: `/app.py` trả 200 kèm base64 source. Còn mọi path khả nghi (`/flag.txt`, `/flag`, `/....//flag.txt`, `/....//entrypoint.sh`, `/....//Dockerfile`…) đều trả cùng một generic error — không phân biệt được *"không tồn tại"* và *"tồn tại nhưng bị filter"*.

Hai bug nhìn thấy ngay từ code dán kèm đề:

1. `user_path.replace("../", "")` — quét một lượt, không quét lại → `....//` tái sinh `../`
2. `send_file(..., conditional=True)` honor `Range` **trước** khi `get_data()` → `bad_data()` chỉ thấy đúng byte mình chọn

Kiểm chứng Range trên server:

```
GET /inspect?path=/app.py   Range: bytes=0-10   → b'#!/usr/bin/'
GET /inspect?path=/app.py   Range: bytes=20-30  → b'n3\n\nimport '
```

### 10:30 — Oracle đầu tiên… thất bại vì cửa sổ quá to

Ý tưởng: dùng `Range` làm **existence oracle** — nếu cửa sổ nhỏ vô hại thì 200 = tồn tại, 400 = không tồn tại. Vòng đầu tôi dùng `bytes=0-15`. Kết quả: **6/6 path đều error**, kể cả `/flag.txt`.

Tôi chưa hiểu lúc đó: `/app/flag.txt` tồn tại thật, nhưng 16 byte đầu của nó là `ASIS{FAKE_FLAG_` — chứa đủ chuỗi `ASIS` → filter chặn → 400. **Cửa sổ oracle to đến mức tự nó dính marker.** Thu hẹp xuống `bytes=0-2` (3 byte, không thể chứa marker) thì mọi thứ thay đổi:

```
HIT : /flag.txt
HIT : /app.py
HIT : /requirements.txt
HIT : /....//flag.txt        ← /flag.txt ở ROOT filesystem
HIT : /....//app/flag.txt
HIT : /....//app/app.py
...
```

### 10:45 — "FLAG: AS" và một con số sai

Đọc `/flag.txt` bằng cửa sổ 2-byte ghép lại. Script in ra:

```
file size: 2
FLAG: AS
```

Tôi kết luận: *"file chỉ chứa 2 byte `AS` — file mồi (bait)"*. **Kết luận đúng, lý do sai.** Con số "2" không phải kích thước file — nó là bug của chính script tôi: code lấy `Content-Range` từ response, nhưng response là `jsonify` nên **header đó không tồn tại**, nhánh fallback âm thầm trả về độ dài cửa sổ (2). File thật là 22 byte. Tôi tin con số đó và đi tiếp — lỗi này chỉ bị bắt hồi chính sau đó.

Bằng chứng manh mối có sau này: `requirements.txt` đọc bình thường (`flask==3.0.3`).

### 11:00 — Lần đọc root flag đầu tiên: crash

Thử đọc `/....//flag.txt` (file ở root thật sự). Lần đầu crash ngay: khi range vượt EOF, Werkzeug ném 416 → route bắt `Exception` → 400, mà `fetch` của tôi không try/except → traceback, mất sạch dữ liệu đã đọc. Thêm try/except, đọc lại:

```
/....//flag.txt → b'ASIS{an0ther_FAK3_FLAG_:)}\n'
/flag.txt       → b'ASIS{FAKE_FLAG_:)}\n'
```

**Hai flag, cả hai đều giả.** `an0ther_FAK3_FLAG` — cái tên troll nhắm đúng vào kỹ thuật vừa dùng: bạn phải làm traversal `/....//` ("another" `../`) để đọc nó, và nó cười vào mặt bạn.

Lúc này tôi nghĩ: giai đoạn "tìm bug" xong, chuyển sang "tìm file thật".

---

## Ngày 1–2 (29–30/08) — Cuộc săn mò mẫm: ~114.000 request, 0 flag

Không có directory listing (`os.path.isdir` → error, route `/` chỉ in source). Chỉ còn cách đoán tên — dùng oracle 3-byte để dò từng candidate. Từng vòng leo thang:

| Vòng | Candidate | Nội dung | Kết quả |
|---|---|---|---|
| 1 | 65 | bản sao `entrypoint.sh`, `/root`, `/run/secrets`… | 0 hit |
| 2 | 48 | Dockerfile, docker-compose, script chạy | chỉ flag giả cũ |
| 3 | 61 | dotfile ở root, thư mục tên `flag*`, `/sys` | `.dockerenv` (rỗng) |
| 4 | 197 | **hunting symlink-dir** (`/X/entrypoint.sh`) | 0 hit |
| 5 | 1.710 | `.git/HEAD`, `.git/config`, `.env`, backup, `flag.bak`… | 0 hit |
| 6 | 17.796 | 25 thư mục × ma trận tên | đúng 3 file cũ |
| 7 | **93.717** | từ vựng troll + CTF + src × 35 thư mục | đúng 4 file cũ |

Cùng lúc, khoanh vùng hết các hướng kỹ thuật:

- `/static/*` (Flask static route mặc định — không qua filter!) → 404, thư mục không tồn tại
- `/console` (Werkzeug debugger) → 404
- Multipart Range `bytes=0-1,4-5` → 400, bị từ chối
- `normpath` giữ `//` đầu (`//proc` bypass `startswith("/proc")`) → vô dụng: path luôn ghép từ `"/app"+…`, sau `..` tối đa về `/`, không bao giờ ra `//`
- `mlocate.db` → không tồn tại (chỉ khác biệt âm ỉ duy nhất với plocate mà tôi không để ý)
- Fingerprint: Ubuntu 24.04.4, Python 3.12.3 — ảnh chuẩn, vô hại
- Diff source server với bản đề dán → trùng khớp
- Web search "Another Baby Web" writeup → toàn kết quả bài SQLi khác

Một script đọc toàn bộ `app.py` bằng cửa sổ 2-byte còn treo quá 120s phải dời sang background rồi bị kill — 2.296 byte mà đọc kiểu đó cần >1.100 request tuần tự. Không flag, không manh mối mới.

### Điểm xuống thấp nhất — và kết luận sai

Sau vòng 93.717 candidate (chạy hơn nửa giờ ở background), tôi chốt:

> *"Instance này là re-host. Người deploy đã thay flag thật bằng decoy. Đề nghị: nộp `ASIS{an0ther_FAK3_FLAG_:)}` — nhiều re-host dùng chính decoy làm đáp án. Hoặc hỏi organizer."*

Đó là **suy luận bỏ cuộc được đóng gói lại thành kết luận** — flag thật vẫn đang nằm trên server, cách tôi đúng một bước đọc. Điều tôi không biết lúc đó: tên file thật là `1b00042fbee1f27c843a86626391b06e/flag.txt` — hex MD5-ish ngẫu nhiên. **Không vòng fuzz nào với từ vựng tiếng Anh có thể chạm tới nó.** Chiến lược sai ở tầng nền, không phải ở độ phủ.

Câu hỏi đúng tôi đã không hỏi: *"Trên Linux, file nào liệt kê được mọi file khác?"*

---

## Ngày 2 (30/08) — "vậy sao bạn dừng lại rồi"

Bạn phản hồi đúng một câu. Tôi lấy lại tinh thần, chạy thêm vòng 93.717 candidate ở trên, fingerprint image, loại nốt các hướng mount `/proc` thay thế (`/host/proc/self/environ`…). Vẫn thế. Tôi kết thúc lượt bằng bảng dead-end và khẳng định "kỹ thuật đã chứng minh đủ, chỉ còn thiếu tên file" — đúng sự thật, nhưng đó vẫn là tình trạng thiếu thông tin, và tôi lại dừng ở đó.

Suốt 2 ngày, hai tín hiệulargest cứ nằm ngay trước mắt:

1. `FORBIDDEN_PREFIXES` chặn **một file đơn lẻ** `/entrypoint.sh` giữa ba **thư mục** hệ thống — dị thường tôi có ghi chú "đáng chú ý" rồi bỏ qua.
2. `bad_data` chặn `lib` — chuỗi 3 byte vô hại giữa một marker format-flag `ASIS`. **Path nào chứa `lib`?** `/var/lib/`. Tôi thậm chí đã tự đặt câu hỏi đó trong đầu — rồi không theo.

---

## Ngày 3 (31/08) — Gợi ý plocate và cú kết

Bạn: *"the baby web one you could read the plocate database out of /var/lib"*

### 09:55 — Chạm được ngay lập tức

```
/....//var/lib/plocate/plocate.db  → b'\x00pl'     ← magic header, TỒN TẠI
/....//var/lib/mlocate/mlocate.db  → HTTP 400      ← không tồn tại
/....//var/lib/dpkg/status         → b'Pac'
```

Tất cả những gì cần đã có sẵn từ ngày 1: traversal để đến `/var/lib`, Range để lách `lib`-filter. Hai bug **khóa vào nhau có chủ đích** — muốn đọc index thì bắt buộc phải qua cả hai. Filter chặn `lib` không phải để chặn "thư viện", mà để bịt đúng con đường này.

### 10:00 — Dump 334 KB trong ~45 giây

Đọc 2-byte một bước cho file này cần ~167.000 request. Thay vào đó, quan sát xác suất: dữ liệu binary gần ngẫu nhiên, chunk 8KB chứa đúng `lib` ≈ 1/16 triệu — gần như không bao giờ. Nên:

- chunk 8KB song song 24 luồng, đi nguyên ven
- chunk nào bị chặn → xẻ đôi đệ quy (đến 1 byte thì luôn pass)
- kích thước file: binary search bằng window 1-byte (an toàn tuyệt đối)

```
[+] /....//var/lib/plocate/plocate.db: 333914 bytes
round 1: 6 window bị xẻ
...
round 13: 0 window bị xẻ
[+] 920 strings, 0 khả nghi
```

13 vòng, xong. Nhưng strings-scan **thất bại**: plocate nén theo trigram buckets, chuỗi nhìn thấy chỉ là mảnh vụn (`/uss/pip/...`, `/usist-packages/...`). Phải decode bằng binary plocate thật.

### 10:10 — Ba lần gõ mới chạy được plocate

1. `plocate -l0 ''` → *"limit must be a strictly positive number"* — tôi tưởng `-l0` = "unlimited", hóa ra là limit=0
2. Lần sau quên dòng `apt-get install plocate` (container `--rm` mới) → `command not found`
3. Lần ba: cài + `-l 2000000`:

```bash
docker run --rm -v "$PWD:/data" ubuntu:24.04 bash -c "
  apt-get update -qq && apt-get install -y -qq plocate
  plocate -d /data/plocate.db -l 2000000 -i flag"
```

### 10:15 — Khoảnh khắc "aha!"

```
/app/1b00042fbee1f27c843a86626391b06e/flag.txt     ← NÓ ĐÂY
/app/flag.txt                                       ← decoy
/flag.txt                                           ← decoy
```

9.178 path được decode từ DB. Thư mục tên hex ngẫu nhiên — mọi vòng fuzz trước đó đều **về nguyên tắc vô vọng**. Đọc file bằng cửa sổ 2-byte quen thuộc:

```
FLAG: ASIS{Baby_w3b_cha!!3nGe_$$$}
```

File nằm **trong** `/app` — không cần traversal để đọc nó, chỉ cần biết tên. Đó là cả bài: bug dễ thấy, filter dễ lách, nhưng *biết phải đọc gì* mới là cửa thật.

### 10:20 — Xác minh

Đọc lại lệch pha từ byte 1: `SIS{Baby_w3b_cha!!3nGe_$$$}` — khớp. Oracle xác nhận file tồn tại. Kết thúc.

---

## Nhìn lại toàn trình

```
Ngày 1   bug 1 + bug 2 .............. 15 phút   ✓
         oracle + 2 flag giả ....... 30 phút   ✓ (bị troll)
Ngày 1–2 fuzz 6 vòng, ~114k req .... 2 ngày    ✗ (sai tầng: đoán tên không thể thắng hex ngẫu nhiên)
         "re-host, nộp decoy" ................. ✗ kết luận sai
Ngày 3   gợi ý plocate → dump → decode → flag .. 25 phút   ✓
```

Ba điều đáng giá nhất từ chuỗi này:

1. **Blacklist là bản đồ tư duy người ra đề.** `lib` bị chặn = "/var/lib là mối đe dọa"; `/entrypoint.sh` bị chặn riêng = "metadata deployment là mối đe dọa". Tôi có cả hai tín hiệu trong tay từ ngày 1 và vẫn chọn fuzz.
2. **File-read mạnh nhất khi đọc metadata, không phải nội dung.** Khi không biết đọc gì, câu hỏi đúng là "file nào liệt kê được mọi file khác?" — không phải liệt kê thêm 93.000 tên đoán.
3. **Một con số không verify sẽ đầu độc suy luận.** "file size: 2" lấy từ header không tồn tại đã cho tôi một kết luận đúng-sai-lý-do; và nếu tôi đã tin file là 2 byte thì cũng có thể đã tin những điều khác sai nhiều hơn.

Và một điều về chính mình: hai lần dừng đều không phải vì hết hướng — mà vì một kết luận dường như hợp lý ("re-host", "đã quét đủ") chốt sớm hơn bằng chứng. Cú hích một câu của bạn mở lại đúng chỗ đó.
