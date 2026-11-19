# Kilometerstand automatisch uit TeslaMate

Elke dag zet een script op je TeslaMate-server de kilometerstand in
`teslamate/km.json` en pusht dat naar GitHub. De TeslaTrack-app leest dat
bestand bij het openen in en voegt nieuwe standen toe aan *Kilometerstand*.
Je kunt het ook met de hand doen met **🔄 Ophalen uit TeslaMate**.

```
Tesla ──► TeslaMate (Postgres) ──► export-km.sh (cron) ──► km.json op GitHub ──► TeslaTrack-app
```

Per dag waarop je gereden hebt komt er één regel in de app, met de stand aan
het eind van die dag. Bestaat er op die datum al een regel met dezelfde stand
(bijvoorbeeld een die je zelf hebt ingevoerd), dan voegt de app niets toe.

## Eenmalig instellen op de server

1. **Clone deze repo** op de machine waar TeslaMate draait:
   ```bash
   git clone git@github.com:jannr14-ship-it/Tesla-tracking.git ~/Tesla-tracking
   ```
   Die machine moet kunnen pushen. Gebruik een *deploy key* met schrijfrechten
   (GitHub → repo → Settings → Deploy keys) of een fine-grained token dat
   alleen voor deze repo geldt.

2. **Test het script** zonder te pushen:
   ```bash
   cd ~/Tesla-tracking
   GIT_PUSH=0 TESLAMATE_DIR=~/teslamate teslamate/export-km.sh
   cat teslamate/km.json
   ```
   `TESLAMATE_DIR` is de map met de `docker-compose.yml` van TeslaMate. Wijkt
   je setup af, zet de instellingen dan in `teslamate/export-km.env`
   (staat in `.gitignore`), bijvoorbeeld:
   ```bash
   TESLAMATE_DIR=/opt/teslamate
   DB_SERVICE=database
   CAR_ID=1
   # of zonder Docker:
   # PSQL="psql -h localhost -U teslamate teslamate"
   ```

3. **Plan het dagelijks in** met `crontab -e`:
   ```
   55 23 * * *  $HOME/Tesla-tracking/teslamate/export-km.sh >> $HOME/teslatrack-km.log 2>&1
   ```
   Het script commit alleen als er echt een nieuwe stand is.

## In de app

Ga naar *Instellingen → TeslaMate koppeling*:

- **Adres van km.json**: laat dit leeg als de app via GitHub Pages uit deze
  repo draait, dan gebruikt de app `teslamate/km.json`. Draait de app ergens
  anders, vul dan de volledige URL in, bijvoorbeeld
  `https://jannr14-ship-it.github.io/Tesla-tracking/teslamate/km.json`.
- **Automatisch ophalen bij openen**: staat standaard aan.

Let op: `km.json` is openbaar als de repo of de GitHub Pages-site openbaar
is. Het bestand bevat alleen datums en kilometerstanden, geen locaties.
