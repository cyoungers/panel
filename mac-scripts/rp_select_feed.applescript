# "Select Music Feed" Keyboard Maestro macro step. Reads the desired channel
# name from KM variable "RPFeedName" (must exactly match a channel's display
# name, e.g. "The Main Mix", "Mellow Mix", "RockIt!") and switches the Radio
# Paradise web player to it. Matches the post-2026-08 Angular SPA redesign of
# radioparadise.com: the channel switcher is no longer an Angular Material
# menu (`.mat-menu-trigger.channel-selector` / `.mat-menu-content
# [mat-menu-item]`) — it's now a `.action-channels` toggle button that expands
# a `.channel-list` of `.channel-row` buttons, each holding the channel name
# in a `.channel-row__title` span.
#
# The old version of this script also re-injected an inline track-change
# tracker (polling `.player-title`/`.player-artist`/`.rating-heart img` and
# POSTing to a trigger.keyboardmaestro.com webhook on change). Those selectors
# no longer exist post-redesign, and that job is now handled by
# rp_to_panel.applescript posting to the panel's own /nowplaying endpoint, so
# the tracker was dropped here rather than fixed.
tell application "Keyboard Maestro Engine"
	set feedName to getvariable "RPFeedName"
end tell

if feedName is "" then
	display alert "No feed name set"
	return
end if

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

	-- If no tab found, open one
	if rpTab is missing value then
		set firstWindow to first window
		set newTab to make new tab at end of tabs of firstWindow with properties {URL:"https://radioparadise.com/player"}
		set current tab of firstWindow to newTab
		delay 2
		set rpTab to current tab of front window
	end if

	set jsCmd to "
	(function(feedName) {
	  // Auto-press play if paused
	  const playBtn = document.getElementById('play-button');
	  if (playBtn && playBtn.getAttribute('aria-label') === 'Play') {
	    playBtn.click();
	    console.log('▶️ Auto-play triggered');
	  }

	  function selectChannel() {
	    const rows = document.querySelectorAll('.channel-list .channel-row');
	    const target = Array.from(rows).find(r => {
	      const title = r.querySelector('.channel-row__title');
	      return title && title.textContent.trim() === feedName;
	    });
	    if (target) {
	      target.click();
	      console.log('🎛 Selected feed:', feedName);
	    } else {
	      console.warn('❌ Feed not found in channel list:', feedName);
	    }
	  }

	  const channelsBtn = document.querySelector('.action-channels');
	  if (!channelsBtn) {
	    throw new Error('Channel selector button (.action-channels) not found');
	  }

	  if (channelsBtn.getAttribute('aria-expanded') === 'true') {
	    selectChannel();
	  } else {
	    channelsBtn.click();
	    console.log('🔽 Opened channel menu for feed:', feedName);
	    setTimeout(selectChannel, 500);
	  }
	})(" & quoted form of feedName & ");
	"

	try
		do JavaScript jsCmd in rpTab
	on error errMsg
		display alert "JS error: " & errMsg
	end try
end tell
