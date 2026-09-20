# Execute AppleScript step of the "RP to Panel" Keyboard Maestro macro.
# Scrapes the Radio Paradise web player DOM in the open Safari tab and returns
# the now-playing JSON as the macro's "RPPanelJSON" variable (a later action
# POSTs it to the panel's /nowplaying endpoint). Matches the post-2026-08
# Angular SPA redesign of radioparadise.com.
# If the RP tab can't be found, or the tab has navigated off the player view
# (e.g. to a settings/account page) so the now-playing DOM elements are gone,
# falls back to the previous RPPanelJSON value instead of clobbering it with
# "" -- an empty value breaks downstream %JSONValue%RPPanelJSON...% lookups
# in macros that process this variable.
tell application "Safari"
	set theTab to missing value
	repeat with w in windows
		repeat with t in tabs of w
			if (URL of t) contains "radioparadise.com" then
				set theTab to t
				exit repeat
			end if
		end repeat
		if theTab is not missing value then exit repeat
	end repeat
	if theTab is missing value then
		tell application "Keyboard Maestro Engine" to return getvariable "RPPanelJSON"
	end if
	set js to "(function(){var t=document.querySelector('.now-title'),a=document.querySelector('.now-artist');if(!t||!a)return '';var albumEls=document.querySelectorAll('.now-album');var album=albumEls[0]?albumEls[0].textContent.trim():'';var relLen=albumEls[1]?albumEls[1].textContent:'';var released='',length='';var rm=relLen.match(/RELEASED:\\s*([\\d-]+)/);if(rm)released=rm[1];var lm=relLen.match(/LENGTH:\\s*([\\d:]+)/);if(lm)length=lm[1];var coverEl=document.querySelector('.now-album-cover');var cover=coverEl?coverEl.src.replace('/covers/m/','/covers/l/'):'';var avgText=(document.querySelector('.now-rating-info')||{}).textContent||'';var am=avgText.match(/Avg\\.\\s*([\\d.]+)/);var avg=am?am[1]:'';var nm=avgText.match(/\\((\\d+)\\)/);var num=nm?nm[1]:'';var rh=document.querySelector('.rating-heart-btn');var ratingLabel=rh?(rh.getAttribute('aria-label')||''):'';var yrm=ratingLabel.match(/rating:\\s*(.+)$/i);var yourRaw=yrm?yrm[1].trim():'';var rating=(yourRaw===''||yourRaw==='--')?'':yourRaw;var cells=document.querySelectorAll('#now-playing-rating .ratings-cell');var dist=[];for(var j=0;j<cells.length;j++){var ti=cells[j].getAttribute('title')||'';var dm=ti.match(/^(\\d+)\\s*votes:\\s*(\\d+)/);dist.push({n:dm?parseInt(dm[1]):j+1,count:dm?parseInt(dm[2]):0});}var chanEl=document.querySelector('.channel-title-button');var chan=chanEl?chanEl.textContent.trim():'';var playing=null;if(document.getElementById('pause-button'))playing=true;else if(document.getElementById('play-button'))playing=false;return JSON.stringify({feed:chan,artist:a.textContent.trim(),title:t.textContent.trim(),rating:rating,cover_url:cover,album:album,released:released,length:length,avg_rating:avg,num_ratings:num,rating_dist:dist,playing:playing});})()"
	set theResult to (do JavaScript js in theTab)
	if theResult is "" then
		tell application "Keyboard Maestro Engine" to return getvariable "RPPanelJSON"
	end if
	return theResult
end tell
