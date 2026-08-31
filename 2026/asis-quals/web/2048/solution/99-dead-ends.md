# 99 — Dead ends (đã loại bỏ, để tiết kiệm thời gian làm lại)

## EL injection qua leaderboard name — KHÔNG phải vector

Leaderboard đầy name là payload EL của player khác: `initParam.flag`, `header.host`,
`cookie.JSESSIONID`, `sessionScope.flag_TAG12`, `pageContext.request.rem`... — tất cả
hiển thị **literal** (bị strip `${` và `}`).

Đã thử:
- `${initParam.flag}` → strip → hiện `initParam.flag`
- Unicode escape `${initParam.flag}` → strip cả backslash → `u0024u007b77u007d` (của player khác thấy trên bảng)
- Score thấp, score 999999999 — không đổi hành vi
- Entry 10s sau vẫn không thấy — POST không re-render gì server-side cả

Kết luận: name đi thẳng vào JSON store rồi ra JSON, **không qua EL evaluator**. Các
entry `initParam.flag` trên bảng chính là dấu vết người khác cũng nghĩ giống vậy.

Lưu ý: entry `XNLaf97a06_initParam.fla` (truncated 24 ký tự) của player trước xác nhận
maxlength 24 đang chặn, nhưng dù có dài hơn cũng vô ích vì không có EL evaluation.

## mirror.jsp param names

- `?label=...` → **400** "the mirror only serves parcels by label"
- `?parcel=...` → đúng param (404 khi label sai)
- Header `X-Label:`, `Label:`, cookie `label=`, method PUT/OVERRIDE — đều không

## Brute-force label trên mirror

Thử ~100 label (flag, flag.txt, secret, test, readme, note, data, dump, JSESSIONID,
name player, event, score...) — tất cả 404. **Shelf trống với người ngoài** vì parcels
do chính bạn drop bằng RCE, và janitor quét 15 phút. Chỉ khi RCE xong mới có gì để đọc.

## AES key guessing — không cần

Entry 003 đã nói seal fail vẫn ship. Thử 15 key themed (portalfluid, wubbalubbadubdub,
picklerick, szechuan, meseeks, c137, 4000...) — tất cả như nhau (CLOSED-clean) vì
key không bao giờ được check khi interceptor bị bypass.

## Frame tự chế cho port 4000

Tất cả các variant python đều im lặng:
- raw blob, blob+EOF
- length prefix 2/4 byte BE/LE
- `[len][data][len]` (đoán mò XByteBuffer)
- wrap trong `byte[]` / `String` serialization
- ChannelData header tự dựng bằng struct python

Phải dùng `catalina-tribes.jar` thật + reflect `START_DATA`/`END_DATA` từ
`XByteBuffer`. Xem 04.

## CC5 gadget

`BadAttributeValueExpException.val` là kiểu `String` trên JDK 9+ (không còn Object)
→ không set được TiedMapEntry vào. CC6 (HashSet) là lựa chọn đúng cho JDK hiện đại.

## Tomcat manager, path traversal

`/manager/html`, `/host-manager/html`, `.git/HEAD`, `WEB-INF/web.xml`, traversal
`../WEB-INF/web.xml` trên mirror — toàn 404/400.

## Port scan (nmap TCP full)

Chỉ 3 port mở: 22 (ssh), 4000 (Tribes), 8080 (HTTP). Không có dịch vụ phụ nào khác.
