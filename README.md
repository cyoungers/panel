# panel — now-playing wall display

A self-hosted now-playing display for a wall-mounted tablet. Shows album art and
metadata for the currently playing music source (Radio Paradise, Apple Music, or
KNKX Art of Jazz), driven by Keyboard Maestro on the Mac.

## Architecture

- A Flask app in a Docker container on Mini-S (`192.168.0.166:8090`) holds the
  current now-playing state in memory and serves the display page.
- A Lenovo Tab One on the wall runs Fully Kiosk Browser pointed at the page.
- Keyboard Maestro macros on the Mac scrape/read each source and POST state to
  the container. The container is source-agnostic — it stores and serves
  whatever was last posted.

Data flow:

```
source (RP web player / Music app / KNKX stream)
  -> Keyboard Maestro publisher macro (per source, gated on DND_MusicSource)
  -> POST /nowplaying (JSON)
  -> container in-memory state
  -> GET /nowplaying (page polls every 3s)
  -> tablet display
```

## Endpoints

- `GET  /`              display page (index.html)
- `GET  /health`        health check
- `GET  /nowplaying`    current state as JSON
- `POST /nowplaying`    update state (merges provided fields)
- `POST /action/scene/<key>`  fire a Home scene (see Home scenes below)
- `POST /action/<name>` generic stub (unused)
- `GET  /cover-am`      current Apple Music artwork (written by the AM macro)
- `GET  /cover-knkx`    KNKX Art of Jazz cover graphic (static SVG)

## State fields

`feed, artist, title, album, released, length, rating, avg_rating, num_ratings,
rating_dist (list), cover_url, playing (true/false/null), description,
updated_at`

`description` and `playing` clear automatically when a POST omits them, so
they don't linger across source switches.

## Sources (Keyboard Maestro)

The "Select Music Feed" macro sets the global `DND_MusicSource` to `RP` / `AM` /
`KNKX`. Each publisher macro is periodic and exits unless its source is active.

- **Radio Paradise** — "RP to Panel": AppleScript scrapes the RP web player DOM
  (title, artist, album, date, length, your rating, average, rating histogram,
  play state, cover) and posts it.
- **Apple Music** — "AM to Panel": AppleScript reads the Music app, writes the
  track artwork to `app/cover-am.jpg`, and pipes fields to `~/ai/am_post.py`,
  which posts them. `cover_url` points at `/cover-am?id=<persistentID>`.
- **KNKX Art of Jazz** — "KNKX to Panel": posts a static payload (SVG cover +
  description). No per-track data; play/pause hidden.

## Home scenes (panel buttons)

The bottom button bar fires HomeKit scenes. Flow (event-driven, no polling):

```
tablet button -> POST /action/scene/<key>
             -> container looks up key in the SCENES allowlist (main.py)
             -> GET http://<mac>:4490/action.html?macro=<UID>&value=<ShortcutName>
             -> KBM "Set Home Scene" macro runs: shortcuts run "<ShortcutName>"
```

Pieces, and the non-obvious bits:

- **Container** (`main.py`): `KM_HOST` / `KM_PORT` / `KM_MACRO` constants, and the
  `SCENES` dict maps button key -> Shortcut name. That dict is the allowlist —
  nothing else can be triggered. Add a scene = add a dict entry + a button.
- **KBM macro "Set Home Scene"** (its UID is `KM_MACRO`): must have a **Public
  Web** trigger and be in a macro group available in **all applications**, or the
  web server returns "Macro not found". Two actions:
    1. Set Variable `DND_PanelScene` to `%TriggerValue%`
    2. Execute Shell Script: `/usr/bin/shortcuts run "$KMVAR_DND_PanelScene"`
  The value is bound to a variable first because Execute Shell Script does NOT
  expand `%...%` tokens in its script body (ordinary text fields do).
- **Shortcuts**: one per scene, each a Control Home action. Names use a `Panel `
  prefix (e.g. `Panel Relax`) because a Shortcut can't share a name with a
  HomeKit scene.
- **KM Web Server**: enabled in KM Settings -> Web Server (port 4490).

Buttons are momentary (set-only); the panel shows no on/off state because
HomeKit doesn't report it back. Lights use per-room Off buttons instead of
toggles (two LR scenes share the same lights, so a toggle would be ambiguous).

## Files

- `docker-compose.yml`  service (port 8090, `app/` volume-mounted for iteration)
- `Dockerfile`          python:3.12-slim + flask
- `requirements.txt`    flask
- `app/main.py`         Flask app
- `app/index.html`      display page (polls `/nowplaying`)
- `app/knkx.svg`        KNKX cover graphic
- `app/cover-am.jpg`    runtime: current AM artwork (gitignored)

Note: `~/ai/am_post.py` lives on the Mac (where Keyboard Maestro runs), not in
this repo.

## Deploy / iterate

- First build: `docker compose up -d --build`
- `main.py` change: `docker restart panel` (`app/` is volume-mounted)
- `index.html` / `knkx.svg` change: just reload the tablet
- Dockerfile/compose/requirements change: `docker compose up -d --build`

Tablet: Fully Kiosk Browser, start URL `http://192.168.0.166:8090`,
Keep Screen On + Start on Boot enabled.
