import os
import time
import threading
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))

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


@app.route("/action/<name>", methods=["POST", "OPTIONS"])
def action(name):
    if request.method == "OPTIONS":
        return ("", 204)
    # Stub: relay target (KBM trigger / Homebridge) wired in a later step.
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
