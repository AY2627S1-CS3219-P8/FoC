# AI Assistance Disclosure:
# Tool: Codex (model: GPT-6), date: 2026-09-30
# Scope: Writing implementation code — test command execution, real-source counts, stable identities, inert import, absent database access, unchanged files, and rejected invalid batches in subprocesses.
# Author review: All affected work reviewed by Keith.
# Details: ../../ai/usage-log.md; ai-20260930-008

"""Subprocess contracts for the read-only seed command."""

import csv
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SERVICE = Path(__file__).resolve().parents[2]
CSV = SERVICE.parent / "data/csv/supplier-seed-data.csv"
MAPPINGS = [SERVICE / "seed/manifest.json", SERVICE / "seed/area_mapping.json"]
MODULE = "app.commands.seed_suppliers"


def environment():
    env = {key: value for key, value in os.environ.items() if not any(
        token in key.upper() for token in ("DATABASE", "POSTGRES", "USER_SERVICE", "AUTH_TIMEOUT")
    )}
    env["PYTHONPATH"] = str(SERVICE)
    return env


def run(*args, cwd=SERVICE):
    return subprocess.run([sys.executable, "-m", MODULE, *map(str, args)], cwd=cwd,
                          env=environment(), capture_output=True, text=True, check=False)


def write_source(path, mutate=None, reverse=False):
    with CSV.open(encoding="cp1252", newline="") as stream:
        reader = csv.DictReader(stream)
        headers, rows = reader.fieldnames, list(reader)
    if mutate:
        mutate(rows)
    with path.open("w", encoding="cp1252", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(reversed(rows) if reverse else rows)


def test_real_repeated_and_reordered_data_are_stable_and_read_only(tmp_path):
    before = {path: path.read_bytes() for path in [CSV, *MAPPINGS]}
    reordered = tmp_path / "reordered.csv"
    write_source(reordered, reverse=True)
    reports = []
    for path in (CSV, CSV, reordered):
        completed = run("--file", path, "--dry-run", cwd=tmp_path)
        assert completed.returncode == 0, completed.stderr
        report = json.loads(completed.stdout)
        assert report["valid"] and not report["batch_rejected"]
        assert report["source_count"] == report["validated_supplier_count"] == 21
        assert report["category_counts"] == {"Food": 16, "Coffee": 5, "Shopping": 3, "Printing": 2}
        assert report["total_category_assignments"] == 26
        assert len(report["reviewed_corrections"]) == 5
        assert not report["issues"]
        reports.append(report)
    def identities(report):
        return {item["seed_key"]: item["supplier_id"] for item in report["validated_records"]}
    assert identities(reports[0]) == identities(reports[1]) == identities(reports[2])
    expected = {entry["seed_key"] for entry in json.loads(MAPPINGS[0].read_text()) if entry["correct_24_hours"]}
    for report in reports:
        assert {item["seed_key"] for item in report["reviewed_corrections"]} == expected
        assert all(item["closing_day_offset"] == 1 for item in report["reviewed_corrections"])
    assert {path: path.read_bytes() for path in before} == before


def test_multiple_failures_reject_batch_but_count_only_validated_records(tmp_path):
    path = tmp_path / "invalid.csv"
    def mutate(rows):
        rows[0].update(Type="Unknown//Food", StartingTime="900hrs", Latitude="NaN", ImageURL="https://elsewhere/ANNA.jpeg")
        rows[1]["Longitude"] = "181"
    write_source(path, mutate)
    completed = run("--file", path, "--dry-run")
    assert completed.returncode == 1 and "Traceback" not in completed.stderr
    report = json.loads(completed.stdout)
    assert report["batch_rejected"] and not report["valid"]
    assert report["source_count"] == 21 and report["validated_supplier_count"] == 19
    assert report["total_category_assignments"] == sum(report["category_counts"].values())
    assert {"UNKNOWN_CATEGORY", "BLANK_CATEGORY", "INVALID_SOURCE_TIME", "INVALID_COORDINATE",
            "UNKNOWN_IMAGE", "COORDINATE_OUT_OF_RANGE"} <= {issue["code"] for issue in report["issues"]}
    assert all(issue["file"] and issue["row_number"] and issue["seed_key"] for issue in report["issues"])
    assert "Batch rejected" in report["message"]


@pytest.mark.parametrize("args", [[], ["--dry-run"], ["--file", str(CSV)]])
def test_usage_and_required_dry_run(args):
    completed = run(*args)
    assert completed.returncode != 0
    assert "usage:" in completed.stderr and "Traceback" not in completed.stderr
    if "--file" in args:
        assert "Add --dry-run" in completed.stderr


def test_unreadable_source(tmp_path):
    completed = run("--file", tmp_path / "missing.csv", "--dry-run")
    report = json.loads(completed.stdout)
    assert completed.returncode == 1 and report["batch_rejected"]
    assert "SOURCE_READ_ERROR" in {issue["code"] for issue in report["issues"]}
    assert "Traceback" not in completed.stderr


def test_missing_mappings_are_reported_without_traceback(tmp_path):
    code = f"""
from pathlib import Path
from app.commands import seed_suppliers
seed_suppliers.SEED_ROOT = Path({str(tmp_path)!r})
raise SystemExit(seed_suppliers.main(['--file', {str(CSV)!r}, '--dry-run']))
"""
    completed = subprocess.run([sys.executable, "-c", code], env=environment(), cwd=tmp_path,
                               capture_output=True, text=True)
    assert completed.returncode == 1 and "Traceback" not in completed.stderr
    report = json.loads(completed.stdout)
    assert report["batch_rejected"] and not report["validated_records"]
    assert "JSON_READ_ERROR" in {issue["code"] for issue in report["issues"]}


def test_import_is_inert_and_execution_never_imports_database_modules(tmp_path):
    code = f"""
import contextlib
import importlib.abc
import io
import sys
class RejectDatabase(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {{'sqlalchemy', 'psycopg', 'psycopg2'}} or fullname in {{'app.db', 'app.config', 'app.main'}}:
            raise AssertionError('Unexpected database/application import: ' + fullname)
sys.meta_path.insert(0, RejectDatabase())
sys.argv = ['test', '--invalid-import-argument']
output = io.StringIO()
with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
    from app.commands.seed_suppliers import main
assert output.getvalue() == ''
raise SystemExit(main(['--file', {str(CSV)!r}, '--dry-run']))
"""
    completed = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=environment(),
                               capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["valid"]
