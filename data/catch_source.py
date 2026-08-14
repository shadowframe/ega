#!/usr/bin/env python3
"""Lädt die beiden offiziellen DKZ-Quelldateien sicher herunter."""

from __future__ import annotations

import argparse
import os
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

XML_URL = "https://rest.arbeitsagentur.de/infosysbub/download-portal-rest/ct/dkz-downloads/DKZ_alle_Berufe_gueltig_ungueltig.xml"
XLSX_URL = "https://rest.arbeitsagentur.de/infosysbub/download-portal-rest/ct/dkz-downloads/DKZ_Berufe_Zuordnung_Berufsgattung.xlsx"
XML_NAME = "DKZ_alle_Berufe_gueltig_ungueltig.xml"
XLSX_NAME = "DKZ_Berufe_Zuordnung_Berufsgattung.xlsx"
USER_AGENT = "ega-dkz-source-downloader/1.0"


def _download(url: str, destination: Path, timeout: float, retries: int) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        temporary_name: str | None = None
        try:
            request = Request(url, headers={"Accept": "*/*", "User-Agent": USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                with tempfile.NamedTemporaryFile(
                    mode="wb", dir=destination.parent, prefix=f".{destination.name}.", suffix=".part", delete=False
                ) as temporary:
                    temporary_name = temporary.name
                    while chunk := response.read(1024 * 1024):
                        temporary.write(chunk)
                    temporary.flush()
                    os.fsync(temporary.fileno())
            temporary_path = Path(temporary_name)
            if temporary_path.stat().st_size == 0:
                raise ValueError(f"Leere Antwort für {url}")
            os.replace(temporary_path, destination)
            return destination
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            last_error = error
            if temporary_name:
                Path(temporary_name).unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"Download fehlgeschlagen: {url}: {last_error}") from last_error


def _validate_xml(path: Path) -> None:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        raise ValueError(f"XML-Quelle ist ungültig: {path}") from error
    if root.tag.rsplit("}", 1)[-1] not in {"alleBerufe", "berufe", "berufeliste", "root"}:
        raise ValueError(f"Unerwartetes XML-Wurzelelement: {root.tag}")


def _validate_xlsx(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise ValueError(f"XLSX-Quelle ist keine gültige ZIP-Datei: {path}")
    with zipfile.ZipFile(path) as archive:
        required = {"xl/workbook.xml"}
        missing = required - set(archive.namelist())
        if missing:
            raise ValueError(f"XLSX-Quelle ist unvollständig; fehlt: {sorted(missing)}")
        if archive.testzip() is not None:
            raise ValueError(f"XLSX-Quelle enthält ein beschädigtes Archiv: {path}")


def download_sources(output_dir: Path, timeout: float = 30.0, retries: int = 3) -> dict[str, Path]:
    """Lädt XML und XLSX atomar und gibt die beiden Zielpfade zurück."""
    if timeout <= 0 or retries < 0:
        raise ValueError("timeout muss > 0 und retries muss >= 0 sein")
    xml_path = _download(XML_URL, output_dir / XML_NAME, timeout, retries)
    xlsx_path = _download(XLSX_URL, output_dir / XLSX_NAME, timeout, retries)
    try:
        _validate_xml(xml_path)
        _validate_xlsx(xlsx_path)
    except Exception:
        # Bei ungültigen Quellen keine fehlerhaften Quelldateien liegen lassen.
        xml_path.unlink(missing_ok=True)
        xlsx_path.unlink(missing_ok=True)
        raise
    return {"xml": xml_path, "xlsx": xlsx_path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    sources = download_sources(args.output_dir, args.timeout, args.retries)
    for kind, path in sources.items():
        print(f"{kind.upper()}: {path} ({path.stat().st_size:,} Bytes)".replace(",", "."))


if __name__ == "__main__":
    main()
