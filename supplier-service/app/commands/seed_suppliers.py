# AI Assistance Disclosure:
# Tool: Codex (model: GPT-6), date: 2026-09-30
# Scope: Writing implementation code — implement the specified read-only argparse command, module-relative mappings, contextual JSON diagnostics, validated counts, correction reporting, and batch exit behavior.
# Author review: All affected work reviewed by Keith.
# Details: ../../ai/usage-log.md; ai-20260930-008

"""Read-only seed validation: python -m app.commands.seed_suppliers --file ... --dry-run."""

import argparse
import json
from collections import Counter
from pathlib import Path

from app.commands.seed_parsing import (
    SeedSourceResult, load_csv, load_seed_source, normalize_seed_source,
)

SEED_ROOT = Path(__file__).resolve().parents[2] / "seed"


def dry_run_report(source_path: str | Path) -> dict[str, object]:
    """Report diagnostic successes without accepting any part of an invalid batch.

    The loader supplies matching/mapping issues and permanent identity. Each
    unambiguous match goes through the complete normalizer, even when another
    record failed. These diagnostic records are never an accepted partial import.
    """
    source = load_csv(source_path)
    matched = load_seed_source(source_path, SEED_ROOT / "manifest.json", SEED_ROOT / "area_mapping.json")
    issues = list(matched.issues)
    records, corrections = [], []
    counts = Counter({name: 0 for name in ("Food", "Coffee", "Shopping", "Printing")})
    for match in matched.matches:
        normalized = normalize_seed_source(SeedSourceResult((match,), ()))
        issues.extend(normalized.issues)
        for record in normalized.records:
            counts.update(record.category_names)
            records.append({
                "seed_key": record.seed_key,
                "supplier_id": str(record.supplier_id),
                "source": {"file": record.source.file, "row_number": record.source.row_number,
                           "Name": record.source.values.get("Name"), "Building": record.source.values.get("Building")},
                "values": record.values.model_dump(mode="json"),
                "category_names": list(record.category_names),
            })
            if match.correct_24_hours:
                corrections.append({
                    "seed_key": record.seed_key, "supplier_id": str(record.supplier_id),
                    "row_number": record.source.row_number,
                    "source_name": record.source.values.get("Name"),
                    "source_times": {"StartingTime": record.source.values.get("StartingTime"),
                                     "ClosingTime": record.source.values.get("ClosingTime")},
                    "opening_time": record.values.opening_time.isoformat(),
                    "closing_time": record.values.closing_time.isoformat(),
                    "closing_day_offset": record.values.closing_day_offset,
                })
    valid = not issues
    return {
        "dry_run": True, "valid": valid, "batch_rejected": not valid,
        "message": "Dry run valid; no data written." if valid else
                   "Batch rejected; no data written. Review the contextual issues and correct the source or reviewed mappings.",
        "source_count": len(source.records),
        "validated_supplier_count": len(records),
        "category_counts": dict(counts),
        "total_category_assignments": sum(counts.values()),
        "reviewed_corrections": corrections,
        "validated_records": records,
        "issues": [issue.to_dict() for issue in issues],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate reviewed supplier seeds without database access or writes.")
    parser.add_argument("--file", required=True, help="Path to the CP1252 supplier source CSV.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print a JSON report; required until persistence exists.")
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.error("Only dry-run mode is available. Add --dry-run; persistence is not implemented.")
    report = dry_run_report(args.file)
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
