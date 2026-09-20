#!/bin/bash
# An "Execute Shell Script" step at the end of the user's own "ban
# artist/song" Keyboard Maestro macro (the one that appends a line to
# DND_RPBannedArtistList and calls the skip-track macro). Its own macro
# group is DABCD81D-FCDC-40B5-9CA8-3EDF83549282.
#
# Action input: set to "%Variable%DND_RPBannedArtistList%", passed to this
# script via stdin (KM's "Pass input: to stdin" option). MUST be run as a KM
# action, not invoked directly from a terminal -- %Variable%...% substitution
# only happens inside KM's own execution, so running this .sh file by hand
# sends an empty list and wipes the panel's copy of the real one.
#
# Each line the ban macro appends should be tagged with what kind of ban it
# is, so the panel's skip banner can say exactly why: prefix with "A|" for a
# banned artist (e.g. "A|Nickelback") or "T|" for a banned track title (e.g.
# "T|Free Bird"). An untagged line still works -- matched against both
# artist and title -- for backward compatibility with older entries.
#
# Wraps the variable's raw text in a JSON body and POSTs it to the panel's
# /api/banned-list endpoint, which replaces its in-memory banned set and
# persists it to creds/rp_banned_list.json. Uses python3's json.dumps (not
# shell string concatenation) so quotes/newlines in the list can't break the
# JSON.

python3 -c '
import json, sys, urllib.request

text = sys.stdin.read()
body = json.dumps({"list": text}).encode()
req = urllib.request.Request(
    "http://192.168.0.166:8090/api/banned-list",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
urllib.request.urlopen(req, timeout=5)
'
