#!/usr/bin/env bash
# Saves a resume HTML file as a PDF next to it, using a Chromium-based browser
# in headless mode if one is installed. Prints the PDF path, or explains how to
# save it from the browser instead.
#   render_pdf.sh path/to/resume.html [output.pdf]
set -euo pipefail
HTML="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUT="${2:-${HTML%.html}.pdf}"
CANDIDATES=(
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
  "/Applications/Chromium.app/Contents/MacOS/Chromium"
  google-chrome google-chrome-stable chromium chromium-browser microsoft-edge brave-browser
)
for c in "${CANDIDATES[@]}"; do
  if [ -x "$c" ] || command -v "$c" >/dev/null 2>&1; then
    "$c" --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="$OUT" "file://$HTML" >/dev/null 2>&1 || true
    if [ -s "$OUT" ]; then echo "$OUT"; exit 0; fi
  fi
done
echo "No Chromium-based browser found for automatic PDF export." >&2
echo "Open $HTML in your browser, choose Print, then Save as PDF (turn off headers and footers)." >&2
exit 2
