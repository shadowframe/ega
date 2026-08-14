# Datenaufbereitung der Berufeliste

Dieses Verzeichnis enthält die beiden unveränderten DKZ-Quelldateien sowie die daraus erzeugte, bereinigte Berufeliste.

## Dateien

- `DKZ_Berufe_Zuordnung_Berufsgattung.xlsx` – Zuordnung der Berufe zu den berufskundlichen Gruppen und Angabe des berufskundlichen Typs.
- `DKZ_alle_Berufe_gueltig_ungueltig.xml` – vollständige DKZ-Berufeliste einschließlich Zuständen und Gültigkeitszeiträumen.
- `create_data.py` – reproduzierbares Erzeugungsprogramm.
- `berufe_bereinigt.json` – erzeugtes Ergebnis.

Dotfiles werden nicht als Quelldateien verwendet.

## Quelle der Quelldateien

Die beiden DKZ-Dateien stammen aus dem Downloadportal der Bundesagentur für Arbeit, Bereich „Berufe“:

[DKZ-Downloadportal – Berufe](https://www.arbeitsagentur.de/institutionen/dkz-downloadportal#Berufe)

## Angewendete Filter

Ein Datensatz wird nur übernommen, wenn alle folgenden Bedingungen erfüllt sind:

1. Die berufskundliche Gruppe (`BKGR Beruf` bzw. `berufskundlicheGruppe`) ist eine der Gruppen `1910`, `2910`, `2920`, `2930`, `2940`, `2950`, `3810`, `3910`, `3920`, `4910` oder `7910`.
2. Der Zustand ist `E`. In der XLSX ist dies die Auswahl der gewünschten Endpunkte.
3. Der berufskundliche Typ ist `t` (Tätigkeiten). Der Wert kommt aus der XLSX; die XML-Datei enthält dieses Merkmal nicht als eigenes Attribut.
4. `gueltigBis` ist leer oder liegt am Stichtag bzw. danach. Einträge mit einem Ablaufdatum vor dem Stichtag werden ausgeschlossen.

Die XML-Daten sind für Bezeichnung, ID, Codenummer und Gültigkeitsdaten führend. Die XLSX wird über `Codenr. Beruf` mit der XML-Datei verknüpft.

## Einrichtung mit `.venv`

Das Programm benötigt keine externen Python-Pakete. Trotzdem wird eine virtuelle Umgebung verwendet, damit die Ausführung vom System-Python getrennt bleibt.

Mit `uv`:

```bash
cd ~/Projekte/ega/data
uv venv .venv
```

Falls `.venv` bereits existiert und neu erstellt werden soll:

```bash
uv venv --clear .venv
```

Alternativ – sofern das Betriebssystemmodul für virtuelle Umgebungen installiert ist:

```bash
python3 -m venv .venv
```

## Liste erzeugen

Direkt aus dem Verzeichnis:

```bash
.venv/bin/python create_data.py
```

Oder nach Aktivierung der Umgebung:

```bash
source .venv/bin/activate
python create_data.py
```

Das Programm schreibt standardmäßig `berufe_bereinigt.json`. Der Stichtag ist standardmäßig das aktuelle Datum. Für reproduzierbare Ergebnisse kann er ausdrücklich gesetzt werden:

```bash
.venv/bin/python create_data.py --reference-date 2026-08-14
```

Die Pfade und der Name der Ausgabedatei können bei Bedarf überschrieben werden:

```bash
.venv/bin/python create_data.py \
  --xlsx DKZ_Berufe_Zuordnung_Berufsgattung.xlsx \
  --xml DKZ_alle_Berufe_gueltig_ungueltig.xml \
  --output berufe_bereinigt.json
```

## Aufbau der JSON-Datei

Die JSON-Datei enthält neben der Liste `berufe` die verwendeten Filter, den Stichtag und die Anzahl der Datensätze. Jeder Beruf enthält unter anderem:

- `id`
- `codenr`
- `obercodenr`
- `bezeichnung`
- `zustand`
- `berufskundlicheGruppe`
- `berufskundlicherTyp`
- `berufskundlicheGattung` mit KldB-Codenummer sowie den beiden Bezeichnungen aus der XLSX (`bezeichnung` und `bezeichnungStatistik`)
- `gueltigVon`
- `gueltigBis`

Die Ausgabe wird nach Codenummer und ID sortiert. Die Quelldateien werden nicht verändert.

## Entgeltatlas-Crawler

`crawler.py` erweitert `berufe_bereinigt.json` um Daten aus dem Entgeltatlas der Bundesagentur für Arbeit und schreibt `ega.json`.

Verwendet wird die aktuelle Entgeltatlas-API:

```text
https://rest.arbeitsagentur.de/infosysbub/entgeltatlas/pc/v1/entgelte/{kldb}
```

Der Crawler fragt immer für Deutschland (`r=1`) und die Branche Gesamt (`b=1`) ab. Für jeden Beruf werden folgende Werte gespeichert:

- Median (`median`)
- unteres Quartil (`unteresQuartil`)
- oberes Quartil (`oberesQuartil`)
- Besetzung (`besetzung`, sofern von der API geliefert)

Die Werte werden vollständig für jede Kombination aus `geschlecht` (`alle`, `männlich`, `weiblich`) und `altergruppe` (`alle`, `<25`, `25-54`, `>54`) abgelegt. Beispielpfad für den Median von Männern zwischen 25 und 54 Jahren: `beruf.ega.werte.geschlecht.männlich.25-54.median`. Der Crawler verwendet den fünfstelligen KldB-Schlüssel aus `berufskundlicheGattung.codenr`. Die API liefert dafür ohne den Parameter `l` alle vier Altersgruppen und drei Geschlechter der zugehörigen Leistungsstufe.

### API-Key

Der API-Key wird nicht in den Quellcode geschrieben. Er wird zur Laufzeit über eine Umgebungsvariable übergeben:

```bash
export ENTGELTATLAS_API_KEY='...'
```

Der aktuell von der Entgeltatlas-Webanwendung verwendete öffentliche Client-Key kann aus der geladenen Webseite beziehungsweise deren Konfiguration entnommen werden. Alternativ akzeptiert das Programm `--api-key`.

### Crawler ausführen

```bash
cd ~/Projekte/ega/data
source .venv/bin/activate
export ENTGELTATLAS_API_KEY='...'
python crawler.py
```

Die Ausgabe wird nach `berufe_bereinigt.json`-Daten plus Entgeltwerten in `ega.json` geschrieben. Für die Netzwerkbelastung werden eindeutige KldB-Schlüssel nur einmal abgefragt und standardmäßig acht parallele Anfragen verwendet. Optionen:

```bash
python crawler.py --workers 4 --timeout 60 --retries 5
python crawler.py --api-key '...' --output ega.json
```

`ega.json` enthält zusätzlich:

- `summe.kldb3stellig` – Anzahl der Berufe mit dreistelligem KldB-Schlüssel
- `summe.kldb5stellig` – Anzahl der Berufe mit fünfstelligem KldB-Schlüssel
- `statistik.eindeutigeKldb3Stellig` und `statistik.eindeutigeKldb5Stellig` – Anzahl der tatsächlich abgefragten eindeutigen Schlüssel

Die API kann einzelne Werte als negative Statuscodes liefern, zum Beispiel für zu wenige oder nicht vorhandene Daten. Diese Werte werden unverändert im jeweiligen Entgeltfeld gespeichert.

Die Terminaloberfläche ist im Projektstamm dokumentiert: [README.md](../README.md).