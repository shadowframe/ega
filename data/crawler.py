#!/usr/bin/env python3
"""Crawlt Entgeltwerte aus dem Entgeltatlas der Bundesagentur für Arbeit.

Die API liefert für einen fünfstelligen KldB-Schlüssel ohne den Parameter
``l`` alle Geschlechts- und Altersgruppenwerte der zugehörigen Leistungsstufe.
Der API-Schlüssel wird aus der Umgebungsvariable ENTGELTATLAS_API_KEY gelesen.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://rest.arbeitsagentur.de/infosysbub/entgeltatlas/pc/v1/entgelte"
DEFAULT_INPUT = Path(__file__).with_name("berufe_bereinigt.json")
DEFAULT_OUTPUT = Path(__file__).with_name("ega.json")

GENDER_NAMES = {1: "alle", 2: "männlich", 3: "weiblich"}
AGE_NAMES = {1: "alle", 2: "<25", 3: "25-54", 4: ">54"}


def numeric_kldb(value: str) -> str:
    """Normalisiert z. B. ``B 11101`` zu ``11101``."""
    result = re.sub(r"\D", "", value or "")
    if len(result) not in (3, 5):
        raise ValueError(f"Keine drei- oder fünfstellige KldB gefunden: {value!r}")
    return result


def fetch_json(kldb: str, api_key: str, timeout: float, retries: int) -> list[dict]:
    query = urlencode({"r": 1, "b": 1})  # Deutschland, Branche Gesamt
    request = Request(
        f"{API_URL}/{kldb}?{query}",
        headers={
            "Accept": "application/json",
            "X-API-Key": api_key,
            "User-Agent": "ega-entgeltatlas-crawler/1.0",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, list):
                raise ValueError(f"Unerwartete API-Antwort für KldB {kldb}: keine Liste")
            return payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"API-Abfrage für KldB {kldb} fehlgeschlagen: {last_error}") from last_error


def metric(record: dict) -> dict:
    """Reduziert einen API-Datensatz auf die verlangten Entgeltwerte."""
    return {
        "median": record.get("entgelt"),
        "unteresQuartil": record.get("entgeltQ25"),
        "oberesQuartil": record.get("entgeltQ75"),
        "besetzung": record.get("besetzung"),
    }


def organize_metrics(records: list[dict], kldb: str) -> dict:
    """Ordnet alle 3 x 4 Geschlechts-/Alterskombinationen an."""
    matrix: dict[str, dict[str, dict]] = {
        gender: {} for gender in GENDER_NAMES.values()
    }
    for record in records:
        if str(record.get("kldb", "")) != kldb:
            continue
        gender_id = (record.get("gender") or {}).get("id")
        age_id = (record.get("ageCategory") or {}).get("id")
        if gender_id in GENDER_NAMES and age_id in AGE_NAMES:
            matrix[GENDER_NAMES[gender_id]][AGE_NAMES[age_id]] = metric(record)

    missing = [
        f"{gender}/{age}"
        for gender in GENDER_NAMES.values()
        for age in AGE_NAMES.values()
        if age not in matrix[gender]
    ]
    if missing:
        raise ValueError(
            f"Unvollständige API-Antwort für KldB {kldb}; "
            f"fehlende Kombinationen={missing}"
        )
    return {"geschlecht": matrix}


def load_source(path: Path) -> tuple[dict, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("berufe"), list):
        raise ValueError(f"Ungültige Quelldatei: {path}")
    return data, data["berufe"]


def crawl(source: dict, berufe: list[dict], api_key: str, timeout: float, retries: int, workers: int) -> dict:
    kldb_by_code: dict[str, str] = {}
    for beruf in berufe:
        kldb = numeric_kldb((beruf.get("berufskundlicheGattung") or {}).get("codenr", ""))
        kldb_by_code.setdefault(kldb, kldb)

    results: dict[str, list[dict]] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(fetch_json, kldb, api_key, timeout, retries): kldb
            for kldb in sorted(kldb_by_code)
        }
        for number, future in enumerate(as_completed(futures), start=1):
            kldb = futures[future]
            try:
                results[kldb] = future.result()
            except Exception as error:  # noqa: BLE001 - Fehler wird gesammelt und am Ende ausgegeben
                errors.append(str(error))
            print(f"API-Fortschritt: {number}/{len(futures)}", file=sys.stderr)
    if errors:
        raise RuntimeError("; ".join(errors[:5]) + (" …" if len(errors) > 5 else ""))

    output_berufe = []
    for beruf in berufe:
        kldb = numeric_kldb((beruf.get("berufskundlicheGattung") or {}).get("codenr", ""))
        enriched = dict(beruf)
        enriched["ega"] = {
            "kldb": kldb,
            "werte": organize_metrics(results[kldb], kldb),
        }
        output_berufe.append(enriched)

    counts = {"3": 0, "5": 0}
    unique_counts = {"3": 0, "5": 0}
    for beruf in berufe:
        kldb = numeric_kldb((beruf.get("berufskundlicheGattung") or {}).get("codenr", ""))
        counts[str(len(kldb))] += 1
    for kldb in results:
        unique_counts[str(len(kldb))] += 1

    return {
        "beschreibung": "Berufeliste mit Entgeltwerten aus dem Entgeltatlas",
        "quelle": {
            "berufeliste": source.get("beschreibung", "berufe_bereinigt.json"),
            "entgeltatlasApi": API_URL,
        },
        "filter": {
            "region": {"id": 1, "bezeichnung": "Deutschland"},
            "branche": {"id": 1, "bezeichnung": "Gesamt"},
            "geschlechter": GENDER_NAMES,
            "altergruppen": AGE_NAMES,
        },
        "summe": {
            "kldb3stellig": counts["3"],
            "kldb5stellig": counts["5"],
        },
        "statistik": {
            "anzahlBerufe": len(berufe),
            "eindeutigeKldb3Stellig": unique_counts["3"],
            "eindeutigeKldb5Stellig": unique_counts["5"],
            "erklaerung": "summe zählt die Berufe der Eingabeliste nach KldB-Stellenzahl; statistik zählt die tatsächlich abgefragten eindeutigen KldB-Schlüssel.",
        },
        "berufe": output_berufe,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--api-key", default=None, help="API-Key; alternativ ENTGELTATLAS_API_KEY")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    import os
    api_key = args.api_key or os.environ.get("ENTGELTATLAS_API_KEY")
    if not api_key:
        parser.error("API-Key fehlt: ENTGELTATLAS_API_KEY setzen oder --api-key verwenden")
    if args.workers < 1 or args.retries < 0:
        parser.error("--workers muss >= 1 und --retries muss >= 0 sein")

    source, berufe = load_source(args.input)
    result = crawl(source, berufe, api_key, args.timeout, args.retries, args.workers)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(berufe)} Berufe nach {args.output} geschrieben.")


if __name__ == "__main__":
    main()
