"""Airflow DAGs for the shared data platform.

Airflow is used as the batch orchestrator. Transformations stay in dbt; Airflow
only coordinates extraction, quality gates, dbt runs and asset registration.
This separation keeps SQL testable and avoids putting business logic in DAGs.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# The image sets PYTHONPATH to the repository root. Local runs from the repo
# root also work because of this insert.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from platforms.data_platform.app.services.quality import run_quality  # noqa: E402

DATA_ROOT = REPO_ROOT / "data" / "raw"
DBT_DIR = Path(__file__).resolve().parents[1] / "dbt"

DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}


def _validate_tcm() -> None:
    path = DATA_ROOT / "tcm" / "documents.jsonl"
    report = run_quality_sync("tcm_documents", str(path))
    if report["failed_rows"]:
        raise ValueError(f"TCM quality gate failed: {report['failed_rows']} rows")
    print(json.dumps(report, ensure_ascii=False))


def _validate_retail() -> None:
    sales = run_quality_sync("retail_sales", str(DATA_ROOT / "retail" / "fact_sales.csv"))
    inventory = run_quality_sync("retail_inventory", str(DATA_ROOT / "retail" / "inventory_snapshot.csv"))
    if sales["failed_rows"] or inventory["failed_rows"]:
        raise ValueError("retail quality gate failed")
    print(json.dumps({"sales": sales, "inventory": inventory}, ensure_ascii=False))


def run_quality_sync(ruleset: str, uri: str) -> dict:
    """Airflow tasks are sync; the quality service exposes an async entry point."""
    import asyncio

    return asyncio.run(run_quality(ruleset, uri))


with DAG(
    dag_id="tcm_ingestion",
    description="Ingest and validate the TCM document corpus",
    start_date=datetime(2026, 1, 1),
    schedule="0 2 * * *",
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["tcm", "ingestion"],
) as tcm_dag:
    validate_tcm = PythonOperator(task_id="validate_tcm_documents", python_callable=_validate_tcm)
    dbt_tcm = BashOperator(
        task_id="build_tcm_metadata_models",
        bash_command=f"cd {DBT_DIR} && dbt run --select tag:tcm",
    )
    validate_tcm >> dbt_tcm


with DAG(
    dag_id="retail_ingestion",
    description="Load retail facts, validate quality and build replenishment features",
    start_date=datetime(2026, 1, 1),
    schedule="30 2 * * *",
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["retail", "features"],
) as retail_dag:
    validate_retail = PythonOperator(task_id="validate_retail_data", python_callable=_validate_retail)
    dbt_retail = BashOperator(
        task_id="build_retail_marts",
        bash_command=f"cd {DBT_DIR} && dbt run --select tag:retail",
    )
    test_retail = BashOperator(
        task_id="test_retail_marts",
        bash_command=f"cd {DBT_DIR} && dbt test --select tag:retail",
    )
    validate_retail >> dbt_retail >> test_retail
