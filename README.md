# panel — now-playing wall display

A self-hosted now-playing display for a wall-mounted tablet. Shows album art and
metadata for the currently playing music source (Radio Paradise, Apple Music, or
KNKX Art of Jazz), driven by Keyboard Maestro on the Mac. Includes a home
automation scene bar backed by live device state from Home Assistant.

## Architecture

- A Flask app in a Docker container on Mini-S (`192.168.0.166:8090`) holds the
  current now-playing state in memory and serves the display page.
- A Lenovo Tab One on the wall runs Fully Kiosk Browser pointed at the page.
- Keyboard Maestro macros on the Mac scrape/read each source and POST state to
  the container. The container is source-agnostic — it stores and serves
  whatever was last posted.
- Home Assistant (`192.168.0.166:8123`) polls Hue, Lutron, and Aqara devices.
  The panel container polls HA every 5s and exposes state at `/api/homekit`.

Data flow (now-playing):

```
source (RP web player / Music app / KNKX stream)
  -> Keyboard Maestro publisher macro (per source, gated on DND_MusicSource)
  -> POST /nowplaying (JSON)
  -> container in-memory state
  -> GET /nowplaying (page polls every 3s)
  -> tablet display
```

Data flow (device state):

```
Hue bridge / Lutron Smart Bridge / Aqara Hub M3
  -> Home Assistant (polled every 5s via HA integrations)
  -> GET /api/homekit (panel polls HA every 5s)
  -> scene button state on tablet
```

## Endpoints

- `GET  /`              display page (index.html)
- `GET  /health`        health check
- `GET  /nowplaying`    current state as JSON
- `POST /nowplaying`    update state (merges provided fields)
- `GET  /api/homekit`   live device states (from Home Assistant)
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
  play state, cover) and posts it. Script source mirrored at
  `mac-scripts/rp_to_panel.applescript` (paste into the macro's Execute
  AppleScript step — KM doesn't export/import this piece on its own). Rewritten
  2026-08-25 for RP's Angular SPA redesign; selectors are specific to that DOM
  and will need updating if RP redesigns again.
- **Apple Music** — "AM to Panel": AppleScript reads the Music app, writes the
  track artwork to `app/cover-am.jpg`, and pipes fields to `~/ai/am_post.py`,
  which posts them. `cover_url` points at `/cover-am?id=<persistentID>`.
- **KNKX Art of Jazz** — "KNKX to Panel": posts a static payload (SVG cover +
  description). No per-track data; play/pause hidden.

A separate "Get Safari and RP status" macro checks whether the RP Safari tab is
playing/paused (used to drive play/pause toggling from elsewhere in KM,
independent of the publisher macro above). Script source mirrored at
`mac-scripts/rp_status.applescript`. Also rewritten 2026-08-25 for the same
site redesign — the old `.start-listening` element it read no longer exists in
the new DOM.

A "Play-Pause" macro checks current state with an Execute JavaScript in Front
Browser step (source mirrored at `mac-scripts/rp_playpause_state.js`,
returns `"Pause"`/`"Play"`), then branches to a toggle action that clicks
`#pause-button` (when playing) or `#play-button` (when paused/never-played)
directly in the Safari tab. The "playing" case (pause) is mirrored at
`mac-scripts/rp_pause.applescript`; the other cases are still just a one-line
`getElementById(...).click()` inline in the macro, no separate file. The
toggle clicks were rewritten 2026-08-25 for the redesign; the state check
followed on 2026-08-27 — it read `title="Pause"`/`title="Play"` attributes,
which the redesign had already dropped in favor of the same
`#pause-button`/`#play-button` ids the toggle actions use. `rp_pause.applescript`
itself regressed to clicking `#play-button` (a silent no-op while playing,
since that id only exists while paused) and was fixed back to `#pause-button`.

A "Set Song Rating" macro reads a KM variable and clicks the matching rating
value on the now-playing heart widget. Script source mirrored at
`mac-scripts/rp_set_rating.applescript`. Also rewritten 2026-08-25 — the heart
is now a `<button class="rating-heart-btn">` (was an `<img title="...">`); the
ten `.drating_N` rating-pill classes were unchanged by the redesign.

A "Select Music Feed" macro reads KM variable `RPFeedName` (must exactly match
a channel's display name, e.g. "The Main Mix", "Mellow Mix", "RockIt!", "The
Globe", "Beyond...", "Sanctuary", "Serenity", "My Paradise", "KFAT", "Radio
2050") and switches the RP web player to that channel. Script source mirrored
at `mac-scripts/rp_select_feed.applescript`. Also rewritten 2026-08-25 — the
channel switcher used to be an Angular Material menu
(`.mat-menu-trigger.channel-selector` / `.mat-menu-content [mat-menu-item]`);
it's now a `.action-channels` toggle button that expands a `.channel-list` of
`.channel-row` buttons. The old version also re-injected an inline
track-change tracker (polling stale selectors, POSTing to a
trigger.keyboardmaestro.com webhook) that duplicated `rp_to_panel.applescript`
and was silently broken since the redesign — dropped rather than fixed.

## Home scenes (panel buttons)

The bottom button bar fires HomeKit scenes and shows live device state.

### Scene firing flow

```
tablet button -> POST /action/scene/<key>
             -> container looks up key in the SCENES allowlist (main.py)
             -> GET http://<mac>:4490/action.html?macro=<UID>&value=<ShortcutName>
             -> KBM "Set Home Scene" macro runs: shortcuts run "<ShortcutName>"
```

- **KBM macro "Set Home Scene"** (UID in `KM_MACRO`): Public Web trigger,
  available in all applications. Two actions:
    1. Set Variable `DND_PanelScene` to `%TriggerValue%`
    2. Execute Shell Script: `/usr/bin/shortcuts run "$KMVAR_DND_PanelScene"`
- **Shortcuts**: one per scene, each a Control Home action. Names use a `Panel `
  prefix (e.g. `Panel Relax`) to avoid colliding with HomeKit scene names.
- **KM Web Server**: enabled in KM Settings → Web Server (port 4490).

### Button visual states

Each button reflects the live state of its associated devices:

- **Grey bulb** — all devices in the scene are off
- **White bulb** — any device is on (regardless of brightness)
- **Green box** — this scene is active: either just commanded (held for settle
  period) or actual device state matches the commanded levels

The settle period is 3.5s for lights and 20s for curtains (which take longer
to physically move). After settling, the panel snapshots actual brightness/
position and compares on each poll. If an external change drifts state away
from the snapshot, the green box drops.

### Scene → device mapping

| Scene key | Devices |
|---|---|
| `kitchen` / `kitchen_off` | Lutron: Kitchen_Main Lights, Kitchen_Under Cabinet |
| `relax` / `meditate` / `lr_off` | Hue: Table Lamp, Floor Lamp |
| `shades_open` / `shades_closed` / `shades_partial` | Aqara: CurtainLR/LL/RR/RL |

## Home Assistant

HA runs in a separate compose stack at `../homeassistant/`.

```
homeassistant/
├── docker-compose.yml   HA + matter-server (both network_mode: host)
├── config/              HA config (gitignored if checked in separately)
└── matter-data/         matter-server state
```

HA integrations configured:
- **Philips Hue** (bridge at 192.168.0.25)
- **Lutron Caseta** (Smart Bridge Pro 2 at 192.168.0.121)
- **Aqara** (cloud integration — exposes curtain `cover.*` entities)
- **Matter** (with matter-server at `ws://localhost:5580/ws`, for Aqara M3 bridge)

The panel reads entity states via HA's REST API using a Long-Lived Access Token
stored in `creds/ha.json` (gitignored). Entity ID mapping is also in that file.

## Files

```
panel/
├── docker-compose.yml   panel service (port 8090, app/ volume-mounted)
├── Dockerfile           python:3.12-slim + flask + requests
├── requirements.txt     flask, requests
├── app/
│   ├── main.py          Flask app (now-playing state, HA polling, scene relay)
│   ├── index.html       display page + scene bar JS
│   └── knkx.svg         KNKX cover graphic
├── creds/               gitignored; contains ha.json (HA token + entity map)
└── mac-scripts/         source that runs on the Mac inside KM macros
    ├── am_post.py               posts AM track fields to the panel
    ├── rp_to_panel.applescript  scrapes RP web player DOM, returns JSON
    ├── rp_status.applescript    checks RP tab's play/pause state
    ├── rp_playpause_state.js    checks RP play/pause state for the Play-Pause macro
    ├── rp_pause.applescript    clicks #pause-button in the RP tab (Play-Pause macro's playing case)
    ├── rp_set_rating.applescript  clicks a rating value on the RP heart widget
    └── rp_select_feed.applescript  switches the RP channel/feed
```

`app/cover-am.jpg` is written at runtime by the AM macro (gitignored).

`mac-scripts/` mirrors source that actually runs on the Mac inside Keyboard
Maestro macros — `am_post.py` is invoked from a shell script action;
`rp_to_panel.applescript` is pasted directly into an Execute AppleScript
action. Neither is picked up automatically by KM; copy changes over by hand.

## Deploy / iterate

- First build: `docker compose up -d --build`
- `main.py` change: `docker compose build --no-cache && docker compose up -d`
- `index.html` / `knkx.svg` change: just reload the tablet (app/ is volume-mounted)
- `creds/ha.json` change: `docker compose restart panel`

Tablet: Fully Kiosk Browser, start URL `http://192.168.0.166:8090`,
Keep Screen On + Start on Boot enabled.
