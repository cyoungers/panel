# "Set Song Rating" Keyboard Maestro macro step. Reads the desired rating
# (1-10) from the KM variable "RPSongRating", opens the rating popup on the
# Radio Paradise now-playing heart, and clicks the matching value. Matches the
# post-2026-08 Angular SPA redesign of radioparadise.com: the heart is now a
# `<button class="rating-heart-btn">` (was an `<img title="...">`), while the
# ten rating-pill classes (`.drating_1` .. `.drating_10`) are unchanged from
# the pre-redesign site.
tell application "Keyboard Maestro Engine"
	set rawRating to getvariable "RPSongRating"
end tell

if rawRating is "" then
	display alert "No rating set"
	return
end if

set myRating to word 1 of rawRating

set jsCmd to "(function(){" & ¬
	"var heart=document.querySelector(" & quote & ".rating-heart-btn" & quote & ");" & ¬
	"if(!heart){return;}heart.click();" & ¬
	"setTimeout(function(){" & ¬
	"var el=document.querySelector(" & quote & ".drating_" & myRating & quote & ");" & ¬
	"if(el){el.click();}else{heart.click();}" & ¬
	"},500);" & ¬
	"})();"

tell application "Safari"
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
	try
		tell rpTab to do JavaScript jsCmd
	on error errMsg
		display alert "JS error: " & errMsg
	end try
end tell
