# Datenpipeline

Dieses Verzeichnis enthält die Quelldaten, die Aufbereitung und den Crawler für die Entgeltwerte.

Wenn du egaterm nur starten möchtest, brauchst du diese Datei nicht. Die wichtigsten Befehle stehen in der [Root-README](../README.md).

## Was die Pipeline macht

`main.py` führt die Schritte in dieser Reihenfolge aus:

1. `catch_source.py` lädt die offiziellen DKZ-Dateien.
2. `create_data.py` filtert und verbindet die Berufsdaten.
3. `entgeltatlas_client.py` holt den öffentlichen Client-Key der Entgeltatlas-Webseite.
4. `crawler.py` fragt die Entgeltwerte ab und schreibt `ega.json`.

Die Pipeline stoppt, sobald ein Schritt fehlschlägt. Dadurch wird nicht stillschweigend mit unvollständigen Daten weitergearbeitet.

## Einmalig einrichten

Die Skripte verwenden nur die Python-Standardbibliothek. Eine virtuelle Umgebung hält die Ausführung trotzdem sauber vom System-Python getrennt.

Mit Python:

```bash
cd data
python3 -m venv .venv
```

Alternativ mit `uv`:

```bash
cd data
uv venv .venv
```

Falls die virtuelle Umgebung schon existiert, muss dieser Schritt nicht wiederholt werden.

## Die komplette Pipeline starten

Aus dem Projektverzeichnis:

```bash
data/.venv/bin/python data/main.py --plain
```

Oder direkt aus `data/`:

```bash
cd data
.venv/bin/python main.py --plain
```

Optional kann ein fester Stichtag für die DKZ-Bereinigung angegeben werden:

```bash
data/.venv/bin/python data/main.py \
  --reference-date 2026-08-14 \
  --plain
```

Verfügbare Netzwerkoptionen:

```text
--timeout SECONDS   Zeitlimit pro Anfrage
--retries COUNT     Wiederholungen bei Netzwerkfehlern
--workers COUNT     parallele Entgeltatlas-Anfragen
```

Die Pipeline schreibt beziehungsweise aktualisiert:

- `data/DKZ_alle_Berufe_gueltig_ungueltig.xml`
- `data/DKZ_Berufe_Zuordnung_Berufsgattung.xlsx`
- `data/berufe_bereinigt.json`
- `data/ega.json`

Die Quelldateien werden vor dem Ersetzen geprüft. Downloads landen zunächst in temporären `.part`-Dateien.

## Den API-Key musst du nicht kopieren

Die Entgeltatlas-Webanwendung stellt ihren öffentlichen Client-Key in ihrer HTML-Konfiguration bereit. Der Entgeltatlas-Client von egaterm lädt die Webseite und liest dort `infosysbubLibConfig.clientId` aus.

Das bedeutet:

- keine Browser-Session nötig
- keine Anmeldung nötig
- keine Cookies nötig
- keine manuelle Key-Eingabe nötig
- kein Key wird gespeichert oder ausgegeben

Der Key wird nur im Speicher gehalten und für die gestarteten Unterprozesse bereitgestellt.

Für Tests oder einen alternativen Wert kann die automatische Ermittlung überschrieben werden:

```bash
export ENTGELTATLAS_API_KEY='...'
data/.venv/bin/python data/crawler.py
```

## Einzelne Schritte

### Berufeliste neu erzeugen

```bash
cd data
.venv/bin/python create_data.py
```

Die Eingabedateien sind:

- `DKZ_alle_Berufe_gueltig_ungueltig.xml`
- `DKZ_Berufe_Zuordnung_Berufsgattung.xlsx`

Für reproduzierbare Ergebnisse kann der Stichtag gesetzt werden:

```bash
.venv/bin/python create_data.py --reference-date 2026-08-14
```

### Entgeltwerte neu abrufen

```bash
cd data
.venv/bin/python crawler.py
```

Der Crawler verwendet `berufe_bereinigt.json` und schreibt standardmäßig `ega.json`.

Eindeutige KldB-Schlüssel werden nur einmal abgefragt. Standardmäßig laufen acht Anfragen parallel:

```bash
.venv/bin/python crawler.py --workers 4 --timeout 60 --retries 5
```

### TUI starten

```bash
data/.venv/bin/python egaterm.py
```

## Welche Daten übernommen werden

`create_data.py` übernimmt nur Datensätze, die alle Bedingungen erfüllen:

- berufskundliche Gruppe: `1910`, `2910`, `2920`, `2930`, `2940`, `2950`, `3810`, `3910`, `3920`, `4910` oder `7910`
- Zustand: `E` für Endpunkt
- berufskundlicher Typ: `t` für Tätigkeit
- `gueltigBis` ist leer oder liegt am Stichtag beziehungsweise danach

Die XML-Datei ist führend für Bezeichnung, ID, Codenummer und Gültigkeitsdaten. Die XLSX-Datei liefert die Zuordnung zur berufskundlichen Gruppe und zum berufskundlichen Typ.

## Entgeltatlas-Abfragen

Der Crawler verwendet diesen offiziellen API-Endpunkt:

```text
https://rest.arbeitsagentur.de/infosysbub/entgeltatlas/pc/v1/entgelte/{kldb}
```

Alle Abfragen verwenden:

- Region Deutschland (`r=1`)
- Branche Gesamt (`b=1`)

Für jeden Beruf werden Median, unteres Quartil, oberes Quartil und, sofern vorhanden, die Besetzung gespeichert. Die Werte werden nach Geschlecht und Altersgruppe abgelegt:

- Geschlecht: `alle`, `männlich`, `weiblich`
- Alter: `alle`, `<25`, `25-54`, `>54`

Beispiel für den Median von Männern zwischen 25 und 54 Jahren:

```text
beruf.ega.werte.geschlecht.männlich.25-54.median
```

Die API kann für einzelne Kombinationen negative Statuswerte liefern, wenn zu wenige oder keine Daten vorhanden sind. Diese Werte werden unverändert gespeichert.

## Quelldateien

Die DKZ-Dateien stammen aus dem offiziellen [DKZ-Downloadportal der Bundesagentur für Arbeit](https://www.arbeitsagentur.de/institutionen/dkz-downloadportal#Berufe).

Die Pipeline verwendet direkt:

- XML: `https://rest.arbeitsagentur.de/infosysbub/download-portal-rest/ct/dkz-downloads/DKZ_alle_Berufe_gueltig_ungueltig.xml`
- XLSX: `https://rest.arbeitsagentur.de/infosysbub/download-portal-rest/ct/dkz-downloads/DKZ_Berufe_Zuordnung_Berufsgattung.xlsx`

Dotfiles werden nicht als Datenquellen verarbeitet.

## Aufbau von `ega.json`

Die Datei enthält neben `berufe` auch Informationen über Quelle, Filter und Statistik. Jeder Beruf enthält unter anderem:

- `id`
- `codenr`
- `obercodenr`
- `bezeichnung`
- `zustand`
- `berufskundlicheGruppe`
- `berufskundlicherTyp`
- `berufskundlicheGattung`
- `gueltigVon`
- `gueltigBis`
- `ega`

Unter `ega` stehen der verwendete KldB-Schlüssel und die Entgeltwerte.

## Wenn etwas nicht funktioniert

- **`venv` kann nicht erstellt werden:** Installiere unter Debian oder Ubuntu `python3-venv`, bei mehreren Python-Versionen eventuell das passende versionsspezifische Paket.
- **Key-Fehler:** Prüfe zuerst, ob die Entgeltatlas-Webseite erreichbar ist. Alternativ kann testweise `ENTGELTATLAS_API_KEY` gesetzt werden.
- **API-Fehler:** Erhöhe `--timeout` oder `--retries` und reduziere bei Bedarf `--workers`.
- **Keine Daten für einen Beruf:** Die API kann bei kleinen Fallzahlen negative Statuswerte zurückgeben. Das ist nicht automatisch ein Fehler im Crawler.
- **TUI startet nicht:** Prüfe, ob `data/ega.json` vorhanden ist und ob du die virtuelle Umgebung mit dem Python-Aufruf aus dem Projekt verwendest.
