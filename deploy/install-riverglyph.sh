#!/usr/bin/env bash
# Install / remove the riverglyph.enablesu.com LaunchAgents (auth proxy + tunnel)
# on THIS Mac, filling the plist/config templates with this machine's paths.
# Never touches ~/.cloudflared/config.yml (that belongs to the bridge-james tunnel).
#
#   bash deploy/install-riverglyph.sh            # install (or reinstall) + start
#   bash deploy/install-riverglyph.sh uninstall  # stop + remove (e.g. before moving Macs)
#   bash deploy/install-riverglyph.sh status
#
# Only ONE Mac may run the riverglyph tunnel at a time — uninstall on the old Mac
# before installing on the new one. See deploy/CLOUDFLARE.md.
set -euo pipefail

TUNNEL_ID="${RIVERGLYPH_TUNNEL_ID:-4c3ed387-005c-47e2-8d3a-7d25bbd0a131}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
LABELS=(com.enablesu.riverglyph-proxy com.enablesu.riverglyph-tunnel)
DOMAIN="gui/$(id -u)"

stop_agents() {
  for label in "${LABELS[@]}"; do
    launchctl bootout "$DOMAIN/$label" 2>/dev/null && echo "stopped $label" || true
  done
}

status() {
  for label in "${LABELS[@]}"; do
    if launchctl print "$DOMAIN/$label" >/dev/null 2>&1; then
      echo "$label: $(launchctl print "$DOMAIN/$label" | awk '/^\tstate =/{print $3; exit}')"
    else
      echo "$label: not installed"
    fi
  done
  pgrep -fl cloudflared || echo "(no cloudflared running)"
  lsof -nP -iTCP:8765 -sTCP:LISTEN >/dev/null 2>&1 \
    && echo "serve.py: listening on 8765" || echo "serve.py: NOT running (start: python serve.py)"
}

case "${1:-install}" in
  uninstall)
    stop_agents
    for label in "${LABELS[@]}"; do rm -f "$AGENTS/$label.plist"; done
    echo "removed LaunchAgents (left ~/.cloudflared/riverglyph.yml and the tunnel itself in place)"
    exit 0 ;;
  status) status; exit 0 ;;
  install) ;;
  *) echo "usage: $0 [install|uninstall|status]" >&2; exit 2 ;;
esac

# --- preflight -----------------------------------------------------------------
fail() { echo "ERROR: $*" >&2; exit 1; }
CLOUDFLARED="$(command -v cloudflared)" || fail "cloudflared not found (brew install cloudflared)"
[[ -x "$REPO/.venv/bin/python" ]] || fail "no $REPO/.venv (create it; see CLAUDE.md)"
[[ -s "$REPO/deploy/riverglyph.env" ]] || fail "missing deploy/riverglyph.env (copy it from the old Mac, or: bash deploy/gen-riverglyph-credentials.sh)"
CREDS="$HOME/.cloudflared/$TUNNEL_ID.json"
[[ -f "$CREDS" ]] || fail "missing $CREDS — copy the tunnel credentials from the old Mac (see deploy/CLOUDFLARE.md)"
if pgrep -f "cloudflared.*run riverglyph" >/dev/null; then
  pgrep -fl "cloudflared.*run riverglyph" | grep -q "$HOME/.cloudflared/riverglyph.yml" \
    || fail "another riverglyph cloudflared is already running here: $(pgrep -fl 'cloudflared.*run riverglyph')"
fi

# --- tunnel config (separate from config.yml) -----------------------------------
sed -e "s|__HOME__|$HOME|g" -e "s|<TUNNEL-UUID>|$TUNNEL_ID|g" \
  "$REPO/deploy/cloudflared-riverglyph.yml" > "$HOME/.cloudflared/riverglyph.yml"
"$CLOUDFLARED" tunnel --config "$HOME/.cloudflared/riverglyph.yml" ingress validate >/dev/null
echo "wrote ~/.cloudflared/riverglyph.yml"

# --- LaunchAgents ------------------------------------------------------------------
stop_agents
mkdir -p "$AGENTS" "$HOME/Library/Logs"
for label in "${LABELS[@]}"; do
  sed -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME|g" -e "s|__CLOUDFLARED__|$CLOUDFLARED|g" \
    "$REPO/deploy/$label.plist" > "$AGENTS/$label.plist"
  plutil -lint "$AGENTS/$label.plist" >/dev/null
  launchctl bootstrap "$DOMAIN" "$AGENTS/$label.plist"
  echo "started $label"
done

sleep 3
status
echo
echo "Logs: ~/Library/Logs/riverglyph-{proxy,tunnel}.log   Site: https://riverglyph.enablesu.com"
