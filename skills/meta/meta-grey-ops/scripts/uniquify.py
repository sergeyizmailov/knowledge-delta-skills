#!/usr/bin/env python3
"""Make one creative file into N byte-distinct variants, one per account.

    python3 uniquify.py creatives/slots.mp4 --n 5 --out creatives/uniq/
    python3 uniquify.py creatives/*.jpg --n 3 --out creatives/uniq/ --tags J41-16,J41-17,J41-18

Images (Pillow): crop 1–4 px per edge (random per variant), ±1% brightness, re-encode JPEG at
a jittered quality, strip EXIF. Videos (ffmpeg): trim 40–160 ms from the head, scale to a
1-2 px different even size back to original via crop, re-encode (x264 CRF jitter), re-mux;
audio copied. Output names carry the tag or the index: slots.J41-16.mp4.

Then upload per account with media.py — hashes are account-scoped anyway (04 → Media). What
this buys: distinct bytes and metadata per account (identical bytes across accounts is an
UNVERIFIED linking hypothesis). What it does not buy: perceptual distinctness — measured
2026-09-03 on 1080x1080 synthetics, the jitters here move 64-bit dHash by 0-6 and pHash by <=6,
under the ~8 near-duplicate threshold, and Meta's copy detector is SSCD (self-supervised,
survives crops/color/text overlay). Real variance = different source creatives (03 naming).
It does not "pass review" — content is what reviewers see. `--report` prints the distances.

Deterministic per (file, tag): the same input and tag always produce the same output, so a
re-run does not create a new variant for an account that already has one.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import random
import shutil
import subprocess
import sys

IMG = {".jpg", ".jpeg", ".png", ".webp"}
VID = {".mp4", ".mov", ".m4v"}


def seed_for(path: pathlib.Path, tag: str) -> random.Random:
    h = hashlib.sha256((path.name + "|" + tag).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def uniq_image(src: pathlib.Path, dst: pathlib.Path, rnd: random.Random, crop: bool = True) -> None:
    """crop=True: 1-4 px per edge + brightness jitter (default). crop=False: exact pixel
    dimensions kept (text/border-heavy 1080x1080 banners); uniqueness from +-0.5%
    brightness/contrast jitter, EXIF strip (convert() drops it) and JPEG quality 92-95."""
    try:
        from PIL import Image, ImageEnhance
    except ImportError:
        sys.exit("pip install pillow")
    im = Image.open(src).convert("RGB")
    w, h = im.size
    if crop:
        left, top, right, bottom = (rnd.randint(1, 4) for _ in range(4))
        im = im.crop((left, top, w - right, h - bottom))
        im = ImageEnhance.Brightness(im).enhance(1 + rnd.uniform(-0.01, 0.01))
        quality = rnd.randint(88, 95)
    else:
        im = ImageEnhance.Brightness(im).enhance(1 + rnd.uniform(-0.005, 0.005))
        im = ImageEnhance.Contrast(im).enhance(1 + rnd.uniform(-0.005, 0.005))
        quality = rnd.randint(92, 95)
    if dst.suffix.lower() in (".jpg", ".jpeg"):
        im.save(dst, "JPEG", quality=quality, optimize=True)
    else:
        im.save(dst)


def _gray(im, size: tuple[int, int]):
    from PIL import Image
    return im.convert("L").resize(size, Image.LANCZOS)


def dhash(im) -> int:
    """Krawetz 64-bit difference hash (9x8 gray, left>right per row)."""
    px = list(_gray(im, (9, 8)).tobytes())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | int(px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


def phash(im) -> int:
    """64-bit DCT perceptual hash: 32x32 gray → 2-D DCT-II → top-left 8x8 (minus DC) vs median."""
    import math
    n = 32
    px = list(_gray(im, (n, n)).tobytes())
    cos = [[math.cos((2 * x + 1) * u * math.pi / (2 * n)) for x in range(n)] for u in range(n)]
    rows = [[sum(px[y * n + x] * cos[u][x] for x in range(n)) for u in range(8)] for y in range(n)]
    coef = [sum(rows[y][u] * cos[v][y] for y in range(n)) for v in range(8) for u in range(8)]
    vals = coef[1:]
    med = sorted(vals)[len(vals) // 2]
    bits = 0
    for c in vals:
        bits = (bits << 1) | int(c > med)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def image_report(src: pathlib.Path, dst: pathlib.Path) -> dict:
    from PIL import Image, ImageChops
    a, b = Image.open(src).convert("RGB"), Image.open(dst).convert("RGB")
    ga, gb = _gray(a, (64, 64)), _gray(b, (64, 64))
    diff = ImageChops.difference(ga, gb).tobytes()
    return {"dhash": hamming(dhash(a), dhash(b)), "phash": hamming(phash(a), phash(b)),
            "mean_abs_diff": round(sum(diff) / len(diff), 2), "same_size": a.size == b.size}


REPORT_CAVEAT = ("distances are dHash/pHash only (near-duplicate threshold ~8/64); Meta uses SSCD — "
                 "treat variants as byte-level uniqueness, not proof against perceptual dedup")


def uniq_video(src: pathlib.Path, dst: pathlib.Path, rnd: random.Random) -> None:
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found (brew install ffmpeg)")
    trim = rnd.randint(40, 160) / 1000
    crf = rnd.randint(19, 23)
    dx, dy = rnd.choice([0, 2]), rnd.choice([0, 2])
    vf = f"crop=iw-{dx}:ih-{dy}:{dx // 2}:{dy // 2},scale=trunc(iw/2)*2:trunc(ih/2)*2" if (dx or dy) else "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{trim:.3f}", "-i", str(src),
           "-vf", vf, "-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-movflags", "+faststart", "-map_metadata", "-1", str(dst)]
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--n", type=int, help="number of variants (ignored when --tags is given)")
    ap.add_argument("--tags", help="comma-separated account tags → one variant per tag")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-crop", action="store_true",
                    help="images: keep exact dimensions (no 1-4 px crop); jitter + re-encode only")
    ap.add_argument("--report", action="store_true",
                    help="images: print dHash/pHash Hamming distance and mean abs diff vs source")
    args = ap.parse_args()

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else [f"v{i:02d}" for i in range(1, (args.n or 1) + 1)]
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    made = 0
    for f in args.files:
        src = pathlib.Path(f)
        ext = src.suffix.lower()
        if ext not in IMG | VID:
            print(f"  skip {src.name}: unsupported type")
            continue
        for tag in tags:
            dst = out / f"{src.stem}.{tag}{ext}"
            if dst.exists():
                print(f"  = {dst.name} (exists)")
                continue
            rnd = seed_for(src, tag)
            if ext in IMG:
                uniq_image(src, dst, rnd, crop=not args.no_crop)
            else:
                uniq_video(src, dst, rnd)
            line = f"  + {dst.name}"
            if args.report and ext in IMG:
                r = image_report(src, dst)
                line += f"  dhash={r['dhash']} phash={r['phash']} mad={r['mean_abs_diff']}"
            print(line)
            made += 1
    print(f"\n{made} variant(s) → {out}. Upload each with media.py --account <the tag's account>.")
    if args.report:
        print(REPORT_CAVEAT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
