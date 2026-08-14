#!/usr/bin/env python3
"""Führt die vollständige EGA-Datenpipeline als eine sichere Batchkette aus."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    from .entgeltatlas_client import ClientKeyError, resolve_api_key
except ImportError:  # Direkter Aufruf: python data/main.py
    from entgeltatlas_client import ClientKeyError, resolve_api_key

DATA_DIR = Path(__file__).resolve().parent


def build_commands(data_dir: Path, reference_date: str | None, timeout: float, retries: int, workers: int) -> list[list[str]]:
    """Erzeugt die drei fail-fast Befehle ohne Geheimnisse in der Kommandozeile."""
    python = sys.executable
    create_args = [python, str(data_dir / "create_data.py")]
    if reference_date:
        create_args.extend(["--reference-date", reference_date])
    crawler = [
        python,
        str(data_dir / "crawler.py"),
        "--timeout",
        str(timeout),
        "--retries",
        str(retries),
        "--workers",
        str(workers),
    ]
    return [
        [python, str(data_dir / "catch_source.py"), "--timeout", str(timeout), "--retries", str(retries)],
        create_args,
        crawler,
    ]


def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("TERM") not in {None, "dumb"}


class Console:
    def __init__(self, color: bool | None = None) -> None:
        self.color = _supports_color() if color is None else color
        self.cyan = "\033[36m" if self.color else ""
        self.green = "\033[32m" if self.color else ""
        self.yellow = "\033[33m" if self.color else ""
        self.red = "\033[31m" if self.color else ""
        self.dim = "\033[2m" if self.color else ""
        self.bold = "\033[1m" if self.color else ""
        self.reset = "\033[0m" if self.color else ""

    def line(self, text: str = "") -> None:
        print(text, flush=True)

    def banner(self) -> None:
        self.line(f"{self.cyan}{self.bold}╭─ EGA DATA BATCH ─────────────────────────────────────────────╮{self.reset}")
        self.line(f"{self.cyan}│{self.reset}  Quellen holen  →  Berufeliste bereinigen  →  Entgelte crawlen {self.cyan}│{self.reset}")
        self.line(f"{self.cyan}╰──────────────────────────────────────────────────────────────╯{self.reset}")

    def stage(self, number: int, total: int, title: str, command: list[str]) -> None:
        rendered = " ".join(_safe_command_part(part) for part in command)
        self.line(f"\n{self.yellow}{self.bold}[{number}/{total}] {title}{self.reset}")
        self.line(f"{self.dim}$ {rendered}{self.reset}")

    def result(self, success: bool, duration: float) -> None:
        icon = "✓" if success else "✗"
        color = self.green if success else self.red
        self.line(f"{color}{self.bold}{icon}{self.reset} abgeschlossen in {duration:.1f}s")


def _safe_command_part(part: str) -> str:
    # API-Schlüssel werden ausschließlich aus der Umgebung gelesen und erscheinen daher nie.
    return part


def run_stage(command: list[str], title: str, number: int, console: Console, env: dict[str, str]) -> None:
    console.stage(number, 3, title, command)
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=DATA_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for output in process.stdout:
        line = output.rstrip()
        if line:
            console.line(f"  {console.dim}│{console.reset} {line}")
    return_code = process.wait()
    console.result(return_code == 0, time.monotonic() - started)
    if return_code != 0:
        raise RuntimeError(f"Batchstufe fehlgeschlagen: {title} (Exit-Code {return_code})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-date", help="Stichtag für die Bereinigung, Format JJJJ-MM-TT")
    parser.add_argument("--timeout", type=float, default=30.0, help="Netzwerk-Timeout in Sekunden")
    parser.add_argument("--retries", type=int, default=3, help="Wiederholungen bei Netzwerkfehlern")
    parser.add_argument("--workers", type=int, default=8, help="Parallele Entgeltatlas-Anfragen")
    parser.add_argument("--plain", action="store_true", help="Ausgabe ohne ANSI-Farben")
    args = parser.parse_args()
    if args.timeout <= 0 or args.retries < 0 or args.workers < 1:
        parser.error("timeout muss > 0, retries >= 0 und workers >= 1 sein")
    try:
        api_key = resolve_api_key(timeout=args.timeout)
    except ClientKeyError as error:
        parser.error(str(error))

    console = Console(color=False if args.plain else None)
    commands = build_commands(DATA_DIR, args.reference_date, args.timeout, args.retries, args.workers)
    titles = ("DKZ-Quelldateien herunterladen", "Berufeliste bereinigen", "Entgeltatlas-Daten abrufen")
    console.banner()
    console.line(f"{console.dim}Arbeitsverzeichnis: {DATA_DIR}{console.reset}")
    console.line(f"{console.dim}API-Key: gesetzt (Wert wird nicht angezeigt){console.reset}")
    env = os.environ.copy()
    env["ENTGELTATLAS_API_KEY"] = api_key
    try:
        for number, (command, title) in enumerate(zip(commands, titles), start=1):
            run_stage(command, title, number, console, env)
    except (OSError, RuntimeError) as error:
        console.line(f"\n{console.red}{console.bold}Batch abgebrochen:{console.reset} {error}")
        return 1
    console.line(f"\n{console.green}{console.bold}✓ Batchkette erfolgreich abgeschlossen.{console.reset}")
    console.line(f"{console.dim}Ergebnisse: berufe_bereinigt.json und ega.json{console.reset}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
