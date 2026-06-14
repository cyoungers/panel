import os
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
                s = states.get(info["entity"])
                if not s:
                    continue
                attrs = s.get("attributes", {})
                if info["entity"].startswith("cover."):
                    pos = attrs.get("current_position", 0)
                    updates[key] = {"on": pos > 0, "bri": pos, "name": info["name"]}
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
        return jsonify(ok=True, state=snap)
    with _lock:
        return jsonify(dict(_state))


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
