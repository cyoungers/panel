# Execute Shell Script step of the "RP to panel" Keyboard Maestro macro
# (B38576E1-D836-4B0E-8605-9859EBFCE746), after rp_to_panel.applescript has
# set RPPanelJSON. Runs every 5s while RP plays. Needs "Include all
# variables" on the action so the KMVAR_ env vars below are present.
#
# Also attaches the raw DND_RPBannedArtistList text as "banned_list" so the
# panel's copy of the banned list stays in sync however the variable is
# edited (the ban macro pushes on its own, but "Edit Banned artist List"
# and "RP Player Tracker notifiy" change it without pushing). If the merge
# fails for any reason, posts RPPanelJSON unchanged, as before.
if [ -n "$KMVAR_RPPanelJSON" ]; then
  body=$(/usr/bin/python3 -c '
import json, os
d = json.loads(os.environ["KMVAR_RPPanelJSON"])
if "KMVAR_DND_RPBannedArtistList" in os.environ:
    d["banned_list"] = os.environ["KMVAR_DND_RPBannedArtistList"]
print(json.dumps(d))
' 2>/dev/null) || body="$KMVAR_RPPanelJSON"
  curl -s -X POST http://192.168.0.166:8090/nowplaying \
    -H "Content-Type: application/json" \
    -d "$body" >/dev/null
fi
