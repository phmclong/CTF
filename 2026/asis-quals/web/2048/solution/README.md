# Citadel Grid — Multiverse 2048 (ASIS CTF)

**Target:** `http://91.107.164.78:8080` — Tomcat 9.0.116, JSP app
**Độ khó:** medium — chuỗi 5 bước, mỗi bước có một manh mối riêng
**Kết quả:** ✅ Flag: `ASIS{t0McAT_was_Th3_KEY}`

## TL;DR — Attack chain

```
robots.txt → lab-notes.html (bản đồ challenge)
  → X-Forwarded-For: 127.0.0.1 bypass /diagnostics.jsp (xác nhận CC 3.2.1 + Tribes :4000)
    → CC6 gadget (commons-collections 3.2.1) tự build
      → Tribes ChannelData frame gửi vào TCP 4000 (bypass EncryptInterceptor, seal hỏng vẫn deserialize)
        → RCE → ls /opt/citadel vào /opt/citadel/shared
          → /mirror.jsp?parcel=<label> đọc exfil
            → cat vault/flag.txt + gate/launch_*.conf → flag
```

## Các file

| File | Nội dung |
|---|---|
| [01-recon.md](01-recon.md) | Flag giả trong HTML comment, robots.txt, lab-notes |
| [02-diagnostics-bypass.md](02-diagnostics-bypass.md) | XFF spoof vào console nội bộ |
| [03-deserialization.md](03-deserialization.md) | CC6 gadget + bug LazyMap cache + wrapper lệnh |
| [04-tribes-delivery.md](04-tribes-delivery.md) | Framing Tribes đúng chuẩn, CVE-2026-34486 |
| [05-exfiltration.md](05-exfiltration.md) | mirror.jsp 2 chặng, lấy flag |
| [99-dead-ends.md](99-dead-ends.md) | Các lối chết đã loại bỏ (tiết kiệm thời gian làm lại) |
| [exploit/](exploit/) | Toàn bộ code: Gen.java, TribesSend.java, lệnh chạy |

## Hai flag tìm thấy

| Flag | Vị trí | Ghi chú |
|---|---|---|
| `ASIS{lo0k_at_t41s_scr1pt_kiddi3}` | comment HTML trang chủ | **decoy** — "script kiddie" tự nói |
| `ASIS{do_you_think_rick_sanchez_is_stupid?}` | vault/flag.txt | **decoy** — tên biến là câu châm chọc |
| `ASIS{t0McAT_was_Th3_KEY}` | gate pf_*.asc | **flag thật** — t0mcat = tomato-cat CVE hint |
