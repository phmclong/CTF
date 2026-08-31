# 01 — Recon: robots.txt và lab-notes.html

## Bề mặt

Game 2048 theme Rick & Morty ("Citadel Grid", node C-137), Tomcat 9.0.116. Các endpoint:

- `/` — static HTML + `js/game.js` + `js/app.js` (game client thuần)
- `/leaderboard.jsp` — GET trả JSON 20 entry, POST nhận JSON `{name, score, event}`
- `/quote.jsp` — quote ngẫu nhiên 12s/lần
- `/mirror.jsp` — "intranet mirror" (link ở footer)
- `/css/style.css`

Leaderboard đầy 999999999 — các player khác đều RCE rồi. Nhiều name là **EL injection thử nghiệm** (`initParam.flag`, `header.host`, `cookie.JSESSIONID`...) hiển thị literal — xem [99-dead-ends.md](99-dead-ends.md).

## Flag giả #1 — HTML comment

```html
<!-- TODO(staff): before the next citadel audit rotate the staging code -> ASIS{lo0k_at_t41s_scr1pt_kiddi3} -->
```

Tên flag tự phê "scr1pt_kiddi3" — mồi cho người chỉ view-source.

## robots.txt

```
User-agent: *
Disallow: /citadel/
Disallow: /citadel/lab-notes.html
Disallow: /admin/

# garage journal got swept last cycle.
# w-w-was there another door into the intranet? like a diagnostics thing?
```

- `/admin/` = trang login fake, nút bấm hiện "logins disabled since the Jerry incident"
- Comment cuối **gợi ý trực tiếp** phải tìm "diagnostics" door

## /citadel/lab-notes.html — bản đồ challenge

8 entry = design doc của toàn bộ attack chain:

| Entry | Nội dung | Ý nghĩa exploitation |
|---|---|---|
| 001 | "garage gateway... TCP **four-thousand** (4000)... never answers back, it just listens" | port để gửi payload |
| 002 | "**AES, CBC mode, PKCS#5**... Only I know the fluid key" | giao thức seal |
| 003 | "if a parcel's **seal fails inspection**, the inspector grumbles and stamps it FAILED TO DECRYPT... **but ships it downstairs anyway**" | 🔑 seal hỏng vẫn được xử lý = bypass EncryptInterceptor |
| 004 | "**old commons merge library from '01**... it merges anything" | commons-collections 3.2.1 = deserialization gadget |
| 005 | launch code chia 2: **/opt/citadel/vault** + **/opt/citadel/gate**, "randomized label", read-only | phải đọc cả 2 thư mục |
| 006 | **/opt/citadel/shared** world-writable; "pulled through /mirror.jsp?parcel=<label>"; parcels one-shot; janitor sweep 15 phút | kênh exfil |
| 007 | "diagnostics console... same directory as the mirror window... only answers **from inside the garage**. Anything sitting in front of it (proxy, balancer...) is simply **trusted to tell the truth**" + coffee stain "headers" | 🔑 spoof IP qua header |
| 008 | coffee stain: "version numbers, a **CVE-shaped doodle of a tomato-cat**" | Tomcat CVE (t0mcat = tomato-cat) |

Entry 008 + 003 + 004 ghép lại = **CVE-2026-34486** (Tribes EncryptInterceptor bypass → deserialization RCE), đúng version 9.0.116 nằm trong affected range 9.0.0.M1–9.0.116.
