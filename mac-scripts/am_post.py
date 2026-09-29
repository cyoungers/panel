#!/usr/bin/env python3
# Reads AM track fields (record-separator delimited) from stdin and POSTs
# them to the panel container. Fed by the "AM to Panel" Keyboard Maestro macro.
import os
import sys
import json
import urllib.request

PANEL = "http://192.168.0.166:8090"

raw = sys.stdin.read()
if not raw.strip():
    sys.exit(0)

parts = raw.split("\x1e")
while len(parts) < 7:
    parts.append("")
title, artist, album, year, length, state, pid = (p.strip() for p in parts[:7])

# The macro's AppleScript only sets DND_AMLastTrackID after it successfully
# writes this track's artwork to cover-am.jpg. If it doesn't match, the track
# has no artwork and cover-am.jpg still holds the previous song's -- use the
# placeholder instead. (KM passes all variables to this script as KMVAR_*.)
last_art_pid = os.environ.get("KMVAR_DND_AMLastTrackID")
if last_art_pid is not None and last_art_pid.strip() != pid:
    cover_url = PANEL + "/cover-am-noart"
else:
    cover_url = PANEL + "/cover-am?id=" + pid

payload = {
    "feed": "Apple Music",
    "title": title,
    "artist": artist,
    "album": album,
    "released": year,
    "length": length,
    "playing": (state == "playing"),
    "cover_url": cover_url,
    # clear RP-only fields so stale RP data doesn't show under an AM track
    "rating": "",
    "avg_rating": "",
    "num_ratings": "",
    "rating_dist": [],
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    PANEL + "/nowplaying",
    data=data,
    headers={"Content-Type": "application/json"},
)
try:
    urllib.request.urlopen(req, timeout=5)
except Exception:
    pass
