#!/bin/sh
# Regenerates assets/flowchart.png from assets/flowchart.html via headless Chrome.
# Usage: sh assets/generate-flowchart.sh   (from anywhere)
set -e
cd "$(dirname "$0")"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
HEIGHT="${HEIGHT:-1000}"
"$CHROME" --headless --screenshot="$PWD/flowchart.png" \
  --window-size=1276,"$HEIGHT" --hide-scrollbars --default-background-color=FFFFFFFF \
  "file://$PWD/flowchart.html" 2>/dev/null
echo "wrote $PWD/flowchart.png (1276x$HEIGHT)"
