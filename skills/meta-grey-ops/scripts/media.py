#!/usr/bin/env python3
"""Upload images and videos, wait for processing, emit a manifest the spec can cite.

    python3 media.py --account act_123 --image creatives/*.jpg
    python3 media.py --account act_123 --video creatives/slots.mp4 --page 456
    python3 media.py --account act_123 --video a.mp4 b.mp4 --manifest media.json

Then paste `image_hash` / `video_id` / `image_hash` (thumbnail) from the manifest into
the launch spec.

Three traps this exists to remove — all verified against Meta docs 2026-08-31:

1. `graph-video.facebook.com` is DEPRECATED; video uploads go to `graph.facebook.com`.
   Meta's own facebook-python-business-sdk still hardcodes the dead host in
   video_uploader.py (open issue #701, since 2025-04) and returns 500s. If an agent
   reaches for the official SDK to upload video, it fails for a reason no error
   message explains. This module uses the live host.

2. A video is NOT usable the moment the upload returns. `GET /{video_id}?fields=status`
   → `status.video_status` ∈ ready | processing | error. Building an ad against a
   still-processing video fails ("Video not ready for use in an ad"). Poll first.

3. The thumbnail uri from `GET /{video_id}/thumbnails` is an fbcdn URL, and the
   AdCreativeVideoData reference explicitly says not to feed FB CDN URLs into
   `image_url`. The sanctioned path is: fetch the thumbnail, re-upload it via
   /adimages, use the returned `image_hash`. This script does that automatically.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import uuid

import graph

# Server-suggested chunking wins; this is only the opening request size.
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 1800


def upload_image(account: str, path: str) -> dict:
    """POST /act_X/adimages. The multipart FIELD NAME is the filename, and Meta
    requires a real extension — 'sample' or 'sample.tmp' is rejected, 'sample.jpg' is
    not. The response is keyed by that same field name.

    Hashes are account-scoped in practice; re-upload per account, or use
    copy_from={source_account_id, hash} to move one across."""
    name = os.path.basename(path)
    if "." not in name:
        sys.exit(f"{path}: Meta requires a filename extension (e.g. .jpg), got {name!r}")

    # Bytes, not a file handle: graph.call retries idempotent uploads, and a handle left at
    # EOF by the first attempt would send an empty body on the retry.
    with open(path, "rb") as fh:
        content = fh.read()
    resp = graph.call(
        "POST", f"{account}/adimages",
        files={name: (name, content)},
        context=f"adimages {name}",
        # Safe to repeat: the hash is derived from the file's bytes, so a re-upload
        # of the same file returns the same hash instead of a second asset.
        idempotent=True,
    )
    entry = next(iter(resp["images"].values()))
    print(f"  image {name} → hash {entry['hash']} ({entry.get('width')}x{entry.get('height')})")
    # entry['url'] is temporary and the docs say not to use it in creative creation.
    return {"file": path, "image_hash": entry["hash"],
            "width": entry.get("width"), "height": entry.get("height")}


def upload_video(account: str, path: str) -> str:
    """Chunked upload against graph.facebook.com.

    The server dictates chunk boundaries: each `transfer` response returns the NEXT
    start_offset/end_offset. Loop until they are equal. Subcode 1363037 means the
    offsets desynced — the error payload carries the correct ones."""
    size = os.path.getsize(path)
    name = os.path.basename(path)
    # Scraped Ads Manager (Power Editor) EAAB tokens are app-bound callers: advideos rejects
    # them with 100/1363049 "A waterfall ID is required when the caller is a Facebook App"
    # unless every phase carries one client-generated id (field-observed 2026-09-23).
    # System User tokens accept it and ignore it.
    waterfall = str(uuid.uuid4())

    # All three phases retry on a dropped connection. On a grey SOCKS exit a multi-chunk
    # upload will hit one, and without retries a single blip kills the whole file.
    # `transfer` is keyed by (upload_session_id, start_offset) and `finish` by the
    # session, so repeating either is a no-op. `start` is the weak one: a retry that
    # duplicates it leaves an orphaned upload session and an unfinished video_id behind.
    # That costs nothing — nothing references it and it never becomes an ad — which is a
    # better trade than failing a 200 MB upload on a transient.
    start = graph.post(
        f"{account}/advideos",
        {"file_size": size, "upload_phase": "start", "waterfall_id": waterfall},
        context=f"advideos start {name}",
        idempotent=True,
    )
    session_id = start["upload_session_id"]
    video_id = start["video_id"]
    begin, end = int(start["start_offset"]), int(start["end_offset"])
    print(f"  video {name}: session {session_id}, video_id {video_id}, {size} bytes")

    with open(path, "rb") as fh:
        while begin < end:
            fh.seek(begin)
            chunk = fh.read(end - begin)
            try:
                resp = graph.call(
                    "POST", f"{account}/advideos",
                    data={"upload_phase": "transfer", "upload_session_id": session_id, "waterfall_id": waterfall,
                          "start_offset": begin},
                    files={"video_file_chunk": (name, chunk)},
                    context=f"advideos transfer {name}",
                    idempotent=True,
                )
            except graph.GraphError as e:
                # 1363037 = offsets desynced. The error payload carries the offsets the
                # server actually wants; resync to them instead of failing the upload.
                text = e.user_msg or e.message
                # Key off the labelled offsets. Grabbing "any two digits" mis-seeks the
                # moment the message carries a session id, a size, or a code.
                found = dict(re.findall(r"(start_offset|end_offset)\D{0,4}(\d+)", text))
                if e.subcode == 1363037 and {"start_offset", "end_offset"} <= found.keys():
                    begin, end = int(found["start_offset"]), int(found["end_offset"])
                    print(f"\n    ! offset desync, resyncing to {begin}-{end}", file=sys.stderr)
                    continue
                raise
            begin, end = int(resp["start_offset"]), int(resp["end_offset"])
            pct = 100.0 * begin / size if size else 100.0
            print(f"    transferred {begin}/{size} ({pct:.0f}%)", end="\r", flush=True)

    graph.post(
        f"{account}/advideos",
        {"upload_phase": "finish", "upload_session_id": session_id, "title": name,
         "waterfall_id": waterfall},
        context=f"advideos finish {name}",
        idempotent=True,
    )
    print(f"\n  video {name}: upload finished, video_id {video_id}")
    return video_id


def wait_ready(video_id: str) -> None:
    """Block until status.video_status == 'ready'. An ad built against a processing
    video fails, and the failure reads like a bad video id."""
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        st = graph.get(video_id, params={"fields": "status"}, context="video status").get("status", {})
        state = st.get("video_status")
        progress = st.get("processing_progress")
        if state == "ready":
            print(f"  video {video_id}: ready")
            return
        if state == "error":
            sys.exit(f"video {video_id}: processing FAILED — re-encode and re-upload ({st})")
        if state not in ("processing", "uploading", None):
            # Documented values are ready|processing|error; 'uploading' and others turn up
            # in practice. Report an unknown state rather than silently spinning to timeout.
            print(f"\n    ! unexpected video_status {state!r} — still waiting", file=sys.stderr)
        print(f"    {state} {progress or ''}%   ", end="\r", flush=True)
        time.sleep(POLL_INTERVAL_S)
    sys.exit(f"video {video_id}: still {state} after {POLL_TIMEOUT_S}s — check it in Media Library")


def thumbnail_hash(account: str, video_id: str) -> dict:
    """Preferred thumbnail → local file → /adimages → image_hash.

    The docs discourage passing an fbcdn uri into video_data.image_url, so we convert
    it to an owned image_hash instead. If you do pass the uri directly, pass it WHOLE:
    truncating its signed query string fails creative creation (2446603)."""
    thumbs = graph.get(f"{video_id}/thumbnails", context="thumbnails").get("data", [])
    if not thumbs:
        print(f"  video {video_id}: no thumbnails yet — supply image_hash manually")
        return {}
    chosen = next((t for t in thumbs if t.get("is_preferred")), thumbs[0])

    handle = tempfile.NamedTemporaryFile(prefix=f"metaops-thumb-{video_id}-", suffix=".jpg",
                                         delete=False)
    tmp = handle.name
    handle.close()
    # Plain session: fbcdn is not Graph, so the META_COOKIES header must not travel there.
    resp = graph.plain_session().get(chosen["uri"], timeout=120)
    resp.raise_for_status()
    with open(tmp, "wb") as fh:
        fh.write(resp.content)

    entry = upload_image(account, tmp)
    os.remove(tmp)
    return {"thumbnail_uri": chosen["uri"], "thumbnail_image_hash": entry["image_hash"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account", required=True)
    ap.add_argument("--image", nargs="*", default=[])
    ap.add_argument("--video", nargs="*", default=[])
    ap.add_argument("--page", help="Unused today. Custom thumbnail upload "
                                   "(POST /{video_id}/thumbnails) needs the video associated "
                                   "with a Page; this script uses the auto-generated preferred "
                                   "thumbnail instead, which needs no Page.")
    ap.add_argument("--manifest", default="media.json")
    args = ap.parse_args()

    account = graph.normalize_account(args.account)
    manifest: dict = {"account_id": account, "images": [], "videos": []}

    for path in args.image:
        manifest["images"].append(upload_image(account, path))

    for path in args.video:
        video_id = upload_video(account, path)
        wait_ready(video_id)
        entry = {"file": path, "video_id": video_id}
        entry.update(thumbnail_hash(account, video_id))
        manifest["videos"].append(entry)

    with open(args.manifest, "w", encoding="utf-8") as fh:
        fh.write(graph.redact(json.dumps(manifest, indent=2)))
    print(f"\nmanifest → {args.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
