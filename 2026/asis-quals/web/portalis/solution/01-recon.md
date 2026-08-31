# 01 — Recon: cấu trúc site và manh mối đầu tiên

## Đề bài

> Rick was feeling bored and lonely, so he built Portalis: a convenient place to
> collect every identity, achievement, and questionable business venture on one
> page.
>
> Naturally, the site also **creates a polished preview whenever a profile is
> shared**. Rick claims this outdated system only uses approved profile details
> and that **anything behind the portal is none of your business**. Make yourself
> at home. Just **be careful where your profile points**.

Ba cụm đậm là ba mảnh hint chồng nhau:
- "creates a polished preview" → có pipeline server-side xử lý preview
- "be careful where your profile points" → URL trong profile bị fetch
- "anything behind the portal" → mục tiêu là service nội bộ ("behind the portal")

## Cấu trúc site

| Route | Vai trò |
|---|---|
| `/` | Home (link-in-bio theme Rick & Morty) |
| `/dashboard` | Form chỉnh theme + hộp "Advanced: raw theme JSON" gửi as-is |
| `/explore`, `/help`, `/about` | Trang tĩnh |
| `/u/<user>` | Portal công khai, chứa `<meta property="og:image">` |
| `/u/me` | Portal của session hiện tại |
| `/api/theme` | `PUT` — publish theme JSON (deep-merge) |
| `/api/preview` | `GET` — diagnostics plain-text của preview card |
| `/api/schema` | `GET` — schema field |

Front proxy: **nginx/1.31.4** (hiện 502 khi backend treo). Backend Node.js
(dấu vết undici trong error message sau này).

## Auth

**Không có.** Request `PUT /api/theme` đầu tiên tự tạo profile và set cookie
HttpOnly `sid=<32 hex>`. Mọi response (kể cả 404) đều set `sid` mới nếu chưa có.

## Manh mối quan trọng nhất: `/api/schema`

```json
{
  "settable": ["name", "bio", "accent", "avatarUrl", "links"],
  "rendered_context": ["name", "bio", "accent", "avatarUrl", "links", "ogImage"],
  "note": "ogImage is reserved and populated by the media pipeline; it is not accepted from theme input"
}
```

Bất đối xứng đáng chú ý: `ogImage` **nằm trong rendered_context** (được dùng khi
render) nhưng **không nằm trong settable** (bị cấm set trực tiếp), và được
"media pipeline" điền vào.

→ Nếu ta ép được `ogImage` vào profile bằng con đường khác (prototype
pollution qua deep-merge là ứng viên số 1), media pipeline sẽ fetch URL đó.
Đó chính là cửa SSRF.

## Trang Help tiết lộ cơ chế merge

> Sent as JSON to `PUT /api/theme`. Fields are **deep-merged into your existing
> profile** — omit a field to leave it unchanged.

Deep-merge + JSON người dùng kiểm soát = signature kinh điển của prototype
pollution nếu merge không bảo vệ `__proto__`/`constructor`.

## Trạng thái vận hành (gây khó khăn suốt quá trình)

Server `91.107.189.166:3000` chập chờn: lúc refused, lúc 200, lúc timeout.
Mọi script đều phải bọc retry 3-5 lần và chạy **tuần tự** (chết dưới tải song
song). Nginx trả 502 khi backend treo.
