# "Get Safari and RP status" Keyboard Maestro macro step. Finds the Radio
# Paradise tab in Safari and reports its play/pause state as one of:
# "Safari Not Running", "Safari Running and RP Tab Not Found", or
# "Safari Running and RP Tab Found – RP playing / RP active but paused /
# RP active but never played". Result saved to variable "Local_SafariRPStatus".
# Matches the post-2026-08 Angular SPA redesign of radioparadise.com.
if application "Safari" is running then
	tell application "Safari"
		set rpTab to missing value
		set playerState to ""

		repeat with w in windows
			repeat with t in tabs of w
				if (URL of t contains "radioparadise.com") then
					set rpTab to t
					-- run your JavaScript in the tab
					set playerState to do JavaScript "
                          (function() {
                            if (document.getElementById('pause-button')) {
                              return 'RP playing';
                            } else if (document.getElementById('play-button')) {
                              return 'RP active but paused';
                            }
                            return 'RP active but never played';
                          })();
                        " in rpTab

					exit repeat
				end if
			end repeat
			if rpTab is not missing value then exit repeat
		end repeat

		if rpTab is missing value then
			set RPstatus to "Safari Running and RP Tab Not Found"
		else
			set RPstatus to "Safari Running and RP Tab Found – " & playerState
		end if
	end tell
else
	set RPstatus to "Safari Not Running"
end if

return RPstatus
