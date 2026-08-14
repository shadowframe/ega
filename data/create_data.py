#!/usr/bin/env python3
"""Erzeugt die bereinigte Berufeliste aus den DKZ-Quelldateien.

Die Implementierung verwendet ausschließlich die Python-Standardbibliothek.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

GROUPS = {
    "1910",
    "2910",
    "2920",
    "2930",
    "2940",
    "2950",
    "3810",
    "3910",
    "3920",
    "4910",
    "7910",
}

XLSX_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def column_index(cell_reference: str) -> int:
    """Gibt den nullbasierten Spaltenindex einer Excel-Adresse zurück."""
    letters = re.match(r"[A-Z]+", cell_reference)
    if not letters:
        raise ValueError(f"Ungültige Excel-Zelladresse: {cell_reference}")
    index = 0
    for letter in letters.group(0):
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(text.text or "" for text in item.iter("{%s}t" % XLSX_NS["m"]))
        for item in root.findall("m:si", XLSX_NS)
    ]


def read_xlsx_rows(path: Path) -> list[dict[int, str]]:
    """Liest das Tabellenblatt mit den Berufsgattungszuordnungen."""
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = workbook.find("m:sheets", XLSX_NS)
        sheet_name = "Berufe_Berufsgattung KldB 2010"
        sheet = next(
            sheet
            for sheet in sheets
            if sheet.attrib.get("name") == sheet_name
        )
        rel_id = sheet.attrib["{%s}id" % "http://schemas.openxmlformats.org/officeDocument/2006/relationships"]
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel = next(
            rel
            for rel in rels
            if rel.attrib.get("Id") == rel_id
        )
        target = rel.attrib["Target"].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        worksheet = ET.fromstring(archive.read(target))

    rows: list[dict[int, str]] = []
    for row in worksheet.findall(".//m:sheetData/m:row", XLSX_NS):
        values: dict[int, str] = {}
        for cell in row.findall("m:c", XLSX_NS):
            value = cell.find("m:v", XLSX_NS)
            text = value.text if value is not None and value.text is not None else ""
            if cell.attrib.get("t") == "s" and text:
                text = strings[int(text)]
            elif cell.attrib.get("t") == "inlineStr":
                inline = cell.find("m:is", XLSX_NS)
                text = "".join(t.text or "" for t in inline.iter("{%s}t" % XLSX_NS["m"])) if inline is not None else ""
            values[column_index(cell.attrib["r"])] = text
        if values:
            rows.append(values)
    return rows


def parse_date(value: str) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%d.%m.%Y").date()


def is_current(entry: dict[str, str], reference_date: date) -> bool:
    """Ein leerer Ablauf ist offen; ein Datum vor dem Stichtag ist abgelaufen."""
    expires = parse_date(entry.get("gueltigBis", ""))
    return expires is None or expires >= reference_date


def build_data(xlsx_path: Path, xml_path: Path, reference_date: date) -> dict:
    rows = read_xlsx_rows(xlsx_path)
    if not rows:
        raise ValueError("Das XLSX-Arbeitsblatt enthält keine Daten.")

    headers = rows[0]
    header_to_index = {value.strip(): index for index, value in headers.items()}
    required = {
        "DKZ-ID Beruf",
        "Codenr. Beruf",
        "Bezeichnung n/k Beruf",
        "Zustand",
        "BKGR Beruf",
        "berufs-\nkund-\nlicher Typ",
        "Codenr. KldB 2010 Berufs-\ngattung",
        "Bezeichnung n/k KldB 2010 Berufsgattung",
        "Bezeichnung Statistik KldB 2010 Berufsgattung",
    }
    missing = required - set(header_to_index)
    if missing:
        raise ValueError(f"Fehlende XLSX-Spalten: {sorted(missing)}")

    # Die XLSX-Datei liefert die benötigten Gruppen und den berufskundlichen Typ.
    # Der XML-Schlüssel ist die Codenummer; dadurch bleiben die XML-Bezeichnungen
    # und Gültigkeitsdaten die führenden Werte der Ausgabeliste.
    xlsx_by_code: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        record = {
            name: row.get(index, "").strip()
            for name, index in header_to_index.items()
        }
        if (
            record.get("BKGR Beruf") in GROUPS
            and record.get("Zustand") == "E"
            and record.get("berufs-\nkund-\nlicher Typ", "").lower() == "t"
        ):
            xlsx_by_code[record["Codenr. Beruf"]] = record

    xml_root = ET.parse(xml_path).getroot()
    berufe = []
    for element in xml_root:
        if element.tag.rsplit("}", 1)[-1] != "beruf":
            continue
        entry = element.attrib
        xlsx_record = xlsx_by_code.get(entry.get("codenr", ""))
        if xlsx_record is None or not is_current(entry, reference_date):
            continue
        berufe.append(
            {
                "id": entry.get("id", ""),
                "codenr": entry.get("codenr", ""),
                "obercodenr": entry.get("obercodenr", ""),
                "bezeichnung": entry.get("bezeichnung", ""),
                "zustand": entry.get("zustand", ""),
                "berufskundlicheGruppe": entry.get("berufskundlicheGruppe", ""),
                "berufskundlicherTyp": "t",
                "berufskundlicheGattung": {
                    "codenr": xlsx_record.get("Codenr. KldB 2010 Berufs-\ngattung", ""),
                    "bezeichnung": xlsx_record.get("Bezeichnung n/k KldB 2010 Berufsgattung", ""),
                    "bezeichnungStatistik": xlsx_record.get("Bezeichnung Statistik KldB 2010 Berufsgattung", ""),
                },
                "gueltigVon": entry.get("gueltigVon", ""),
                "gueltigBis": entry.get("gueltigBis", ""),
            }
        )

    berufe.sort(key=lambda item: (item["codenr"], int(item["id"] or 0)))
    return {
        "beschreibung": "Bereinigte Berufeliste aus den DKZ-Daten",
        "stichtag": reference_date.isoformat(),
        "filter": {
            "berufskundlicheGruppen": sorted(GROUPS),
            "zustand": "E",
            "berufskundlicherTyp": "t",
            "abgelaufeneEintraege": "gueltigBis vor dem Stichtag ausschließen",
        },
        "anzahl": len(berufe),
        "berufe": berufe,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, default=Path(__file__).with_name("DKZ_Berufe_Zuordnung_Berufsgattung.xlsx"))
    parser.add_argument("--xml", type=Path, default=Path(__file__).with_name("DKZ_alle_Berufe_gueltig_ungueltig.xml"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("berufe_bereinigt.json"))
    parser.add_argument("--reference-date", type=date.fromisoformat, default=date.today(), help="Stichtag im Format JJJJ-MM-TT (Standard: heute)")
    args = parser.parse_args()

    data = build_data(args.xlsx, args.xml, args.reference_date)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{data['anzahl']} Berufe nach {args.output} geschrieben (Stichtag: {data['stichtag']}).")


if __name__ == "__main__":
    main()
