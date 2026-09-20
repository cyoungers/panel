// "Play-Pause" Keyboard Maestro macro's state-check step (KM "Execute
// JavaScript in Front Browser" action, run against the Safari tab showing
// the Radio Paradise web player). Determines whether RP is currently playing
// or paused so the macro can branch to the matching toggle action. Returns
// "Pause" (RP is playing -- a pause button is present) or "Play" (RP is
// paused/never played -- a play button is present).
//
// Matches the post-2026-08 Angular SPA redesign of radioparadise.com, which
// dropped the old title="Pause"/title="Play" attributes in favor of plain
// ids (#pause-button / #play-button) -- same id-swap this script's original
// title-attribute selectors needed to follow.

var scriptResults = "";

var node = document.getElementById('pause-button');
//If it isn't "null", then it exists.
if (node != null) {
   scriptResults = "Pause";
}
var node = document.getElementById('play-button');
//If it isn't "null", then it exists.
if (node != null) {
   scriptResults = "Play";
}

scriptResults
