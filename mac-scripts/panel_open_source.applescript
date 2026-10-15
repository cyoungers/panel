-- "Panel - Open Music Source" (KM macro, Public Web trigger, group Home::Remote Triggers).
-- Fired when the panel's music area is tapped. Brings the current source
-- (DND_MusicSource: RP / AM / KNKX) to the front on the Mac.

on showSafariTab(urlPart, fallbackURL)
	tell application "Safari"
		repeat with w in windows
			try
				set t to (first tab of w whose URL contains urlPart)
				set miniaturized of w to false
				set current tab of w to t
				set index of w to 1
				activate
				return
			end try
		end repeat
		activate
		open location fallbackURL
	end tell
end showSafariTab

tell application "Keyboard Maestro Engine" to set src to getvariable "DND_MusicSource"

if src is "AM" then
	tell application "Music" to activate
else if src is "KNKX" then
	showSafariTab("knkx.org", "https://www.knkx.org/")
else
	showSafariTab("radioparadise.com", "https://radioparadise.com/player")
end if
