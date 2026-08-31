#!/usr/bin/env python3
"""Recover the Walkie Leaks flag from the supplied USBPcap capture.

Only the Python standard library is required.  The two substitution tables are
from the public CHIRP driver for the Radtel RT-752/GT-10 radio family:
https://github.com/EA5JQP/Chirp-Driver-Radtel-RT752/blob/main/rt752.py
"""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path
from typing import Iterator


SECRET_RANDOM = bytes.fromhex(
    "4ac52e21ebb48844f2b0417be6bff9f63c0600196a42b1d68d39615c797a4598"
    "e518becc8be8a8d85731033a14e22f51aa30f4ae604f6b70db3bc1e0c9fc49df"
    "f0324ca907fd56a0d4f527d78cb9d259ffd3eeefc363da2aa26cf3fe9e77d90d7"
    "ed546405d902d1c73b3ab0b84229dc6bd1efade23b271ceaf806d439354967492"
    "81581a1d87a5911068e13d6ed036667d5e67cdb747ed7f28122cfb8f0edc7882"
    "5b6924a4e48995f7c84e1f9c139b0a4d3f76e38e622bb86426d1204bacc4e75f"
    "ecad75028af1175aea3894e90537bc9abaa725c0343ecbbb50cf8572c21183a6a1"
    "86dd0f169ff8b69952a36f091b08b50c15c729ca7c333597046548015355"
)

SECRET_CODE_DATA = bytes.fromhex(
    "c921f400af91da1ffe26f70ba1eec3acbb192bbc021c9039e2d08bc443f5769b"
    "566062edbd3ea431eb9352f2fd4f8af8fafff64a161029d77a50e1966447716b8"
    "853a79fca28d294b9e3b1923f137c48242e5e6633d182705c7b639d490d84e40"
    "6d457d82d405a17e979f0a97dc53795c078fc6855e0e738737e3aabb81edb87e"
    "586341d0f544edc6c3d2f2ccdb2811b32a5d9ccc73b6574b7dfd5d308b351cb"
    "0761859c8edd2a040efbae9e206d4ba2c1446a8c6ef3b5bec65d9983223c8d97"
    "aaec98678f69a889ad5f0305cede5b1823251a9aa64db64172f114bf11363058"
    "59cf0c6fbaefb48012c877270946d6f915457fa3a0b07535424ce801c2e60aea"
)

# Printable ASCII except "}". Restricting the middle prevents FF padding from
# being mistaken for part of a direct, contiguous flag.
FLAG_RE = re.compile(rb"ASIS\{[\x20-\x7c\x7e]{0,200}\}")


def enhanced_packets(raw: bytes) -> Iterator[bytes]:
    """Yield captured frames from little-endian pcapng Enhanced Packet Blocks."""
    if raw[:4] != b"\x0a\x0d\x0d\x0a" or raw[8:12] != b"\x4d\x3c\x2b\x1a":
        raise ValueError("expected a little-endian pcapng capture")

    offset = 0
    while offset + 12 <= len(raw):
        block_type, block_len = struct.unpack_from("<II", raw, offset)
        if block_len < 12 or offset + block_len > len(raw):
            raise ValueError(f"invalid pcapng block at offset 0x{offset:x}")
        if struct.unpack_from("<I", raw, offset + block_len - 4)[0] != block_len:
            raise ValueError(f"pcapng block length mismatch at offset 0x{offset:x}")

        if block_type == 6:  # Enhanced Packet Block
            body = raw[offset + 8 : offset + block_len - 4]
            if len(body) >= 20:
                captured_len = struct.unpack_from("<I", body, 12)[0]
                yield body[20 : 20 + captured_len]
        offset += block_len


def usb_payloads(raw: bytes) -> Iterator[tuple[int, bytes]]:
    """Yield (endpoint, payload) pairs from USBPcap pseudo-headers."""
    for frame in enhanced_packets(raw):
        if len(frame) < 27:
            continue
        header_len = struct.unpack_from("<H", frame, 0)[0]
        if header_len < 27 or header_len > len(frame):
            continue
        endpoint = frame[21]
        data_len = struct.unpack_from("<I", frame, 23)[0]
        if header_len + data_len > len(frame):
            continue
        payload = frame[header_len : header_len + data_len]
        if endpoint in (0x02, 0x82) and payload:
            yield endpoint, payload


def transactions(raw: bytes) -> list[tuple[bytes, bytes]]:
    """Group each host OUT request with all following radio IN fragments."""
    result: list[tuple[bytes, bytes]] = []
    request: bytes | None = None
    response = bytearray()

    for endpoint, payload in usb_payloads(raw):
        if endpoint == 0x02:
            if request is not None:
                result.append((request, bytes(response)))
            request = payload
            response.clear()
        elif request is not None:
            response.extend(payload)

    if request is not None:
        result.append((request, bytes(response)))
    return result


def checksum_is_valid(plain: bytes) -> bool:
    """Implement the response checksum used by the public RT-752 driver."""
    start = 6
    end = len(plain)
    if start == end:
        return True
    if end > 0x10:
        if len(plain) < 12:
            return False
        data_len = struct.unpack_from(">H", plain, 10)[0]
        end = min(data_len + 0x0C + 1 + 4, end)

    received = plain[end - 4 : end]
    calculated = (0x5AA5 + sum(plain[start : end - 4])).to_bytes(4, "big")
    return received == calculated


def decrypt_envelope(encoded: bytes) -> bytes | None:
    """Remove the outer seed/SecretRandom layer from an IN response."""
    if len(encoded) < 2:
        return None
    seed = encoded[0]
    plain = bytes(
        (value - SECRET_RANDOM[(seed + index) & 0xFF]) & 0xFF
        for index, value in enumerate(encoded[1:])
    )
    return plain if checksum_is_valid(plain) else None


def decrypt_data(envelope: bytes) -> tuple[int, bytes] | None:
    """Decode the inner payload and return its target memory address."""
    if len(envelope) <= 16 or envelope[0] != 0x5A:
        return None
    address, data_len = struct.unpack(">LH", envelope[6:12])
    if len(envelope) < 12 + data_len + 1:
        return None

    encrypted = envelope[12 : 12 + data_len]
    seed = envelope[12 + data_len]
    secret = SECRET_CODE_DATA[seed]
    data = bytes(
        SECRET_CODE_DATA[(value - SECRET_RANDOM[index & 0xFF] + secret) & 0xFF]
        for index, value in enumerate(encrypted)
    )
    return address, data


def find_flag(
    pages: list[tuple[int, int, bytes]],
) -> tuple[str, int, int, int, list[str]] | None:
    """Find a normal flag or one split across 16-byte, FF-padded records."""
    for transaction_no, address, data in pages:
        direct = FLAG_RE.search(data)
        if direct:
            return (
                direct.group().decode("ascii"),
                transaction_no,
                address,
                direct.start(),
                [direct.group().decode("ascii")],
            )

        search_at = 0
        while True:
            start = data.find(b"ASIS{", search_at)
            if start < 0:
                break
            fragments: list[bytes] = []
            for record_start in range(start, len(data), 16):
                record = data[record_start : record_start + 16]
                fragment = bytes(byte for byte in record if 0x20 <= byte <= 0x7E)
                if not fragment:
                    break
                fragments.append(fragment)
                candidate = b"".join(fragments)
                match = FLAG_RE.search(candidate)
                if match:
                    return (
                        match.group().decode("ascii"),
                        transaction_no,
                        address,
                        start,
                        [part.decode("ascii") for part in fragments],
                    )
            search_at = start + 1
    return None


def main() -> int:
    default_capture = Path(__file__).resolve().parent.parent / "Capture.pcapng"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "capture",
        nargs="?",
        type=Path,
        default=default_capture,
        help=f"USBPcap capture (default: {default_capture})",
    )
    args = parser.parse_args()

    raw = args.capture.read_bytes()
    grouped = transactions(raw)
    pages: list[tuple[int, int, bytes]] = []
    for transaction_no, (_request, response) in enumerate(grouped, 1):
        envelope = decrypt_envelope(response)
        if envelope is None:
            continue
        decoded = decrypt_data(envelope)
        if decoded is not None:
            address, data = decoded
            pages.append((transaction_no, address, data))

    print(f"[+] transactions: {len(grouped)}")
    print(f"[+] decoded blocks: {len(pages)} ({sum(len(p[2]) for p in pages)} bytes)")

    found = find_flag(pages)
    if found is None:
        print("[-] ASIS flag not found")
        return 1

    flag, transaction_no, address, offset, fragments = found
    print(
        f"[+] flag block: transaction {transaction_no}, "
        f"address 0x{address:08x}, offset 0x{offset:04x}"
    )
    print(f"[+] fragments: {' | '.join(fragments)}")
    print(f"[+] FLAG: {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
