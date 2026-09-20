# "Pause RP" Keyboard Maestro macro step. Finds the Radio Paradise tab in
# Safari and clicks the pause button. Only meant to run while RP is playing
# (gated elsewhere in the macro, typically on rp_playpause_state.js's
# "Pause" result) -- #pause-button only exists in the DOM while playing, so
# running this while already paused is a silent no-op (?.click() on null).
# Matches the post-2026-08 Angular SPA redesign of radioparadise.com.
tell application "Safari"
    activate
    set rpTab to missing value

    repeat with w in windows
        repeat with t in tabs of w
            if (URL of t contains "radioparadise.com") then
                set rpTab to t
                exit repeat
            end if
        end repeat
        if rpTab is not missing value then exit repeat
    end repeat

    if rpTab is missing value then
        display alert "No Radio Paradise tab found"
        return
    end if

    tell rpTab to do JavaScript "document.getElementById('pause-button')?.click();"
end tell
