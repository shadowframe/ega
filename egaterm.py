#!/usr/bin/env python3
"""Kleine, dependency-freie Terminaloberfläche für ega.json.

Start:
    python egaterm.py
    python egaterm.py --data data/ega.json
"""

from __future__ import annotations

import argparse
import curses
import json
import locale
import sys
from pathlib import Path
from typing import Any

DEFAULT_DATA = Path(__file__).with_name("data") / "ega.json"
GENDERS = ("alle", "männlich", "weiblich")
AGES = ("alle", "<25", "25-54", ">54")
FILTER_KEYS = {
    "1": ("gender", 0),
    "2": ("gender", 1),
    "3": ("gender", 2),
    "4": ("age", 0),
    "5": ("age", 1),
    "6": ("age", 2),
    "7": ("age", 3),
}
STATUS_VALUES = {-1, -2, -10, -100}
MAX_VISIBLE_SUGGESTIONS = 8
ASCII_LOGO = (
    " ███████╗ ██████╗  █████╗ ████████╗███████╗██████╗ ███╗   ███╗",
    " ██╔════╝██╔════╝ ██╔══██╗╚══██╔══╝██╔════╝██╔══██╗████╗ ████║",
    " █████╗  ██║  ███╗███████║   ██║   █████╗  ██████╔╝██╔████╔██║",
    " ██╔══╝  ██║   ██║██╔══██║   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║",
    " ███████╗╚██████╔╝██║  ██║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║",
    " ╚══════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝",
)


def has_entgelt_data(metric: dict[str, Any] | None) -> bool:
    """True, wenn mindestens ein Entgeltwert kein API-Statuscode ist."""
    if not metric:
        return False
    return any(
        isinstance(metric.get(key), (int, float))
        and metric[key] not in STATUS_VALUES
        and metric[key] >= 0
        for key in ("median", "unteresQuartil", "oberesQuartil")
    )


def metric_for_filters(beruf: dict[str, Any], gender: str, age: str) -> dict[str, Any] | None:
    """Liest einen Wert aus beiden unterstützten ega.json-Strukturen.

    Die aktuelle ega.json enthält Geschlecht und Alter als getrennte Ansichten.
    Eine künftige Kreuztabelle (Geschlecht -> Alter -> Werte) wird ebenfalls
    verstanden.
    """
    values = ((beruf.get("ega") or {}).get("werte") or {})
    genders = values.get("geschlecht") or {}
    ages = values.get("altergruppe") or {}

    gender_value = genders.get(gender)
    if isinstance(gender_value, dict) and age in gender_value:
        # Kreuztabelle: geschlecht -> altergruppe -> Metrik
        candidate = gender_value[age]
        return candidate if isinstance(candidate, dict) else None
    if gender != "alle" and age == "alle":
        return gender_value if isinstance(gender_value, dict) else None
    if gender == "alle" and age != "alle":
        candidate = ages.get(age)
        return candidate if isinstance(candidate, dict) else None
    if gender == "alle" and age == "alle":
        candidate = genders.get("alle") or ages.get("alle")
        return candidate if isinstance(candidate, dict) else None
    return None


def matching_berufe(berufe: list[dict[str, Any]], query: str, gender: str, age: str) -> list[dict[str, Any]]:
    query = query.casefold().strip()
    result = []
    for beruf in berufe:
        if not has_entgelt_data(metric_for_filters(beruf, gender, age)):
            continue
        haystack = " ".join(
            str(beruf.get(key, ""))
            for key in ("bezeichnung", "codenr", "obercodenr")
        ).casefold()
        if not query or query in haystack:
            result.append(beruf)
    return result


def fmt_money(value: Any) -> str:
    if not isinstance(value, (int, float)) or value in STATUS_VALUES or value < 0:
        return "keine Daten"
    return f"{int(value):,}".replace(",", ".") + " €"


def shorten(text: str, width: int) -> str:
    if width <= 1:
        return ""
    return text if len(text) < width else text[: width - 1] + "…"


def color(pair: int = 0, flags: int = 0) -> int:
    """Kombiniert ein Farb-Paar sicher mit curses-Attributen."""
    try:
        return flags | curses.color_pair(pair)
    except curses.error:
        return flags


def add_line(window: Any, row: int, text: str = "", attr: int = 0, col: int = 0) -> None:
    height, width = window.getmaxyx()
    if 0 <= row < height - 1 and 0 <= col < width - 1:
        try:
            window.addnstr(row, col, text, max(0, width - col - 1), attr)
        except curses.error:
            pass


def panel_line(window: Any, row: int, left: str, right: str = "", attr: int = 0) -> None:
    height, width = window.getmaxyx()
    if not (0 <= row < height - 1):
        return
    body_width = max(1, width - 4)
    left = shorten(left, body_width)
    right = shorten(right, body_width)
    try:
        window.addnstr(row, 1, left, body_width, attr)
        if right and width > len(right) + 3:
            window.addnstr(row, max(2, width - len(right) - 2), right, len(right), attr)
    except curses.error:
        pass


def draw_visual(window: Any, row: int, metric: dict[str, Any], width: int) -> int:
    q25, median, q75 = (
        metric.get("unteresQuartil"),
        metric.get("median"),
        metric.get("oberesQuartil"),
    )
    if not all(isinstance(v, (int, float)) and v >= 0 and v not in STATUS_VALUES for v in (q25, median, q75)):
        add_line(window, row, "  ◌  Visualisierung nicht möglich: Entgeltwerte fehlen.", color(5))
        return row + 1

    track = max(24, min(72, width - 34))
    span = max(float(q75) - float(q25), 1.0)
    marker = round((float(median) - float(q25)) / span * (track - 1))
    marker = max(0, min(track - 1, marker))
    left = float(median) - float(q25)
    right = float(q75) - float(median)
    bar_left = "━" * marker
    bar_right = "─" * max(0, track - marker - 1)
    prefix = f"  Q25 {fmt_money(q25):>10}  ├"
    suffix = f"┤  Q75 {fmt_money(q75):<10}"
    add_line(window, row, prefix + bar_left, color(4))
    add_line(window, row, "◆", color(3, curses.A_BOLD), col=len(prefix) + len(bar_left))
    add_line(window, row, bar_right + suffix, color(4), col=len(prefix) + len(bar_left) + 1)
    add_line(window, row + 1, f"  {'':18}◀ {fmt_money(left)} bis Median                 Median bis {fmt_money(right)} ▶", color(6))
    add_line(window, row + 2, f"  {'':18}unteres Quartil                         oberes Quartil", curses.A_DIM)
    return row + 3


def draw(window: Any, berufe: list[dict[str, Any]], query: str, suggestions: list[dict[str, Any]], selected: int, gender_i: int, age_i: int, chosen: dict[str, Any] | None, status: str) -> None:
    window.erase()
    height, width = window.getmaxyx()
    gender, age = GENDERS[gender_i], AGES[age_i]
    if height < 32 or width < 78:
        add_line(window, 0, "egaTERM", color(1, curses.A_BOLD))
        add_line(window, 2, "Bitte Terminal auf mindestens 78 × 32 Zeichen vergrößern.", color(5, curses.A_BOLD))
        add_line(window, 4, f"Aktuell: {width} × {height}", curses.A_DIM)
        add_line(window, height - 2, "Esc/q beendet die Anwendung", curses.A_DIM)
        window.refresh()
        return

    # Mehrzeiliges ASCII-Schriftlogo: egaTERM.
    for logo_row, logo_line in enumerate(ASCII_LOGO):
        logo_attr = color(1, curses.A_BOLD) if logo_row % 2 == 0 else color(3, curses.A_BOLD)
        add_line(window, logo_row, logo_line.center(width - 2), logo_attr)
    add_line(window, 6, "Berufliche Entgelte für Deutschland  ·  Branche Gesamt".center(width - 2), color(6))
    add_line(window, 7, "─" * (width - 2), color(1))

    # Filter-Chips.
    add_line(window, 9, "FILTER", color(3, curses.A_BOLD))
    add_line(window, 10, f"  ⚥  GESCHLECHT   [{gender:^10}]     ◷  ALTER   [{age:^6}]     ◉  DATEN   {len(suggestions):>4} Treffer", color(6, curses.A_BOLD))
    add_line(window, 11, "  1–3 Geschlecht   4–7 Alter   0 Beenden   Ctrl+U Suche leeren   ↑/↓ Vorschlag   Enter Auswahl", curses.A_DIM)

    # Suche.
    add_line(window, 13, "⌕  BERUF SUCHEN", color(3, curses.A_BOLD))
    search_attr = color(2, curses.A_BOLD)
    add_line(window, 14, f"  ❯ {query}_", search_attr)
    add_line(window, 15, "─" * (width - 2), color(1))

    row = 16
    add_line(window, row, f"VORSCHLÄGE  ·  {min(len(suggestions), MAX_VISIBLE_SUGGESTIONS)} von {len(suggestions)}", color(3, curses.A_BOLD))
    row += 1
    if suggestions:
        for index, beruf in enumerate(suggestions[:MAX_VISIBLE_SUGGESTIONS]):
            marker = "◆" if index == selected else "·"
            attr = color(2, curses.A_BOLD) if index == selected else color(6)
            line = f"  {marker}  {beruf.get('bezeichnung', '')}  ·  {beruf.get('codenr', '')}"
            add_line(window, row, shorten(line, width - 2), attr)
            row += 1
    else:
        add_line(window, row, "  ◌  Keine passenden Berufe mit vorhandenen Entgeltdaten.", color(5))
        row += 1
        if gender != "alle" and age != "alle":
            add_line(window, row, "  Die ausgewählte Kreuzkombination ist in dieser ega.json nicht vorhanden.", curses.A_DIM)
            row += 1

    # Detailkarte mit prominentem Median.
    row = max(row + 1, 22)
    add_line(window, row, "─" * (width - 2), color(1))
    row += 1
    if chosen:
        metric = metric_for_filters(chosen, gender, age) or {}
        add_line(window, row, shorten(f"▰  AUSGEWÄHLTER BERUF  ·  {chosen.get('bezeichnung', '')}", width - 2), color(1, curses.A_BOLD))
        row += 1
        add_line(window, row, f"   KldB {chosen.get('ega', {}).get('kldb', '–')}   │   {gender}   │   {age}", color(6))
        row += 2
        add_line(window, row, f"   ▌  MEDIAN   {fmt_money(metric.get('median')):^14}  ▐", color(3, curses.A_BOLD | curses.A_REVERSE))
        add_line(window, row + 1, f"   ◇  Q25      {fmt_money(metric.get('unteresQuartil')):<14}    ◆  Q75      {fmt_money(metric.get('oberesQuartil')):<14}", color(6))
        row += 3
        draw_visual(window, row, metric, width)
    else:
        add_line(window, row, "   ◈  Noch kein Beruf ausgewählt  ·  Enter auf einem Vorschlag drücken", color(6, curses.A_BOLD))

    add_line(window, height - 3, "╰" + "─" * (width - 2) + "╯", color(1))
    add_line(window, height - 2, shorten(f"  {status}", width - 2), color(6))
    window.refresh()


def run_tui(data: dict[str, Any]) -> None:
    berufe = data.get("berufe") or []
    if not berufe:
        raise ValueError("Die JSON-Datei enthält keine Berufe.")

    def app(window: Any) -> None:
        locale.setlocale(locale.LC_ALL, "")
        curses.curs_set(1)
        window.keypad(True)
        try:
            curses.start_color()
            curses.use_default_colors()
            for pair, foreground in (
                (1, curses.COLOR_CYAN),
                (2, curses.COLOR_GREEN),
                (3, curses.COLOR_YELLOW),
                (4, curses.COLOR_BLUE),
                (5, curses.COLOR_RED),
                (6, curses.COLOR_WHITE),
            ):
                curses.init_pair(pair, foreground, -1)
        except curses.error:
            pass
        query = ""
        gender_i = age_i = selected = 0
        chosen = None
        status = "Bereit"
        while True:
            suggestions = matching_berufe(berufe, query, GENDERS[gender_i], AGES[age_i])
            visible_count = min(len(suggestions), MAX_VISIBLE_SUGGESTIONS)
            selected = max(0, min(selected, max(0, visible_count - 1)))
            draw(window, berufe, query, suggestions, selected, gender_i, age_i, chosen, status)
            key = window.get_wch()
            if key == "0" or key == "\x1b" or (key in ("q", "Q") and not query):
                return
            if key in FILTER_KEYS:
                filter_type, filter_index = FILTER_KEYS[key]
                if filter_type == "gender":
                    gender_i = filter_index
                    status = f"Geschlechtsfilter: {GENDERS[gender_i]}"
                else:
                    age_i = filter_index
                    status = f"Altersfilter: {AGES[age_i]}"
                selected = 0
                chosen = None
            elif key in (curses.KEY_UP, "\x10"):
                selected = max(0, selected - 1)
            elif key in (curses.KEY_DOWN, "\x0e"):
                selected = min(max(0, visible_count - 1), selected + 1)
            elif key in ("\n", "\r", curses.KEY_ENTER):
                if suggestions:
                    chosen = suggestions[selected]
                    status = "Datensatz ausgewählt"
            elif key in (curses.KEY_BACKSPACE, "\b", "\x7f"):
                query = query[:-1]
                selected = 0
                chosen = None
            elif key == "\x15":  # Ctrl+U
                query = ""
                selected = 0
                chosen = None
                status = "Suchfeld geleert"
            elif isinstance(key, str) and key.isprintable() and len(key) == 1:
                query += key
                selected = 0
                chosen = None

    curses.wrapper(app)


def self_test() -> None:
    assert not has_entgelt_data({"median": -1, "unteresQuartil": -1, "oberesQuartil": -1})
    assert has_entgelt_data({"median": 2500, "unteresQuartil": -1, "oberesQuartil": -1})
    beruf = {"ega": {"werte": {"geschlecht": {"alle": {"median": 1}}, "altergruppe": {"25-54": {"median": 2}}}}}
    assert metric_for_filters(beruf, "alle", "alle")["median"] == 1
    assert metric_for_filters(beruf, "alle", "25-54")["median"] == 2
    print("egaterm self-test: OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    try:
        data = json.loads(args.data.read_text(encoding="utf-8"))
        run_tui(data)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print(f"Fehler: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
