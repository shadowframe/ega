# EGA Terminal-Anwendung

Dieses Projekt stellt eine terminalbasierte Oberfläche für Berufsdaten und Entgeltinformationen des Entgeltatlas der Bundesagentur für Arbeit bereit.

## Projekt beziehen

Das Repository kann in ein frei wählbares Arbeitsverzeichnis geklont werden:

```bash
git clone https://github.com/shadowframe/ega.git
cd ega
```

Alle folgenden Befehle werden aus dem Projektverzeichnis ausgeführt.

## Terminal-Anwendung `egaterm.py`

`egaterm.py` lädt `data/ega.json` und bietet eine interaktive TUI mit:

- Autosuggest-Suche nach Berufsbezeichnungen
- Auswahl von Berufen mit vorhandenen Entgeltdaten
- Geschlechtsfilter: `alle`, `männlich`, `weiblich`
- Altersgruppenfilter: `alle`, `<25`, `25-54`, `>54`
- Anzeige von Median, unterem Quartil und oberem Quartil
- grafischer Darstellung der Abstände zwischen Q25, Median und Q75
- mehrzeiligem ASCII-Schriftlogo `egaTERM` im Farbschema der Anwendung
Die Visualisierung stellt den Median als Marker zwischen dem unteren und oberen Quartil dar. Dadurch ist direkt erkennbar, ob der Median näher am unteren oder am oberen Quartil liegt. Die beiden Abstände werden zusätzlich als Eurobeträge angezeigt.

## Screenshots

Die Aufnahmen stammen aus der laufenden TUI und zeigen die wichtigsten Ansichten.

### Startansicht mit Autosuggest

![EGA Terminal – Startansicht mit Autosuggest](docs/screenshots/egaterm-default.png)

### Ausgewählter Beruf mit Entgeltkarte

![EGA Terminal – ausgewählter Beruf mit Median und Quartilen](docs/screenshots/egaterm-selected.png)

### Geschlechts- und Altersfilter

![EGA Terminal – Filteransicht männlich und unter 25](docs/screenshots/egaterm-filtered.png)

### Einrichtung und Start

Die virtuelle Umgebung wird bei einer frischen Projektkopie nicht mitgeliefert. Sie wird einmalig selbst im Verzeichnis `data/.venv` erstellt. Die TUI verwendet ausschließlich die Python-Standardbibliothek; zusätzliche Pakete müssen nicht installiert werden.

Voraussetzung ist Python 3.10 oder neuer. Unter Debian/Ubuntu muss gegebenenfalls zuerst das Modul für virtuelle Umgebungen installiert werden:

```bash
sudo apt install python3-venv
```

Falls `python3 -m venv` danach weiterhin mit einer fehlenden `ensurepip`-Komponente abbricht, installiere das versionsspezifische Paket, passend zur installierten Python-Version, zum Beispiel:

```bash
sudo apt install python3.14-venv
```

Danach im Projektverzeichnis die virtuelle Umgebung erstellen und aktivieren:

```bash
python3 -m venv data/.venv
source data/.venv/bin/activate
```

Die TUI kann nun gestartet werden:

```bash
python egaterm.py
```

Alternativ kann die Umgebung auch ohne Aktivierung direkt verwendet werden:

```bash
data/.venv/bin/python egaterm.py
```

Wenn die Umgebung bereits existiert, muss der Erstellungsschritt nicht wiederholt werden. Zum Verlassen einer aktivierten Umgebung:

```bash
deactivate
```

Bedienung:

- Text eingeben: Autosuggest nach Berufsbezeichnung filtern
- `Ctrl+U`: Suchfeld leeren
- `1`: Geschlecht `alle`
- `2`: Geschlecht `männlich`
- `3`: Geschlecht `weiblich`
- `4`: Altersgruppe `alle`
- `5`: Altersgruppe `<25`
- `6`: Altersgruppe `25-54`
- `7`: Altersgruppe `>54`
- `0`: Anwendung jederzeit beenden
- `q`: normales Suchzeichen, keine Beenden-Funktion
- `↑` / `↓`: sichtbaren Vorschlag auswählen
- `Enter`: Datensatz auswählen

Die TUI benötigt keine zusätzlichen Python-Bibliotheken. Sie verwendet ausschließlich die Python-Standardbibliothek, insbesondere `curses`.

Self-Test:

```bash
data/.venv/bin/python egaterm.py --self-test
```

## Verzeichnis `data/`

Die Datenaufbereitung und die Entgeltatlas-Abfragen sind im Verzeichnis `data/` gekapselt. Die ausführliche Dokumentation befindet sich hier:

[`data/README.md`](data/README.md)

Dort werden Quelldateien, Filterregeln, JSON-Strukturen, `.venv`-Einrichtung und Crawler ausführlich beschrieben. Die TUI selbst ist in dieser Root-README dokumentiert.

### Dateien und Skripte

- `data/DKZ_Berufe_Zuordnung_Berufsgattung.xlsx` – Zuordnung von Berufen zu berufskundlichen Gruppen und KldB-Berufsgattungen.
- `data/DKZ_alle_Berufe_gueltig_ungueltig.xml` – vollständige DKZ-Berufeliste mit Zuständen und Gültigkeitsdaten.
- `data/create_data.py` – erzeugt aus XLSX und XML die bereinigte Berufeliste.
- `data/catch_source.py` – lädt die offiziellen DKZ-Quelldateien.
- `data/main.py` – startet die vollständige Datenpipeline als Batchkette.
- `data/berufe_bereinigt.json` – Ergebnis der DKZ-Datenaufbereitung.
- `data/crawler.py` – ruft Entgeltwerte des Entgeltatlas für die KldB-Schlüssel ab.
- `data/entgeltatlas_client.py` – liest den öffentlichen Client-Key aus der aktuellen Entgeltatlas-Webkonfiguration.
- `data/ega.json` – Berufeliste mit ergänzten Entgeltatlasdaten.
- `data/.venv/` – virtuelle Python-Umgebung für die lokalen Skripte.

### Datenpipeline

```text
DKZ XLSX + DKZ XML
        │
        ▼
create_data.py
        │
        ▼
berufe_bereinigt.json
        │
        ▼
crawler.py + Entgeltatlas-API
        │
        ▼
ega.json
        │
        ▼
egaterm.py
```

### Daten neu erzeugen

Bereinigte Berufeliste erstellen:

```bash
cd data
.venv/bin/python create_data.py
```

Entgeltatlasdaten abrufen. Der öffentliche Client-Key wird automatisch aus der aktuellen Entgeltatlas-Webseite gelesen. Eine manuelle Eingabe ist nicht erforderlich:

```bash
cd data
.venv/bin/python crawler.py
```

Auch die vollständige Batchkette (`data/main.py`) holt den Key automatisch, bevor
die erste Stufe startet. Der Key wird nur im Speicher beziehungsweise in der
Umgebung der gestarteten Unterprozesse verwendet und niemals ausgegeben oder in
einer Datei gespeichert.

Für reproduzierbare Tests oder einen abweichenden Client-Key kann die automatische
Ermittlung optional durch die Umgebungsvariable überschrieben werden:

```bash
export ENTGELTATLAS_API_KEY='...'
.venv/bin/python crawler.py
```

Der frühere Parameter `--api-key` wird bewusst nicht mehr angeboten, damit der
Key nicht in Shell-History oder Prozesslisten landet.

Danach kann die TUI erneut gestartet werden:

```bash
data/.venv/bin/python egaterm.py
```

Die Quelldateien werden von den Skripten nicht verändert. Dotfiles im Datenverzeichnis werden nicht als Datenquellen verarbeitet.
