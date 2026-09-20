import os
import re
import time
import json
import threading
import urllib.request
import urllib.parse
import requests
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))
CREDS_DIR = os.environ.get("CREDS_DIR", "/creds")

# --- Home Assistant state poller ---
_hk_lock = threading.Lock()
_hk_state = {}  # key -> {on, bri, name}


def _load_ha_config():
    path = os.path.join(CREDS_DIR, "ha.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _poll_ha():
    while True:
        cfg = _load_ha_config()
        if not cfg or cfg.get("token") == "YOUR_LONG_LIVED_TOKEN_HERE":
            time.sleep(10)
            continue
        try:
            headers = {
                "Authorization": f"Bearer {cfg['token']}",
                "Content-Type": "application/json",
            }
            r = requests.get(f"{cfg['url']}/api/states", headers=headers, timeout=5)
            states = {s["entity_id"]: s for s in r.json()}
            updates = {}
            for key, info in cfg.get("entities", {}).items():
                if info.get("push") or not info.get("entity"):
                    continue
                s = states.get(info["entity"])
                if not s:
                    continue
                attrs = s.get("attributes", {})
                if info["entity"].startswith("cover."):
                    pos = attrs.get("current_position", 0)
                    updates[key] = {"on": pos > 0, "bri": pos, "name": info["name"]}
                elif info["entity"].startswith("lock."):
                    locked = s["state"] == "locked"
                    updates[key] = {"on": locked, "locked": locked, "name": info["name"]}
                else:
                    on = s["state"] == "on"
                    # HA brightness is 0-255; keep as-is for comparison with Hue scale
                    bri = attrs.get("brightness")
                    updates[key] = {"on": on, "bri": bri, "name": info["name"]}
            with _hk_lock:
                _hk_state.update(updates)
        except Exception:
            pass
        time.sleep(5)


threading.Thread(target=_poll_ha, daemon=True).start()

# --- Home scene relay (panel buttons -> KBM Public Web trigger -> Shortcuts) ---
KM_HOST = "192.168.0.110"   # Mac running Keyboard Maestro
KM_PORT = 4490
KM_MACRO = "DA3D7EF3-3CC9-428F-9445-8B92744FD32E"  # "Set Home Scene" macro UID
KM_SKIP_MACRO = "144A8A9E-ABF0-440F-B843-2C497A19C59B"  # "Skip RP Track" macro UID
RP_SKIP_RATING_MAX = 4  # skip tracks previously rated this or lower

# --- RP auto-skip: banned artists/titles + low-rating ---
# Entries come from the "DND_RPBannedArtistList" Keyboard Maestro global
# variable (one entry per line). A "Push RP Banned List" step in the user's
# "ban artist/song" KM macro POSTs the raw text here every time it bans
# something, so the panel always has a fresh copy without polling KM.
#
# Each line is optionally tagged with its kind so the skip banner can say
# exactly what matched: "A|Nickelback" (artist) or "T|Free Bird" (track
# title). An untagged line ("Nickelback") still works as before -- matched
# against both artist and title -- so pre-existing entries don't need
# updating.
BANNED_LIST_PATH = os.path.join(CREDS_DIR, "rp_banned_list.json")

_banned_lock = threading.Lock()
_banned_entries = set()  # {(type, normalized_value)}, type in "artist"/"title"/"either"


def _parse_banned_line(line):
    line = line.strip()
    if not line:
        return None
    if len(line) > 2 and line[1] == "|" and line[0].upper() in ("A", "T"):
        typ = "artist" if line[0].upper() == "A" else "title"
        val = line[2:].strip().lower()
        return (typ, val) if val else None
    return ("either", line.lower())


def _load_banned_list():
    global _banned_entries
    try:
        with open(BANNED_LIST_PATH) as f:
            raw = json.load(f).get("entries", [])
        parsed = {(e[0], e[1]) for e in raw if isinstance(e, list) and len(e) == 2}
        with _banned_lock:
            _banned_entries = parsed
    except Exception:
        pass


def _save_banned_list(entries):
    try:
        with open(BANNED_LIST_PATH, "w") as f:
            json.dump({"entries": sorted([typ, val] for typ, val in entries)}, f)
    except Exception:
        pass


_load_banned_list()

_skip_lock = threading.Lock()
_last_skip_track = None  # (artist, title) normalized, last track we fired a skip for
_last_skip_event = None  # {artist, title, reason, rating, at} for the panel UI banner


def _trigger_km_skip():
    url = "http://%s:%d/action.html?macro=%s" % (KM_HOST, KM_PORT, KM_SKIP_MACRO)
    try:
        resp = urllib.request.urlopen(url, timeout=4)
        print("[rp-skip] triggered ok, status=%s" % resp.status, flush=True)
    except Exception as e:
        print("[rp-skip] FAILED to reach KM at %s: %r" % (url, e), flush=True)


def _maybe_skip_track(artist, title, rating):
    """Fire the RP skip macro if the now-playing track is banned or was
    previously rated RP_SKIP_RATING_MAX or lower. Runs the trigger in a
    background thread so it never delays the /nowplaying response."""
    global _last_skip_track, _last_skip_event
    norm_artist = (artist or "").strip().lower()
    norm_title = (title or "").strip().lower()
    if not norm_artist and not norm_title:
        return
    track_key = (norm_artist, norm_title)

    reason = None
    rating_val = None
    with _banned_lock:
        banned = _banned_entries
    for typ, val in banned:
        if typ in ("artist", "either") and val == norm_artist:
            reason = "banned_artist" if typ == "artist" else "banned"
            break
        if typ in ("title", "either") and val == norm_title:
            reason = "banned_title" if typ == "title" else "banned"
            break
    if not reason:
        m = re.search(r"\d+", str(rating) if rating is not None else "")
        if m and int(m.group()) <= RP_SKIP_RATING_MAX:
            reason = "rating"
            rating_val = int(m.group())

    if not reason:
        return

    with _skip_lock:
        if _last_skip_track == track_key:
            return
        _last_skip_track = track_key
        _last_skip_event = {
            "artist": artist, "title": title, "reason": reason,
            "rating": rating_val, "at": time.time(),
        }

    print("[rp-skip] decided to skip %r by %r (reason=%s)" % (title, artist, reason), flush=True)
    threading.Thread(target=_trigger_km_skip, daemon=True).start()

# button key -> Shortcut name (allowlist; nothing else can be triggered)
SCENES = {
    "kitchen":        "Panel Kitchen Lights",
    "kitchen_off":    "Panel Kitchen Off",
    "relax":          "Panel Relax",
    "meditate":       "Panel Meditate",
    "lr_off":         "Panel LR Off",
    "shades_open":    "Panel Shades Open",
    "shades_closed":  "Panel Shades Closed",
    "shades_partial": "Panel Shades Partial",
}

_lock = threading.Lock()
_state = {
    "feed": None,
    "artist": None,
    "title": None,
    "rating": None,
    "cover_url": None,
    "album": None,
    "released": None,
    "length": None,
    "avg_rating": None,
    "num_ratings": None,
    "rating_dist": None,
    "description": None,
    "playing": None,
    "updated_at": None,
}


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/api/homekit")
def homekit():
    with _hk_lock:
        return jsonify(dict(_hk_state))


@app.route("/nowplaying", methods=["GET", "POST", "OPTIONS"])
def nowplaying():
    if request.method == "OPTIONS":
        return ("", 204)
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        with _lock:
            for k in ("feed", "artist", "title", "rating", "cover_url",
                      "album", "released", "length", "avg_rating",
                      "num_ratings", "rating_dist", "playing"):
                if k in data:
                    _state[k] = data[k]
            _state["description"] = data.get("description", "")
            _state["updated_at"] = time.time()
            snap = dict(_state)
        _maybe_skip_track(snap.get("artist"), snap.get("title"), snap.get("rating"))
        return jsonify(ok=True, state=snap)
    with _lock:
        snap = dict(_state)
    with _skip_lock:
        snap["last_skip"] = _last_skip_event
    return jsonify(snap)


@app.route("/api/banned-list", methods=["GET", "POST", "OPTIONS"])
def banned_list():
    global _banned_entries, _last_skip_track
    if request.method == "OPTIONS":
        return ("", 204)
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        raw = data.get("list", "")
        entries = {p for p in (_parse_banned_line(l) for l in raw.splitlines()) if p}
        with _banned_lock:
            _banned_entries = entries
        _save_banned_list(entries)

        # If this push just banned whatever's currently playing, the macro
        # that pushed it is presumably about to skip that track itself (this
        # is exactly the "ban this track" flow) -- mark it as already
        # handled so /nowplaying doesn't race it and fire a second, redundant
        # skip for the same track.
        with _lock:
            cur_artist = (_state.get("artist") or "").strip().lower()
            cur_title = (_state.get("title") or "").strip().lower()
        matched = any(
            (typ in ("artist", "either") and val == cur_artist) or
            (typ in ("title", "either") and val == cur_title)
            for typ, val in entries
        )
        if matched:
            with _skip_lock:
                _last_skip_track = (cur_artist, cur_title)

        return jsonify(ok=True, count=len(entries))
    with _banned_lock:
        return jsonify(entries=sorted([typ, val] for typ, val in _banned_entries))


@app.route("/action/scene/<key>", methods=["POST", "OPTIONS"])
def action_scene(key):
    if request.method == "OPTIONS":
        return ("", 204)
    shortcut = SCENES.get(key)
    if not shortcut:
        return jsonify(ok=False, error="unknown scene", key=key), 404
    url = "http://%s:%d/action.html?macro=%s&value=%s" % (
        KM_HOST, KM_PORT, KM_MACRO, urllib.parse.quote(shortcut))
    try:
        urllib.request.urlopen(url, timeout=4)
    except Exception as e:
        return jsonify(ok=False, error=str(e), key=key), 502
    return jsonify(ok=True, key=key, shortcut=shortcut)


@app.route("/api/push/<key>", methods=["POST", "OPTIONS"])
def push_status(key):
    if request.method == "OPTIONS":
        return ("", 204)
    cfg = _load_ha_config()
    if not cfg:
        return jsonify(ok=False, error="no config"), 500
    info = cfg.get("entities", {}).get(key)
    if not info or not info.get("push"):
        return jsonify(ok=False, error="not pushable"), 403
    data = request.get_json(silent=True) or {}
    if "on" not in data:
        return jsonify(ok=False, error="missing 'on'"), 400
    raw = data["on"]
    on = False if raw in (False, 0, "false", "0", "off", "no") else bool(raw)
    with _hk_lock:
        _hk_state[key] = {"on": on, "name": info["name"]}
    return jsonify(ok=True, key=key, on=on)


@app.route("/action/ha/<key>/<service>", methods=["POST", "OPTIONS"])
def action_ha(key, service):
    if request.method == "OPTIONS":
        return ("", 204)
    cfg = _load_ha_config()
    if not cfg:
        return jsonify(ok=False, error="no config"), 500
    info = cfg.get("entities", {}).get(key)
    if not info or not info.get("controllable"):
        return jsonify(ok=False, error="not controllable"), 403
    if service not in ("turn_on", "turn_off", "toggle"):
        return jsonify(ok=False, error="bad service"), 400
    entity_id = info["entity"]
    domain = entity_id.split(".")[0]
    headers = {"Authorization": f"Bearer {cfg['token']}", "Content-Type": "application/json"}
    try:
        requests.post(
            f"{cfg['url']}/api/services/{domain}/{service}",
            headers=headers, json={"entity_id": entity_id}, timeout=5)
        return jsonify(ok=True, key=key, service=service)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 502


@app.route("/action/<name>", methods=["POST", "OPTIONS"])
def action(name):
    if request.method == "OPTIONS":
        return ("", 204)
    # Generic stub retained; scenes are handled by /action/scene/<key>.
    return jsonify(ok=True, action=name, note="stub - not yet wired")


@app.route("/cover-am")
def cover_am():
    path = os.path.join(HERE, "cover-am.jpg")
    if not os.path.exists(path):
        return ("", 404)
    resp = send_file(path, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp


@app.route("/cover-knkx")
def cover_knkx():
    path = os.path.join(HERE, "knkx.svg")
    if not os.path.exists(path):
        return ("", 404)
    return send_file(path, mimetype="image/svg+xml")


@app.route("/")
def index():
    return send_file(os.path.join(HERE, "index.html"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090, threaded=True)
