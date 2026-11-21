"""Builds app/libs/onnxruntime-android-1.28.0-vox.aar from Maven's onnxruntime-android 1.28.0.

Why: the app ships two users of onnxruntime. sherpa-onnx 2.0.2 (Nemotron) brings
its own libonnxruntime.so, version 1.28.2, and onnxruntime-android 1.28.0
(Granite) brings another. Only one file of that name fits in the APK, and each
library's functions carry a version label (VERS_1.28.2 against VERS_1.28.0), so
whichever copy is left out breaks the other side: on 21 Nov 2026 the phone
failed with 'cannot locate symbol "OrtGetApiBase"'.

The fix keeps sherpa's 1.28.2 library, the newer one, and points onnxruntime's
small Java bridge (libonnxruntime4j_jni.so) at it: the bridge's request for
VERS_1.28.0 is relabelled VERS_1.28.2. Both export the same three functions
(OrtGetApiBase and two execution provider calls), and 1.28.2 serves API
version 28, which the 1.28.0 bridge asks for. Only the arm64-v8a bridge is
kept, because the APK is arm64 only.

Usage:  python tools/make_ort_aar.py PATH/TO/onnxruntime-android-1.28.0.aar
"""
import struct
import sys
import zipfile
from pathlib import Path

OLD = b"VERS_1.28.0"
NEW = b"VERS_1.28.2"
ABI = "arm64-v8a"
OUT = Path(__file__).resolve().parent.parent / "app" / "libs" / "onnxruntime-android-1.28.0-vox.aar"


def elf_hash(name: bytes) -> int:
    h = 0
    for c in name:
        h = (h << 4) + c
        g = h & 0xF0000000
        if g:
            h ^= g >> 24
        h &= ~g
    return h & 0xFFFFFFFF


def relabel(so: bytes) -> bytes:
    data = bytearray(so)
    assert data[:4] == b"\x7fELF" and data[4] == 2 and data[5] == 1, "expected a 64-bit little-endian ELF"
    shoff, = struct.unpack_from("<Q", data, 0x28)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x3A)
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * shentsize) for i in range(shnum)]
    verneed = [s for s in sections if s[1] == 0x6FFFFFFE]
    assert len(verneed) == 1, "no version needs section"
    _, _, _, _, offset, _, link, count, _, _ = verneed[0]
    strtab = sections[link][4]
    changed = 0
    pos = offset
    for _ in range(count):
        _, cnt, _, aux, nxt = struct.unpack_from("<HHIII", data, pos)
        apos = pos + aux
        for _ in range(cnt):
            _, flags, other, name, anext = struct.unpack_from("<IHHII", data, apos)
            start = strtab + name
            if data[start:start + len(OLD) + 1] == OLD + b"\0":
                data[start:start + len(NEW)] = NEW
                struct.pack_into("<I", data, apos, elf_hash(NEW))
                changed += 1
            apos += anext
        pos += nxt
    assert changed == 1, f"expected one {OLD.decode()} need, found {changed}"
    assert OLD not in data, f"{OLD.decode()} is still referenced elsewhere in the file"
    return bytes(data)


def main() -> None:
    source = Path(sys.argv[1])
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            name = item.filename
            if name.startswith("jni/"):
                if name != f"jni/{ABI}/libonnxruntime4j_jni.so":
                    continue  # other ABIs, and the 1.28.0 runtime sherpa-onnx's replaces
                dst.writestr(item, relabel(src.read(item)))
            else:
                dst.writestr(item, src.read(item))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
