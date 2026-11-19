#!/usr/bin/env bash
# TeslaTrack — dagelijkse export van de kilometerstand uit TeslaMate.
#
# Leest per dag de laatste kilometerstand uit de TeslaMate-database (tabel
# `drives`), schrijft die naar teslamate/km.json in deze repo en pusht de
# wijziging naar GitHub. De TeslaTrack-app leest dat bestand bij het openen in.
#
# Draai dit op de server waar TeslaMate draait, bijv. elke avond via cron:
#   55 23 * * *  /pad/naar/Tesla-tracking/teslamate/export-km.sh >> /var/log/teslatrack-km.log 2>&1
#
# Instellingen (omgevingsvariabelen, of zet ze in teslamate/export-km.env):
#   TESLAMATE_DIR  map met de docker-compose.yml van TeslaMate   (standaard: ~/teslamate)
#   DB_SERVICE     naam van de database-service in die compose   (standaard: database)
#   DB_USER        databasegebruiker                             (standaard: teslamate)
#   DB_NAME        databasenaam                                  (standaard: teslamate)
#   PSQL           eigen psql-commando; overschrijft de vier hierboven,
#                  bijv. "psql -h localhost -U teslamate teslamate"
#   CAR_ID         TeslaMate car_id                              (standaard: 1)
#   TZ_NAME        tijdzone voor de datum                        (standaard: Europe/Amsterdam)
#   GIT_PUSH       1 = commit + push, 0 = alleen bestand schrijven (standaard: 1)
#   GIT_BRANCH     branch om naar te pushen                       (standaard: huidige branch)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
[ -f "$SCRIPT_DIR/export-km.env" ] && . "$SCRIPT_DIR/export-km.env"

TESLAMATE_DIR="${TESLAMATE_DIR:-$HOME/teslamate}"
DB_SERVICE="${DB_SERVICE:-database}"
DB_USER="${DB_USER:-teslamate}"
DB_NAME="${DB_NAME:-teslamate}"
PSQL="${PSQL:-docker compose --project-directory $TESLAMATE_DIR exec -T $DB_SERVICE psql -U $DB_USER -d $DB_NAME}"
CAR_ID="${CAR_ID:-1}"
TZ_NAME="${TZ_NAME:-Europe/Amsterdam}"
GIT_PUSH="${GIT_PUSH:-1}"
OUT="$SCRIPT_DIR/km.json"

case "$CAR_ID" in ''|*[!0-9]*) echo "CAR_ID moet een getal zijn" >&2; exit 1;; esac

log() { echo "[$(date '+%F %T')] $*"; }

if [ "$GIT_PUSH" = "1" ]; then
  git -C "$REPO_DIR" pull --rebase --quiet
fi

# TeslaMate slaat tijden op als UTC (timestamp zonder tijdzone).
JSON="$($PSQL -X -q -A -t -v ON_ERROR_STOP=1 -v car_id="$CAR_ID" -v tz="$TZ_NAME" <<'SQL'
WITH per_dag AS (
  SELECT (end_date AT TIME ZONE 'UTC' AT TIME ZONE :'tz')::date AS dag,
         max(end_km) AS stand
  FROM drives
  WHERE car_id = :car_id AND end_km IS NOT NULL AND end_date IS NOT NULL
  GROUP BY 1
)
SELECT json_build_object(
  'bron', 'TeslaMate',
  'bijgewerkt', to_char(now() AT TIME ZONE :'tz', 'YYYY-MM-DD"T"HH24:MI:SS'),
  'standen', coalesce(
    (SELECT json_agg(json_build_object('datum', to_char(dag, 'YYYY-MM-DD'),
                                       'stand', round(stand::numeric)::int)
                     ORDER BY dag)
     FROM per_dag),
    '[]'::json)
);
SQL
)"

case "$JSON" in
  '{'*) ;;
  *) echo "Onverwachte uitvoer van psql: $JSON" >&2; exit 1;;
esac

# Alleen schrijven als de standen veranderd zijn (het tijdstempel telt niet mee),
# zodat er geen lege dagelijkse commits ontstaan.
strip_ts() { sed -E 's/"bijgewerkt" *: *"[^"]*"//'; }
if [ -f "$OUT" ] && [ "$(strip_ts < "$OUT")" = "$(printf '%s\n' "$JSON" | strip_ts)" ]; then
  log "Geen nieuwe kilometerstand."
  exit 0
fi
printf '%s\n' "$JSON" > "$OUT"
log "km.json bijgewerkt."

if [ "$GIT_PUSH" = "1" ]; then
  git -C "$REPO_DIR" add "$OUT"
  git -C "$REPO_DIR" commit --quiet -m "Kilometerstand bijgewerkt uit TeslaMate ($(date +%F))"
  if [ -n "${GIT_BRANCH:-}" ]; then
    git -C "$REPO_DIR" push --quiet origin "HEAD:$GIT_BRANCH"
  else
    git -C "$REPO_DIR" push --quiet
  fi
  log "Gepusht naar GitHub."
fi
