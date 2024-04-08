#!/bin/bash

DEFAULT_WEBSITE="about:blank"
# Point to current directory
export SSLKEYLOGFILE="$(dirname $0)/keylogfile.txt"

case "$(uname -s)" in
Linux*)
	BROWSER_BINS=(chromium google-chrome firefox brave librewolf icecat)
	# Kill all browser processes
	for BROWSER_BIN in "${BROWSER_BINS[@]}"; do
		if command -v "$BROWSER_BIN" &>/dev/null; then
			killall -9 "$BROWSER_BIN" &>/dev/null
		fi
	done

	WEBSITE="$@"
	if [ -z "$WEBSITE" ] || [[ ! "$WEBSITE" =~ ^http ]]; then
		WEBSITE="$DEFAULT_WEBSITE"
		echo "Fallback to $DEFAULT_WEBSITE"
	fi

	# Open default browser
	xdg-open "$WEBSITE"
	;;
Darwin*)
	open "$@"
	;;
esac
