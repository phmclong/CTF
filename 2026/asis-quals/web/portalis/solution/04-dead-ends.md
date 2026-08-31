# 04 — Các hướng đã chết (có bằng chứng)

Ghi lại đầy đủ để không đi lại. Mỗi mục đều đã được verify bằng control trước
khi kết luận âm tính.

## A. Hai "mồi" (decoy) của đề

### `/api/flag` + `X-Internal: 1` → flag giả

```bash
curl -H "X-Internal: 1" http://91.107.189.166:3000/api/flag
# → {"flag":"flag{decoy_this_endpoint_is_a_trap}"}   ← tự xưng là trap
```

Đã đốt quanh nó:

| Test | Kết quả |
|---|---|
| Gate so value chính xác chuỗi `"1"` (`01`, `true`, `2`, `abc`, rỗng → 403) | khớp literal |
| SSRF loopback `[::1]` không header | **vẫn 403** → gate là header, KHÔNG phải source-IP |
| SSRF từ `[::ffff:127.0.0.1]`, `172.18.0.3` (self), `172.18.0.2`, hostname `portalis` | 403 hết — không remote-address check |
| Query param (`?X-Internal=1`, `?internal=1`, ...) | 403/404 — không read query |
| `;`-path (`/api/flag;internal=1`), `%3F`-tricks | 404 |
| Method khác (POST/PUT/OPTIONS/HEAD) | 404 (strict method matching) |
| Header combo: XFF, X-Real-IP, Host variants, Authorization | vẫn flag mồi |
| UA rỗng / undici UA | không đổi |

### `robots.txt` → `Disallow: /internal-metadata` → route KHÔNG tồn tại

```
User-agent: *
Disallow: /internal-metadata
```

45 query params, 33 headers (X-Internal, X-Pipeline, XFF, Authorization...),
37 path variants (.json/.xml/.png, /api/-prefix), 6 method, 8 POST body,
Host-header matrix 10 biến thể, UA variants — **404 tuyệt đối mọi điều kiện**.
Tên gần-đúng `media-metadata` (service thật) là đánh lạc hướng chủ đích.

## B. Fetch options từ prototype (giả mạo method/headers của SSRF fetch)

Pollute `signal: "not-a-signal"`, `dispatcher: "x"` (giá trị sai kiểu — undici
ném TypeError nếu được spread vào options). Fetch vẫn chạy bình thường → app
build fetch options riêng, cứng. Cũng thử `method`, `fetchMethod`,
`httpMethod`, `redirect`, `timeout`, `headers` nhiều kiểu key — không ăn.

## C. Nhánh "image" của media pipeline

Pipeline in `is not an image` khi content-type không phải image → tồn tại nhánh
xử lý image thật, chưa từng kích hoạt. Đã thử:

- Static handler kín path traversal (nginx normalize → 400/404)
- Fuzz 20+ tên file image/favicon (favicon.ico, og.png, logo.svg, ...) → 404 hết
- Không endpoint nào trong network trả `image/*` → nhánh không thể kích hoạt

## D. Không có bot internal

Đặt `ogImage` = marker, đọc lại `/u/me` 3 lần cách 8s → diag không đổi. Dòng
`portal-diag` chỉ là fetch trực tiếp không header.

## E. Các vector khác

- **`links[]` render**: deep-merge biến array thành object `{"0":{...}}` →
  template không bao giờ render links (portal-links luôn rỗng)
- **XSS `name`/`bio`**: escape đúng; `accent` chèn vào `style=""` nhưng quote
  bị escape thành `&quot;`
- **Query param injection lên `/api/preview`** (`?url=`, `?ogImage=`...): không ăn
- **`avatarUrl` làm SSRF thứ hai**: set qua field chính danh → template KHÔNG
  render nó (avatar-circle render accent vào background, không có thẻ img).
  Không fetch. Map render đầy đủ: chỉ name/bio/accent/links/ogImage được dùng.
- **`/u/:user` ăn mọi subpath** (`/u/me/x/y` = 200 template thường) — không
  phải route thật
- **Pollute runtime keys** (28 key: status, headers, message, error, code, type,
  data, url, host, method, ...) với marker → không key nào leak vào response nào
- **Pollute `toString`/`valueOf`** crash-test (giá trị sai kiểu) → mọi route vẫn
  normal — không code path nào String()-ify object qua prototype
- **Redirect**: không route nào trả 3xx
- **Share-pipeline trigger**: GET /u/me ×2 + đợi 12s → profile không bị ghi
  ogImage. POST lên /u/me, /api/preview, /api/share, /api/card, /api/og,
  /api/render → 404 hết. "Media pipeline" không có trigger riêng — preview
  chính là pipeline.
- **Port scan public IP** (nmap từ ngoài, toàn dải 1-65535 + UDP): chỉ 22/3000
  ổn định. Port 2000/5060 mở đúng một lần scan đầu rồi biến mất (accept im
  lặng, không HTTP/TLS/banner) — nhiễu mạng, không khai thác được.
- **Subnet sweep** 172.16-21.x/10.x/192.168.x: toàn "ALIVE" giả do gateway
  spoof RST (xem 03-ssrf.md)
