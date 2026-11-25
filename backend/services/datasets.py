"""Inspect local CSV integrity without serving raw records."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def dataset_status(root: Path = ROOT) -> list[dict]:
    manifest = json.loads((root / 'data/manifest.json').read_text())
    output = []
    for name, expected in manifest.items():
        path = root / 'data/raw' / name
        result = {'name': name, 'role': expected['role'], 'rows': expected['rows'],
                  'columns': len(expected['columns']), 'status': 'missing'}
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result['status'] = 'verified' if digest == expected['sha256'] else 'modified'
        output.append(result)
    return output


def audit_csv(path: Path) -> dict:
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    return {'rows': len(rows), 'columns': header,
            'missing_cells': sum(not v.strip() for r in rows for v in r),
            'duplicate_rows': len(rows) - len(set(map(tuple, rows))),
            'malformed_rows': sum(len(r) != len(header) for r in rows),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
