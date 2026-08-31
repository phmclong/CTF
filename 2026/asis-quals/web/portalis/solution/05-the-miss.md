# 05 — Vì sao bỏ sót port 9001 qua 3 phiên

Phân tích lỗ hổng phương pháp — phần có giá trị nhất của challenge này.

## Service ẩn là gì

`media-metadata service` bind **chỉ IPv4 loopback** (`127.0.0.1:9001`) trong
cùng container với app. Nó trả:

```
GET /     → 200 "media-metadata service\nGET /flag"
GET /flag → 200 "ASIS{Y0U_WeR3nT_SuPp0$eD_To_S3E_Th1S_P0rT@L}"
```

## Lỗi 1: scan bằng IPv6 loopback cho một service IPv4

Phiên 3 (file `3.md`) đã quét "57 port qua `[::1]` và `[::ffff:]`" — nhưng
nhìn danh sách port thực tế đã dùng: không có 9001. Và phần quét qua
`[::ffff:]` bị nhiễu bởi hai vấn đề dưới đây nên không đáng tin kết quả âm tính.

**Bài học:** `[::1]` (IPv6 loopback) và `[::ffff:127.0.0.1]` (IPv4-mapped) là
**hai không gian loopback khác nhau**. Service bind `127.0.0.1` (mặc định của
`server.listen(port)` không host trong nhiều stack) vô hình với scan IPv6.
Loopback scan phải quét cả hai giao thức.

## Lỗi 2: stale-preview làm kết quả scan sai

Phiên 2 (file `2.md`) tự ghi nhận: "đọc preview chỉ được 502 nginx hoặc kết quả
cũ". Khi URL fetch mới chưa xong, preview trả **kết quả fetch trước đó** —
scan tuần tự các port mà không verify "kết quả này thuộc URL hiện tại" sẽ đọc
nhầm: port đang đóng nhưng hiện lỗi của port trước. Một service "mở" dễ bị
đọc thành "đóng".

**Bài học:** oracle dạng poll-fetch phải gắn URL marker duy nhất vào mỗi probe
và chỉ công nhận kết quả nhắc đúng marker đó.

## Lỗi 3: gateway spoof RST → dừng scan quá sớm

Mọi IP không routable đều trả ECONNREFUSED (xem 03-ssrf.md). Cảm giác "mạng
trống rỗng, chỉ có app" hình thành từ tín hiệu RST giả — trong khi service
thật nằm ngay loopback, không đi qua gateway nào cả.

**Bài học:** trên network có middlebox phản hồi thay (RST spoof), kết luận
âm tính từ connect-error là vô giá trị. Chỉ HTTP response thật mới là bằng chứng.

## Lỗi 4: hai mồi hút 100% attention vào route-fuzz

- `/api/flag` với flag tự xưng "decoy" — route THẬT, gate THẬT, để người chơi
  đốt thời gian bypass header
- `robots.txt` nêu `/internal-metadata` — route KHÔNG tồn tại, đặt tên gần
  service thật (`media-metadata`) một chữ

Khoảng 500 phép thử fuzz (45 params + 33 headers + 74 paths + method/body +
variant tên) đổ vào hai mồi này. Trong khi đó service thật không cần một phép
fuzz nào — chỉ cần một GET tới đúng `:9001`.

**Bài học:** khi đề cho artifact "internal" (robots, flag giả), luôn hỏi:
liệu có LỚP KHÁC của "internal" không (port, giao thức, interface) thay vì chỉ
tìm route ẩn trên cùng cổng 3000.

## Lỗi 5 (nhỏ): tinHint sai tầng

Hint "search for some open ports" ban đầu được diễn giải thành: (a) port public
IP — quét toàn dải, chỉ thấy noise 2000/5060; (b) port container khác — không
có container thứ hai. Cả hai đúng phương pháp nhưng sai tầng: port cần tìm
nằm **trong chính container app**, tầng loopback, gần như tầng thấp nhất.

## Sửa lại checklist cho lần sau

1. Loopback scan: **cả `[::1]` và `[::ffff:127.0.0.1]`**, danh sách port ≥130
   (hoặc 1-65535 nếu oracle rẻ)
2. Mỗi probe gắn marker riêng; chỉ tin kết quả khớp marker
3. Sau probe vào host có thể DROP: reset oracle về URL refused-nhanh
4. Trước khi tin "host chết": control-test với IP chắc chắn không tồn tại
5. Decoy route ≠ dấu hiệu route thật ở cùng chỗ — nghĩ tầng khác (port/proto)
