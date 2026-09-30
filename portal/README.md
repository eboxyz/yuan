# Setup page

A single static page (plain HTML, CSS and JavaScript; no framework, no build
tool, no outside requests). People answer the setup questions, and the page
builds a zip in their browser: their answers (`intake.json`), their resume, the
`tracker-setup` skill, a starter `CLAUDE.md` and `START_HERE.txt`. Opening that
folder with Claude builds their tracker. Answers autosave to the browser's
local storage; nothing is sent anywhere.

- `index.html`, `styles.css`, `app.js`: the page. Question wording comes from
  `tracker-setup/intake.schema.json` (`title`, `description`, `x-labels`,
  `x-help`, `x-default`), so the page and the generated tracker say the same thing.
- `lib.js`: the zip writer, the validator (same rules and messages as
  `tracker-setup/scripts/intake.py`) and the package builder. No page code, so it
  runs under Node for testing.
- `skill-bundle.js`: generated. After changing anything in `tracker-setup/`, run
  `python3 portal/build.py` (`--check` tells you if it's stale).

Preview: open `index.html` in a browser, or serve the folder with any static
server (`python3 -m http.server -d portal 8600`). Deep links: `#step=want`.
Host it anywhere that serves static files.
