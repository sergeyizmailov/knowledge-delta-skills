#!/usr/bin/env python3
"""Summarize an English-language Meta Ads Manager CSV export as Markdown."""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections.abc import Iterable
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="Ads Manager CSV export.")
    parser.add_argument(
        "--name-column",
        help="Entity label column. Defaults to Ad name, Ad set name, then Campaign name.",
    )
    parser.add_argument(
        "--result-column",
        help="Business-result column used for CVR and CPA, such as Purchases or Qualified leads.",
    )
    parser.add_argument(
        "--value-column",
        help="Revenue/value column used for ROAS, such as Purchase conversion value.",
    )
    parser.add_argument("--top", type=int, default=15, help="Rows to show by spend (default: 15).")
    return parser.parse_args()


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    value = raw.strip().replace("\u00a0", "").replace(" ", "")
    if not value or value in {"—", "-", "N/A", "n/a"}:
        return None
    value = re.sub(r"[^0-9,.+\-%]", "", value).rstrip("%")
    if not value:
        return None
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        tail = value.rsplit(",", 1)[1]
        value = value.replace(",", "." if len(tail) in {1, 2} else "")
    try:
        return float(value)
    except ValueError:
        return None


def first_matching(headers: list[str], candidates: Iterable[str]) -> str | None:
    index = {normalized(header): header for header in headers}
    for candidate in candidates:
        if normalized(candidate) in index:
            return index[normalized(candidate)]
    return None


def resolve_exact(headers: list[str], requested: str | None, label: str) -> str | None:
    if requested is None:
        return None
    match = first_matching(headers, [requested])
    if match is None:
        raise ValueError(f"{label} not found: {requested}")
    return match


def resolve_spend(headers: list[str]) -> str | None:
    exact = first_matching(headers, ["Amount spent"])
    if exact:
        return exact
    return next((header for header in headers if normalized(header).startswith("amount spent")), None)


def total(rows: list[dict[str, str]], column: str | None) -> float | None:
    if column is None:
        return None
    values = [parse_number(row.get(column)) for row in rows]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def ratio(numerator: float | None, denominator: float | None, scale: float = 1.0) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return numerator / denominator * scale


def fmt_number(value: float | None, digits: int = 0) -> str:
    if value is None or not math.isfinite(value):
        return "—"
    return f"{value:,.{digits}f}"


def fmt_money(value: float | None) -> str:
    return fmt_number(value, 2)


def fmt_percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}%"


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def main() -> int:
    args = parse_args()
    if args.top < 1:
        print("--top must be at least 1", file=sys.stderr)
        return 2
    csv_path = args.csv_file.expanduser().resolve()
    if not csv_path.is_file():
        print(f"CSV file does not exist: {csv_path}", file=sys.stderr)
        return 2

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        rows = list(reader)
    if not headers or not rows:
        print("CSV must contain a header and at least one data row", file=sys.stderr)
        return 2

    try:
        name_col = resolve_exact(headers, args.name_column, "Name column") or first_matching(
            headers, ["Ad name", "Ad set name", "Campaign name"]
        )
        result_col = resolve_exact(headers, args.result_column, "Result column")
        value_col = resolve_exact(headers, args.value_column, "Value column")
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    columns = {
        "spend": resolve_spend(headers),
        "impressions": first_matching(headers, ["Impressions"]),
        "reach": first_matching(headers, ["Reach"]),
        "clicks": first_matching(headers, ["Outbound clicks", "Link clicks"]),
        "lpv": first_matching(headers, ["Landing page views"]),
        "three_second": first_matching(
            headers,
            ["3-second video plays", "3-second video views", "Video plays at 3 seconds"],
        ),
        "thruplay": first_matching(headers, ["ThruPlays", "Thruplays"]),
    }
    sums = {key: total(rows, column) for key, column in columns.items()}
    sums["results"] = total(rows, result_col)
    sums["value"] = total(rows, value_col)

    metrics = {
        "CPM": ratio(sums["spend"], sums["impressions"], 1000),
        "Click CTR": ratio(sums["clicks"], sums["impressions"], 100),
        "CPC": ratio(sums["spend"], sums["clicks"]),
        "Click → LPV": ratio(sums["lpv"], sums["clicks"], 100),
        "LPV → selected result": ratio(sums["results"], sums["lpv"], 100),
        "CPA": ratio(sums["spend"], sums["results"]),
        "ROAS": ratio(sums["value"], sums["spend"]),
        "Hook rate": ratio(sums["three_second"], sums["impressions"], 100),
        "Hold rate": ratio(sums["thruplay"], sums["three_second"], 100),
    }

    print("# Meta Ads export summary")
    print()
    print(f"- File: `{markdown_escape(csv_path.name)}`")
    print(f"- Rows: {len(rows)}")
    print(f"- Entity: `{name_col}`" if name_col else "- Entity: not detected")
    print(f"- Result: `{result_col}`" if result_col else "- Result: not selected")
    print(f"- Value: `{value_col}`" if value_col else "- Value: not selected")
    print()
    print("## Weighted totals")
    print()
    print("| Metric | Value |")
    print("|---|---:|")
    for label, value in [
        ("Spend", fmt_money(sums["spend"])),
        ("Impressions", fmt_number(sums["impressions"])),
        (columns["clicks"] or "Outbound/link clicks", fmt_number(sums["clicks"])),
        ("Landing page views", fmt_number(sums["lpv"])),
        (result_col or "Business results", fmt_number(sums["results"], 2)),
        (value_col or "Conversion value", fmt_money(sums["value"])),
        ("CPM", fmt_money(metrics["CPM"])),
        (f"CTR ({columns['clicks']})" if columns["clicks"] else "Click CTR", fmt_percent(metrics["Click CTR"])),
        ("CPC", fmt_money(metrics["CPC"])),
        ("Click → LPV", fmt_percent(metrics["Click → LPV"])),
        ("LPV → selected result ratio", fmt_percent(metrics["LPV → selected result"])),
        ("CPA", fmt_money(metrics["CPA"])),
        ("ROAS", fmt_number(metrics["ROAS"], 2)),
        ("Hook rate (3-second plays / impressions)", fmt_percent(metrics["Hook rate"])),
        ("Hold rate (ThruPlays / 3-second plays)", fmt_percent(metrics["Hold rate"])),
    ]:
        print(f"| {markdown_escape(label)} | {value} |")

    if name_col and columns["spend"]:
        ranked = sorted(
            rows,
            key=lambda row: parse_number(row.get(columns["spend"])) or 0,
            reverse=True,
        )[: args.top]
        print()
        print(f"## Top {len(ranked)} rows by spend")
        print()
        click_rate_label = f"CTR ({columns['clicks']})" if columns["clicks"] else "Click CTR"
        print(f"| Entity | Spend | Impressions | {click_rate_label} | Click → LPV | Results | CPA | ROAS |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|")
        for row in ranked:
            spend = parse_number(row.get(columns["spend"]))
            impressions = parse_number(row.get(columns["impressions"])) if columns["impressions"] else None
            clicks = parse_number(row.get(columns["clicks"])) if columns["clicks"] else None
            lpv = parse_number(row.get(columns["lpv"])) if columns["lpv"] else None
            results = parse_number(row.get(result_col)) if result_col else None
            value = parse_number(row.get(value_col)) if value_col else None
            print(
                "| "
                + " | ".join(
                    [
                        markdown_escape(row.get(name_col, "") or "(blank)"),
                        fmt_money(spend),
                        fmt_number(impressions),
                        fmt_percent(ratio(clicks, impressions, 100)),
                        fmt_percent(ratio(lpv, clicks, 100)),
                        fmt_number(results, 2),
                        fmt_money(ratio(spend, results)),
                        fmt_number(ratio(value, spend), 2),
                    ]
                )
                + " |"
            )

    warnings: list[str] = []
    if result_col is None:
        warnings.append(
            "No result column was selected; CPA and conversion rate are intentionally omitted. "
            "Pass `--result-column` with one consistent business outcome."
        )
    if value_col is None:
        warnings.append("No value column was selected; ROAS is intentionally omitted.")
    if columns["clicks"] is None:
        warnings.append("No Outbound clicks or Link clicks column was found.")
    if columns["lpv"] is None:
        warnings.append("No Landing page views column was found; click-to-page loss cannot be assessed.")
    if columns["three_second"] is None or columns["thruplay"] is None:
        warnings.append("Video inputs are incomplete; hook and/or hold rate cannot be calculated.")
    if columns["reach"]:
        warnings.append("Reach is not summed because users can overlap across rows; calculate frequency in Ads Manager at the intended reporting level.")
    if result_col and columns["lpv"]:
        warnings.append(
            "The LPV-to-result ratio is not necessarily a landing-page session CVR: Ads Manager results can include view-through or modeled attribution. "
            "Use click-only or analytics/backend sessions for a true page CVR."
        )

    print()
    print("## Data-quality notes")
    print()
    for warning in warnings or ["No structural issues detected from the selected columns."]:
        print(f"- {warning}")
    print("- Interpret changes against comparable account cohorts, attribution settings, conversion lag, and backend outcomes; this report applies no universal performance thresholds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
