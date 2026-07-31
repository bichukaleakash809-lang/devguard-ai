"""
Train the ML terminus of the hero loop (05_DATAHUB_MASTER §3).

§3 requires "a REAL trivial model (e.g. scikit-learn logistic regression) trained
on the feature table, registered as an `mlModel` entity with lineage to its
feature source", and is explicit about why: "Makes the Production ML Agents claim
factual, not aspirational. A 20-line model is still a real model."

So this is deliberately small. It is not trying to be good at predicting churn —
it is trying to be REAL: it reads the actual feature table produced by dbt from
the actual substrate Postgres, fits an actual estimator, and writes an actual
artifact. When the hero-loop rename breaks `user_id`, the feature table fails to
build and THIS script fails with a real traceback. That failure is the runtime
evidence that terminates the blast radius at a registered ML model.

    python substrate/ml/train_churn_model.py
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
from datetime import datetime, timezone

FEATURE_TABLE = "analytics_marts.user_order_features"
ARTIFACT_DIR = pathlib.Path("substrate/ml/artifacts")

# The feature columns the model consumes. `user_id` is listed because its
# presence is what the hero loop breaks — the model does not train on it, but it
# is required to join and to identify rows.
ID_COLUMN = "user_id"
FEATURE_COLUMNS = ["order_count", "lifetime_value_cents", "avg_order_cents", "refund_count"]
LABEL_EXPR = "refund_count > 0"


def _dsn() -> str:
    return (
        f"host={os.getenv('SUBSTRATE_PG_HOST', 'localhost')} "
        f"port={os.getenv('SUBSTRATE_PG_PORT', '5433')} "
        f"dbname={os.getenv('SUBSTRATE_PG_DB', 'devguard')} "
        f"user={os.getenv('SUBSTRATE_PG_USER', 'devguard')} "
        f"password={os.getenv('SUBSTRATE_PG_PASSWORD', 'devguard')}"
    )


def main() -> int:
    import psycopg2
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split

    conn = psycopg2.connect(_dsn())
    try:
        with conn.cursor() as cur:
            # Selected BY NAME on purpose. If user_id has been renamed upstream,
            # this raises psycopg2.errors.UndefinedColumn — a real failure with a
            # real message, not a simulated one.
            cols = ", ".join([ID_COLUMN] + FEATURE_COLUMNS)
            cur.execute(f"SELECT {cols}, ({LABEL_EXPR}) AS label FROM {FEATURE_TABLE}")
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print(f"FAIL: {FEATURE_TABLE} returned no rows", file=sys.stderr)
        return 1

    X = [[float(r[i]) for i in range(1, 1 + len(FEATURE_COLUMNS))] for r in rows]
    y = [1 if r[-1] else 0 for r in rows]

    if len(set(y)) < 2:
        print("FAIL: label column has a single class; cannot fit", file=sys.stderr)
        return 1

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    model = LogisticRegression(max_iter=1000).fit(X_tr, y_tr)
    accuracy = float(model.score(X_te, y_te))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = {
        # LAW 5: these numbers come from the machine. Nothing here is typed by hand.
        "model_name": "devguard_churn_risk",
        "framework": "scikit-learn",
        "estimator": "LogisticRegression",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "feature_table": FEATURE_TABLE,
        "id_column": ID_COLUMN,
        "feature_columns": FEATURE_COLUMNS,
        "label": LABEL_EXPR,
        "rows_total": len(rows),
        "rows_train": len(X_tr),
        "rows_test": len(X_te),
        "test_accuracy": accuracy,
    }
    (ARTIFACT_DIR / "model_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    print(f"trained on {len(rows)} rows from {FEATURE_TABLE}")
    print(f"test accuracy: {accuracy:.4f}")
    print(f"metadata: {ARTIFACT_DIR / 'model_metadata.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
