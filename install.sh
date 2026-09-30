#!/usr/bin/env bash
# Yuan installer.
#
# Checks for what the tracker needs (Claude Code, Python 3, Postgres), offers
# to install anything missing, and installs the /tracker-setup skill into
# ~/.claude/skills. Asks before installing anything. Safe to run again.
#
#   ./install.sh              interactive
#   ./install.sh --yes        answer yes to every prompt
#   ./install.sh --uninstall  remove the skill (leaves Claude Code/Python/Postgres alone)
set -euo pipefail

REPO_URL="${JST_REPO_URL:-https://github.com/eboxyz/yuan}"
SKILL_DEST="$HOME/.claude/skills/tracker-setup"
ASSUME_YES=0
UNINSTALL=0
NEED_PATH_FIX=0

for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)"; exit 1 ;;
  esac
done

say()  { printf '\n%s\n' "$*"; }
ok()   { printf '  ✓ %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

confirm() {
  [ "$ASSUME_YES" = 1 ] && return 0
  local reply=""
  if { read -r -p "  $1 [y/N] " reply </dev/tty; } 2>/dev/null; then
    case "$reply" in y|Y|yes|YES) return 0 ;; esac
  fi
  return 1
}

if [ "$UNINSTALL" = 1 ]; then
  rm -rf "$SKILL_DEST"
  say "Removed $SKILL_DEST. Claude Code, Python and Postgres were left as they were."
  exit 0
fi

OS="$(uname -s)"
case "$OS" in
  Darwin|Linux) ;;
  *) echo "This installer supports macOS and Linux. On Windows, use WSL and run it there."; exit 1 ;;
esac
SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

say "Yuan — checking your setup"

# ---- Claude Code ----------------------------------------------------------
if have claude; then
  ok "Claude Code is installed"
else
  echo "  Claude Code isn't installed."
  if confirm "Install it now (official installer from claude.ai)?"; then
    curl -fsSL https://claude.ai/install.sh | bash
    case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) NEED_PATH_FIX=1 ;; esac
    export PATH="$HOME/.local/bin:$PATH"
    have claude && ok "Claude Code installed" || echo "  Claude Code didn't install correctly — see https://claude.ai/code"
  else
    echo "  Skipping. You'll need it: https://claude.ai/code"
  fi
fi

# ---- Python 3 ---------------------------------------------------------------
py_ok() { have python3 && python3 -c 'import sys, venv; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; }
if py_ok; then
  ok "Python $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])') is installed"
else
  echo "  Python 3.9+ (with venv) isn't available."
  if [ "$OS" = Darwin ]; then
    if have brew && confirm "Install it with Homebrew (brew install python)?"; then brew install python; fi
  elif have apt-get && confirm "Install it with apt (python3 python3-venv)?"; then
    $SUDO apt-get update -qq && $SUDO apt-get install -y python3 python3-venv
  fi
  py_ok && ok "Python is ready" || { echo "  Please install Python 3.9+ (https://python.org) and run this again."; exit 1; }
fi

# ---- Postgres ---------------------------------------------------------------
pg_running() { have pg_isready && pg_isready -q; }
if have psql && have createdb; then
  ok "Postgres tools are installed"
else
  echo "  Postgres isn't installed."
  if [ "$OS" = Darwin ]; then
    if have brew; then
      confirm "Install it with Homebrew (brew install postgresql@16)?" && brew install postgresql@16 \
        && export PATH="$(brew --prefix postgresql@16)/bin:$PATH"
    else
      echo "  No Homebrew found. Install Postgres.app (https://postgresapp.com) or Homebrew (https://brew.sh), then run this again."
      exit 1
    fi
  elif have apt-get; then
    confirm "Install it with apt (postgresql)?" && { $SUDO apt-get update -qq && $SUDO apt-get install -y postgresql; }
  else
    echo "  Please install Postgres with your package manager, then run this again."; exit 1
  fi
  have psql && have createdb || { echo "  Postgres still isn't available — skipping."; }
fi

if have psql && ! pg_running; then
  echo "  Postgres isn't running."
  if confirm "Start it?"; then
    if [ "$OS" = Darwin ]; then
      have brew && brew services start postgresql@16 || echo "  Open Postgres.app to start it."
    else
      $SUDO systemctl start postgresql 2>/dev/null || $SUDO service postgresql start
    fi
    for _ in 1 2 3 4 5 6 7 8 9 10; do pg_running && break; sleep 1; done
  fi
fi

# On Linux, Postgres only knows the 'postgres' user; the tracker connects as you.
if [ "$OS" = Linux ] && pg_running; then
  if ! psql -d postgres -tAc "SELECT 1" >/dev/null 2>&1; then
    echo "  Postgres has no database user for you ($USER)."
    if confirm "Create one (sudo -u postgres createuser --superuser $USER)?"; then
      $SUDO -u postgres createuser --superuser "$USER" 2>/dev/null || true
    fi
  fi
fi
if pg_running && psql -d postgres -tAc "SELECT 1" >/dev/null 2>&1; then
  ok "Postgres is running and you can connect to it"
else
  echo "  ! Postgres isn't ready — /tracker-setup will help you finish this."
fi

# ---- The skill --------------------------------------------------------------
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$HERE" ] && [ -f "$HERE/tracker-setup/SKILL.md" ]; then
  SRC="$HERE/tracker-setup"
else
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  echo "  Downloading the tracker skill..."
  curl -fsSL "$REPO_URL/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP" --strip-components=1
  SRC="$TMP/tracker-setup"
fi
[ -f "$SRC/SKILL.md" ] || { echo "Couldn't find the skill files. Please report this."; exit 1; }

mkdir -p "$(dirname "$SKILL_DEST")"
rm -rf "$SKILL_DEST"
cp -R "$SRC" "$SKILL_DEST"
ok "Installed the tracker skill to $SKILL_DEST"

if [ "$NEED_PATH_FIX" = 1 ]; then
  say "One more step — add Claude Code to your PATH, then open a new terminal:

  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc   # use ~/.zshrc on a Mac"
fi

say "All set. To create your tracker:

  mkdir ~/job-search && cd ~/job-search
  claude
  /tracker-setup
"
