# 07 — Chuỗi sai lầm: flag giả & các cơn bí tắc (retrospective)

Bổ sung cho `05-the-miss.md` (vì sao bỏ sót port). File này giải thích **cả
chuỗi sai lầm** — từ lúc đọc nhầm vector pollution, tới việc đốt hàng trăm
phép thử quanh flag giả, tới các giai đoạn bí tắc hoàn toàn — mỗi mục gồm:
hiện tượng → kết luận sai → nguyên nhân gốc → cách sửa → bài học.

## Timeline tổng quan

| # | Sai lầm | Phiên | Chi phí |
|---|---|---|---|
| M1 | Ghi nhận ngược vector pollution (`__proto__` vs `constructor.prototype`) | 1–2 | 2 phiên xây hiểu sai nền tảng |
| M2 | Chẩn đoán sai "app tự fetch chính nó gây treo" | 2 | Bỏ hướng loopback sớm |
| M3 | Ở lại quanh flag giả để tìm "giá trị gate thật" | 3–4 | ~130 phép thử header/query/method |
| M4 | Tin `robots.txt` là bản đồ, cố "mở khóa" route không tồn tại | 3 | ~310 phép thử fuzz |
| M5 | Chốt sớm "network khóa = by design" | 3 | Khóa luôn tầng port trong đầu |
| M6 | Tin ECONNREFUSED = host sống → đuổi theo host ma | 4 | 1 chu kỳ scan rỗng (~30 IP) |
| M7 | Tự DoS oracle của chính mình (quên reset pollution) | 4 | Nhiều vòng "app chết" giả |
| M8 | Đuổi port 2000/5060 nhiễu trên public IP | 4 | Recheck nhiều lần vô ích |
| M9 | Khung SSRF sai từ đầu (nghĩ cần outbound/callback) | 1→4 | Trả lời muộn câu "không outbound thì làm gì?" |

---

## M1 — Ghi nhận ngược vector pollution

**Hiện tượng.** `1.md`/`2.md` ghi: `__proto__` top-level → 200, pollute được;
`constructor.prototype` → "bị bỏ qua".

**Thực tế.** Ngược lại hoàn toàn: `__proto__` bị chặn 400, `constructor.prototype`
mới là vector thật (3.md mục 1 phải "khắc phục nhận định ở 2.md").

**Nguyên nhân gốc.** Object.prototype là **global state của cả process** —
một request pollute thành công thì *mọi* request sau (kể cả của session khác,
kể cả gửi vector chết) đều thấy kết quả polluted. Test `__proto__` chạy *sau*
một request `constructor.prototype` thành công → tưởng `__proto__` ăn.

**Cách sửa.** Mỗi test phải (a) clean trước bằng
`{"constructor":{"prototype":{"ogImage":null}}}`, (b) dùng URL marker **duy nhất**
mỗi lần, (c) chỉ công nhận khi preview nhắc đúng marker mới. Đây là nguyên tắc
"differential trên nền sạch" trong `02-prototype-pollution.md`.

**Bài học.** Khi test một sink toàn cục, trạng thái từ request trước luôn rò
sang request sau. Không isolate = mọi kết luận dương tính là nghi ngờ.

---

## M2 — Chẩn đoán sai "app tự fetch vào chính nó gây treo"

**Hiện tượng.** `2.md` mục 7: SSRF tới `http://127.0.0.1:3000/api/schema` —
PUT thành công nhưng preview chỉ trả 502 nginx hoặc **kết quả cũ**
("ETIMEOUT evil"). Kết luận lúc đó: "app tự fetch vào chính nó gây treo (Node
single-thread) hoặc preview bị cache / DNS cache".

**Thực tế.** Hai việc khác xảy ra: (1) hostname `127.0.0.1` bị filter chặn —
response thật là `refused to fetch ... host not allowed`, (2) preview trả
**stale result** của fetch trước đó trong lúc fetch mới chưa xong → đọc nhầm.

**Chi phí.** Vì tưởng self-fetch làm app treo, hướng loopback bị bỏ ngay ở
phiên 2. Bypass thật (`[::1]`, `[::ffff:127.0.0.1]`) chỉ được tìm lại ở phiên 3.

**Cách sửa.** Đọc kỹ response (chuỗi `host not allowed` ≠ timeout) + chờ/poll
đến khi kết quả khớp URL mới (marker). Sau này mọi probe đều kèm cả hai.

**Bài học.** Với oracle bất đồng bộ, "kết quả cũ" là trạng thái bình thường,
không phải bằng chứng cho giả thuyết treo. Phân biệt "chưa có kết quả mới" với
"kết quả là lỗi".

---

## M3 — Flag giả: vì sao nó giữ chân được

**Hiện tượng.** `GET /api/flag` + `X-Internal: 1` → `flag{decoy_this_endpoint_is_a_trap}`
— tự xưng trap bằng chữ literal. Vẫn tiêu tốn ~130 phép thử quanh nó.

**Chuỗi suy luận sai.**
1. *"Gate so sánh '1' nghiêm ngặt quá (01/true/2 đều 403) → chắc '1' không phải
   giá trị thật, phải có giá trị khác"* — đây là **đọc quá sâu chi tiết cài đặt**
   (so sánh chuỗi bình thường của tác giả), biến nó thành puzzle.
2. Từ đó phát sinh: header matrix (XFF, X-Real-IP, Host, Authorization...),
   query injection, method fuzzing, thử qua từng góc SSRF...
3. Kết quả nào cũng ra đúng flag giả → càng tin "còn giá trị thật chưa tìm ra".

**Thực tế.** Route + gate là thật, flag là mồi. Nó tồn tại để **đổi thời gian
port-scan thành thời gian route-fuzz** — và nó làm được việc đó 2 phiên liền.

**Vì sao hiệu quả (tâm lý).**
- Có HTTP 200 + có flag format → não dừng kiểm tra "flag này có thật không?"
  tại chính dấu bằng braces, mặc dù chuỗi bên trong tự khai "trap"
- Gate khó (so '1' chính xác) → cảm giác "gần xong, chỉ cần giá trị đúng"
- Mọi test đều "thành công" (200 + flag) → reinforcing loop

**Bài học.** Khi một artifact tự xưng là mồi thì tin nó **ngay lập tức** và
hỏi: "nó che tầng nào?" — chứ không phải "làm sao vượt qua nó?". Flag giả ở
route 3000 che的事实: tác giả không giấu flag ở tầng route.

---

## M4 — `robots.txt`: cố mở khóa cánh cửa không tồn tại

**Hiện tượng.** `Disallow: /internal-metadata` → 404 tuyệt đối. ~310 phép thử
đổ vào: 45 query params, 33 headers, 37 path variants, 6 method, 8 body...

**Kết luận sai ngầm.** "Route có thật nhưng bị khóa — chỉ cần đúng
param/header/cookie là mở."

**Thực tế.** Route không tồn tại. Tên `internal-metadata` đặt **gần đúng**
service thật (`media-metadata`) một chữ — đánh lạc hướng có chủ đích.

**Chi phí.** Đây là đợt tốn công nhất (workflow 5 agent). Toàn bộ effort nằm ở
tầng route, trong khi flag ở tầng port.

**Bài học.** Trước khi unlock một route ẩn, **verify tầng tồn tại**: route có
thật không? cùng app không? cùng port không? Nếu mọi điều kiện đều 404 sạch
(quả 404 baseline của app, không phải 403/redirect), khả năng cao nó không
tồn tại — và tên gần-đúng trong artifact là mồi, không phải bản đồ.

---

## M5 — Chốt sớm "network khóa = by design"

**Hiện tượng.** `3.md` mục 4: "Kết luận (user xác nhận chủ đích của đề): flag
không cần ra khỏi app; network khóa chặn là by-design."

**Vấn đề.** Kết luận này **đúng** (flag đúng là không cần ra khỏi app) nhưng
**rộng hơn dữ kiện** — nó ngầm đóng luôn mọi tầng khác *trong* app, kể cả
tầng port. Sau này hint "search for some open ports" tới, các lần diễn giải
đầu tiên vẫn bị anchoring: quét public IP, quét container khác — chứ không
nghĩ ngay tới loopback trong chính container.

**Bài học.** Kết luận âm tính phải ghi rõ **phạm vi đã phủ** ("đã quét X, Y, Z
qua giao thức A") thay vì kết luận khẳng định ("mạng trống"). Cái thứ hai tự
đóng cửa những gì chưa quét — ở đây là `[::ffff:127.0.0.1]`.

---

## M6 — Host ma do gateway spoof RST

**Hiện tượng.** Subnet sweep 172.16–21.x / 10.x / 192.168.x cho ~20 host
"ALIVE" (ECONNREFUSED = "host sống, port đóng").

**Thực tế.** Control-test với IP chắc chắn không tồn tại (203.0.113.7,
192.0.2.99 — TEST-NET) → **cũng ECONNREFUSED**. Gateway trả RST thay mặt mọi
dest không routable. Toàn bộ list là host ma.

**Bài học.** Trên network có middlebox, tín hiệu âm tính (error) phải được
**hiệu chuẩn bằng control** trước khi dùng làm bằng chứng dương tính
("host sống"). Nguyên tắc: chỉ HTTP response thật mới đáng tin.

---

## M7 — Tự DoS oracle của chính mình

**Hiện tượng.** Khi probe gateway 172.18.0.1 (DROP mọi thứ), preview sau đó
treo dài → nginx 502 → trông như "app chết". Chờ app "sống lại" — thực ra chỉ
cần fetch treo đó kết thúc.

**Nguyên nhân gốc.** Pollution là global: đặt `ogImage` vào host DROP một lần
→ **mọi** GET /api/preview sau đó đều chờ fetch đó. Mình tự chặn kênh đọc của
chính mình mà không biết.

**Cách sửa.** Mỗi probe xong **reset ngay** về URL refused-nhanh
(`http://172.18.0.9:1/`) — preview luôn phản hồi tức thì. Scanner phiên cuối
(`lbscan.py`) có auto-reset — đây là điều kiện tiên quyết để scan 130 port
được.

**Bài học.** Với SSRF oracle dạng "poll → fetch → đọc", **trạng thái sau probe
là một phần của probe**: luôn trả oracle về fast-fail state, nếu không kết
quả của probe này giết các probe sau.

---

## M8 — Đuổi port 2000/5060 (nhiễu)

**Hiện tượng.** Scan đầu tiên trên public IP thấy 2000 + 5060 mở; accept
connection nhưng im lặng tuyệt đối (không HTTP, không TLS, không banner).
Recheck nc/nmap nhiều vòng — biến mất.

**Thực tế.** Nhiễu mạng của box (đã unstable từ đầu — 1.md ghi nhận). Vẫn tiêu
tốn chú ý vì "open ports" trùng hint.

**Bài học.** Tín hiệu một-lần-xuất-hiện trên hạ tầng đã biết chập chờn cần
được reproduce ít nhất 2 lần trước khi đầu tư. (Và hint nên đọc theo tầng
nguyên lý — "còn giao thức/tầng nào chưa quét" — thay vì khớp chữ với port
vừa thấy.)

---

## M9 — Khung SSRF sai từ đầu: nghĩ cần outbound

**Hiện tượng.** Câu hỏi mở đầu phiên 4: "nếu SSRF không có outbound thì làm
gì được?" — phản ánh khung mặc định: SSRF = callback về server mình.

**Thực tế.** Chuỗi exploit cuối **không cần một byte nào rời mạng của nạn
nhân**: fetch đích là loopback (luôn thông, không qua egress filter), kênh đọc
là chính `/api/preview` của app.

**Bài học.** Với SSRF, hai câu hỏi tách bạch: (1) *fetch tới đâu được?*
(đích), (2) *đọc kết quả bằng gì?* (kênh). Egress chết chỉ giết mô hình
"callback về mình" — mô hình "đọc nội bộ + exfil qua response của app" không
dính dáng gì egress.

---

## Giải phẫu các cơn bí tắc

| Giai đoạn bí | Nguyên nhân trực tiếp | Thứ đã gỡ |
|---|---|---|
| Cuối phiên 2 (502 + kết quả cũ) | M2: nhầm stale-result thành app treo | Phiên 3: đọc kỹ `host not allowed` + marker |
| Giữa phiên 3 (sau 310 fuzz, 0 hit) | M3+M4: hai mồi giữ chân ở tầng route | Không gỡ hẳn — chuyển hướng mạng (M5 lại chặn) |
| Đầu phiên 4 (sau mọi mạng = rỗng) | M5+M6: âm tính giả phủ kín bản đồ | Control-test RST + checklist 05 |
| Trước đợt scan cuối (preview 502 liên tục) | M7: tự DoS oracle | Auto-reset trong `lbscan.py` |

Mẫu hình chung: **mỗi cơn bí đều do một kết luận âm tính/khẳng định chưa được
hiệu chuẩn** — không phải do thiếu kỹ thuật. Lần lượt sửa M6 (control-test),
M7 (auto-reset), rồi quét đúng tầng còn trống (IPv4-mapped loopback) là ra
flag.

## Meta-bài học (thứ tự quan trọng)

1. **Nền sạch trước mọi test sink toàn cục** (M1)
2. **Marker-verify kết quả oracle** (M2, M7)
3. **Control-test tín hiệu âm tính** trước khi build lên đó (M6)
4. **Tin artifact tự xưng là mồi** — hỏi nó che gì, không hỏi cách vượt (M3, M4)
5. **Ghi âm tính theo phạm vi đã phủ**, không theo khẳng định (M5)
6. **Tách "đích fetch" khỏi "kênh đọc"** khi lý luận SSRF (M9)
