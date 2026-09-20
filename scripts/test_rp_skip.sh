#!/bin/bash
# Manually exercises the panel's RP auto-skip feature (banned artist/title +
# low rating) without waiting for a banned or low-rated track to actually
# come up on Radio Paradise.
#
# IMPORTANT: both tests below make the panel fire the REAL skip macro
# (144A8A9E-ABF0-440F-B843-2C497A19C59B) against your actual Mac -- that's
# intentional, it's what makes this a true end-to-end test, but it means
# whatever is really playing on RP at the time will really get skipped.
# Run it when you're at the panel/Mac and can watch it happen, not as a
# background sanity check.
#
# Usage: scripts/test_rp_skip.sh [panel-base-url]
#   defaults to http://192.168.0.166:8090
set -euo pipefail
PANEL="${1:-http://192.168.0.166:8090}"

echo "== Test 1: low-rating skip =="
echo "(doesn't touch the banned list at all -- lowest-risk test)"
curl -s -X POST "$PANEL/nowplaying" -H "Content-Type: application/json" \
  -d '{"feed":"TEST","artist":"Test Artist (low rating)","title":"Test Track A","rating":"3","playing":true}' > /dev/null
echo "Posted a fake now-playing track rated 3/10. Check the panel screen for the"
echo "'Skipping — Rated 3/10' banner, and confirm RP actually skipped."
echo

read -p "Press Enter to continue to the banned-artist test (or Ctrl-C to stop here)... "

echo "== Test 2: banned-artist skip =="
echo "Backing up your real banned list first so this test can't clobber it..."
backup=$(curl -s "$PANEL/api/banned-list" | python3 -c '
import json, sys
print(json.dumps(json.load(sys.stdin)["entries"]))
')
echo "$backup" > /tmp/rp_banned_list_backup.json
n=$(python3 -c "import json; print(len(json.load(open('/tmp/rp_banned_list_backup.json'))))")
echo "Backed up $n existing entries to /tmp/rp_banned_list_backup.json"

test_list=$(python3 -c "
import json
entries = json.load(open('/tmp/rp_banned_list_backup.json'))
entries.append('Test Banned Artist')
print(chr(10).join(entries))
")
curl -s -X POST "$PANEL/api/banned-list" -H "Content-Type: application/json" \
  -d "$(python3 -c "import json,sys; print(json.dumps({'list': sys.argv[1]}))" "$test_list")" > /dev/null

curl -s -X POST "$PANEL/nowplaying" -H "Content-Type: application/json" \
  -d '{"feed":"TEST","artist":"Test Banned Artist","title":"Test Track B","rating":"","playing":true}' > /dev/null
echo "Posted a fake now-playing track by a freshly-banned test artist. Check the"
echo "panel screen for the 'Skipping — Banned' banner, and confirm RP actually skipped."
echo

echo "Restoring your real banned list..."
curl -s -X POST "$PANEL/api/banned-list" -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json
entries = json.load(open('/tmp/rp_banned_list_backup.json'))
print(json.dumps({'list': chr(10).join(entries)}))
")" > /dev/null
echo "Restored. Done."
