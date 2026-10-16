"""Load the synthetic Harbourline mart into BigQuery, then prove BigQuery and the mirror agree.

Creates the dataset QUORUM_BQ_DATASET (default quorum_mart) in GOOGLE_CLOUD_PROJECT
and replaces its three tables. This creates billable resources: run it only on
purpose. Usage:

    GOOGLE_CLOUD_PROJECT=my-project python scripts/seed_bigquery.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.cloud import bigquery  # noqa: E402

from quorum import config, standby, synth, warehouse  # noqa: E402
from quorum.cases import ALERTS  # noqa: E402


def _schema(rows: list[dict], fields: tuple[str, ...]) -> list[bigquery.SchemaField]:
    out = []
    for field in fields:
        values = [row[field] for row in rows if row[field] is not None]
        if values and all(isinstance(value, bool) for value in values):
            kind = "BOOL"
        elif values and all(isinstance(value, int) and not isinstance(value, bool) for value in values):
            kind = "INT64"
        elif values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            kind = "FLOAT64"
        else:
            kind = "STRING"
        out.append(bigquery.SchemaField(field, kind))
    return out


def seed(client: bigquery.Client, project: str) -> None:
    mart = synth.build()
    tables = {
        "customers": (mart["customers"], synth.CUSTOMER_FIELDS),
        "accounts": (mart["accounts"], synth.ACCOUNT_FIELDS),
        "transactions": ([dict(zip(synth.TXN_FIELDS, row)) for row in mart["transactions"]], synth.TXN_FIELDS),
    }
    dataset = bigquery.Dataset(f"{project}.{config.BQ_DATASET}")
    dataset.location = config.BQ_LOCATION
    client.create_dataset(dataset, exists_ok=True)
    for name, (rows, fields) in tables.items():
        schema = _schema(rows, fields)
        if name == "transactions":
            schema = [field if field.name != "amount" else bigquery.SchemaField("amount", "FLOAT64") for field in schema]
        job = client.load_table_from_json(
            [{field: row[field] for field in fields} for row in rows],
            f"{project}.{config.BQ_DATASET}.{name}",
            job_config=bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_TRUNCATE"),
        )
        job.result()
        print(f"loaded {name}: {len(rows)} rows")


class _Ctx:
    def __init__(self, alert_id: str) -> None:
        self.state = {"alert_id": alert_id}


def _summaries(engine) -> dict[str, dict]:
    warehouse._ENGINE = engine
    out = {}
    for alert in ALERTS:
        for call in standby.run_ledger(alert, _Ctx(alert["id"])):
            out[f"{alert['id']} {call['name']} {call['args']}"] = call["result"]["summary"]
    return out


def parity() -> int:
    """Every Ledger tool on every file, on both engines. Returns the number of differences."""
    mirror = _summaries(warehouse._mirror())
    bigquery_side = _summaries(warehouse._BigQuery())
    warehouse._ENGINE = None
    differences = 0
    for key, expected in mirror.items():
        if bigquery_side.get(key) != expected:
            differences += 1
            print(f"DIFFERS {key}\n  mirror:   {expected}\n  bigquery: {bigquery_side.get(key)}")
    print(f"parity: {len(mirror) - differences}/{len(mirror)} tool results identical")
    return differences


if __name__ == "__main__":
    project = config.PROJECT or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        sys.exit("Set GOOGLE_CLOUD_PROJECT.")
    seed(bigquery.Client(project=project, location=config.BQ_LOCATION), project)
    sys.exit(1 if parity() else 0)
