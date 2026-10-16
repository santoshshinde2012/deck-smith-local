"""Optional: export the seed as Parquet to RustFS (S3) and register the tables in Unity Catalog OSS.

Needs the `core` compose profile running. Usage: python -m decksmith.seed.publish
The agent itself reads the DuckDB file; this step makes the same tables visible in the UC OSS
catalog (so lineage names and the uc_oss catalog adapter can be exercised) and in object storage.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import duckdb
import httpx

from decksmith.seed.generate import TABLES

UC_TYPES = {"INTEGER": "INT", "VARCHAR": "STRING", "DATE": "DATE", "DOUBLE": "DOUBLE"}


def export_parquet(db: Path, out_dir: Path) -> dict[str, list[tuple[str, str]]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    schemas: dict[str, list[tuple[str, str]]] = {}
    with duckdb.connect(str(db), read_only=True) as con:
        for table in TABLES:
            con.execute(f"COPY cs.{table} TO '{out_dir / table}.parquet' (FORMAT PARQUET)")
            schemas[table] = [(r[0], r[1]) for r in con.execute(f"DESCRIBE cs.{table}").fetchall()]
    return schemas


def upload_object_store(out_dir: Path, bucket: str) -> None:
    import boto3  # optional dependency: pip install 'deck-smith-local[publish]'

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("OBJECT_STORE_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.environ.get("OBJECT_STORE_ACCESS_KEY", "rustfsadmin"),
        aws_secret_access_key=os.environ.get("OBJECT_STORE_SECRET_KEY", "rustfsadmin"),
    )
    if bucket not in {b["Name"] for b in s3.list_buckets().get("Buckets", [])}:
        s3.create_bucket(Bucket=bucket)
    for file in sorted(out_dir.glob("*.parquet")):
        s3.upload_file(str(file), bucket, f"cs/{file.stem}/{file.name}")


def register_uc(uc_url: str, schemas: dict[str, list[tuple[str, str]]], location: str) -> None:
    api = httpx.Client(base_url=uc_url.rstrip("/") + "/api/2.1/unity-catalog", timeout=30)
    for path, body in (("/catalogs", {"name": "main"}), ("/schemas", {"name": "cs", "catalog_name": "main"})):
        response = api.post(path, json=body)
        if response.status_code not in (200, 201, 409) and "ALREADY_EXISTS" not in response.text:
            response.raise_for_status()
    for table, columns in schemas.items():
        api.delete(f"/tables/main.cs.{table}")
        cols = [
            {
                "name": n,
                "type_name": UC_TYPES.get(t, "STRING"),
                "type_text": UC_TYPES.get(t, "STRING").lower(),
                "type_json": json.dumps(
                    {"name": n, "type": UC_TYPES.get(t, "STRING").lower(), "nullable": True, "metadata": {}}
                ),
                "position": i,
                "nullable": True,
            }
            for i, (n, t) in enumerate(columns)
        ]
        api.post(
            "/tables",
            json={
                "name": table,
                "catalog_name": "main",
                "schema_name": "cs",
                "table_type": "EXTERNAL",
                "data_source_format": "PARQUET",
                "columns": cols,
                "storage_location": f"{location}/cs/{table}",
            },
        ).raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/lakehouse.duckdb"))
    parser.add_argument("--parquet-dir", type=Path, default=Path("data/parquet"))
    parser.add_argument("--uc-url", default=os.environ.get("DECKSMITH_UC_OSS_URL", "http://localhost:8081"))
    parser.add_argument("--bucket", default="lakehouse")
    parser.add_argument("--skip-upload", action="store_true")
    args = parser.parse_args()
    schemas = export_parquet(args.db, args.parquet_dir)
    if not args.skip_upload:
        upload_object_store(args.parquet_dir, args.bucket)
    register_uc(args.uc_url, schemas, f"s3://{args.bucket}")
    print(f"published {len(schemas)} tables to UC OSS main.cs")


if __name__ == "__main__":
    main()
