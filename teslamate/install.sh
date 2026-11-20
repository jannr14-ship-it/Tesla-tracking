#!/usr/bin/env bash
# Eenmalige installatie op de TeslaMate-server:
#   1. test of de kilometerstand uit TeslaMate gelezen kan worden
#   2. test of deze repo naar GitHub kan pushen
#   3. zet een dagelijkse cron-taak (23:55) klaar
# Gebruik:  teslamate/install.sh            (of TESLAMATE_DIR=/pad teslamate/install.sh)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
EXPORT="$SCRIPT_DIR/export-km.sh"
chmod +x "$EXPORT"

# Instellingen bewaren zodat cron ze ook gebruikt.
if [ -n "${TESLAMATE_DIR:-}" ] && [ ! -f "$SCRIPT_DIR/export-km.env" ]; then
  echo "TESLAMATE_DIR=$TESLAMATE_DIR" > "$SCRIPT_DIR/export-km.env"
fi

echo "1/3  Kilometerstand lezen uit TeslaMate..."
GIT_PUSH=0 "$EXPORT"
N=$(grep -o '"datum"' "$SCRIPT_DIR/km.json" | wc -l)
echo "     OK: $N dagen gevonden, laatste: $(grep -o '"datum" *: *"[^"]*" *, *"stand" *: *[0-9]*' "$SCRIPT_DIR/km.json" | tail -1)"
git -C "$REPO_DIR" checkout -- "$SCRIPT_DIR/km.json" 2>/dev/null || rm -f "$SCRIPT_DIR/km.json"

echo "2/3  Pushrechten naar GitHub controleren..."
if ! git -C "$REPO_DIR" push --dry-run --quiet 2>/dev/null; then
  echo "     Deze server kan nog niet naar GitHub pushen. Zie teslamate/README.md, stap 1." >&2
  exit 1
fi
echo "     OK"

echo "3/3  Dagelijkse taak instellen..."
LINE="55 23 * * * $EXPORT >> $HOME/teslatrack-km.log 2>&1"
( crontab -l 2>/dev/null | grep -vF "$EXPORT" || true; echo "$LINE" ) | crontab -
echo "     OK: $LINE"

echo "Eerste export nu uitvoeren..."
"$EXPORT"
echo "Klaar. De app haalt de kilometerstand op zodra je hem opent."
