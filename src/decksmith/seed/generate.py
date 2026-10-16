"""Generate the local lakehouse: subscriptions, monthly aggregates, user access, per-user views.

Usage: python -m decksmith.seed.generate [--out data/lakehouse.duckdb]
"""

from __future__ import annotations

import argparse
import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa

SEED = 42
N_SUBSCRIPTIONS = 8000
MONTHS = [date(2025 + (10 + i - 1) // 12, (10 + i - 1) % 12 + 1, 1) for i in range(12)]  # 2025-10 .. 2026-09
REGIONS = ("EU-West", "EU-Central", "EU-North", "UK")
SEGMENTS = ("SMB", "Mid-market", "Enterprise")
PLANS = {"Pro": 20.0, "Pro+": 60.0, "Ultra": 200.0}  # illustrative monthly list prices (synthetic)
SEGMENT_SEATS = {"SMB": (1, 5), "Mid-market": (5, 40), "Enterprise": (40, 250)}
MONTHLY_CHURN = {"SMB": 0.035, "Mid-market": 0.018, "Enterprise": 0.008}
REGION_CHURN_FACTOR = {"EU-West": 0.9, "EU-Central": 1.0, "EU-North": 0.8, "UK": 1.2}
USER_REGIONS = {"alice": ("EU-West",), "bob": REGIONS, "carol": ()}  # carol: no access at all
SIM_MONTHS = [*MONTHS, date(2026, 10, 1)]  # one extra month so September's churn is observable
TABLES = ("churn_monthly", "revenue_monthly", "subscriptions")


@dataclass
class Subscription:
    sub_id: int
    region: str
    segment: str
    plan: str
    seats: int
    start: date
    end: date | None  # first month NOT active

    def active(self, month: date) -> bool:
        return self.start <= month and (self.end is None or month < self.end)

    def mrr(self, month: date) -> float:
        growth = 1.0 + 0.01 * max(0, (month.year - self.start.year) * 12 + month.month - self.start.month)
        return round(PLANS[self.plan] * self.seats * growth, 2)


def generate(seed: int = SEED, n: int = N_SUBSCRIPTIONS) -> list[Subscription]:
    rng = random.Random(seed)
    subs: list[Subscription] = []
    for i in range(1, n + 1):
        segment = rng.choices(SEGMENTS, weights=(0.6, 0.3, 0.1))[0]
        region = rng.choices(REGIONS, weights=(0.35, 0.3, 0.15, 0.2))[0]
        plan = rng.choices(tuple(PLANS), weights=(0.55, 0.35, 0.10))[0]
        start = MONTHS[0] if rng.random() < 0.7 else rng.choice(MONTHS[1:])
        end = None
        p = MONTHLY_CHURN[segment] * REGION_CHURN_FACTOR[region]
        for month in SIM_MONTHS:
            if month > start and rng.random() < p:
                end = month
                break
        subs.append(Subscription(i, region, segment, plan, rng.randint(*SEGMENT_SEATS[segment]), start, end))
    return subs


def build(out: Path, seed: int = SEED) -> Path:
    subs = generate(seed)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    churn, revenue = [], []
    for month, nxt in zip(MONTHS, SIM_MONTHS[1:], strict=True):
        groups: dict[tuple[str, str], list[Subscription]] = {(r, g): [] for r in REGIONS for g in SEGMENTS}
        for s in subs:
            if s.active(month):
                groups[(s.region, s.segment)].append(s)
        for (region, segment), cohort in groups.items():
            retained = [s for s in cohort if s.active(nxt)]
            churn.append((month, region, segment, len(cohort), len(cohort) - len(retained)))
            revenue.append(
                (
                    month,
                    region,
                    segment,
                    round(sum(s.mrr(month) for s in cohort), 2),
                    round(sum(s.mrr(nxt) for s in retained), 2),
                )
            )
    with duckdb.connect(str(out)) as con:
        con.execute("CREATE SCHEMA cs")
        con.execute(
            "CREATE TABLE cs.subscriptions (sub_id INTEGER, region VARCHAR, segment VARCHAR, plan VARCHAR,"
            " seats INTEGER, start_month DATE, end_month DATE)"
        )
        _insert(
            con, "cs.subscriptions", [(s.sub_id, s.region, s.segment, s.plan, s.seats, s.start, s.end) for s in subs]
        )
        con.execute(
            "CREATE TABLE cs.churn_monthly (month DATE, region VARCHAR, segment VARCHAR,"
            " active_start INTEGER, churned INTEGER)"
        )
        _insert(con, "cs.churn_monthly", churn)
        con.execute(
            "CREATE TABLE cs.revenue_monthly (month DATE, region VARCHAR, segment VARCHAR,"
            " mrr_start DOUBLE, mrr_retained DOUBLE)"
        )
        _insert(con, "cs.revenue_monthly", revenue)
        con.execute("CREATE TABLE cs.user_region_access (user_id VARCHAR, region VARCHAR)")
        con.executemany(
            "INSERT INTO cs.user_region_access VALUES (?, ?)",
            [(u, r) for u, regions in USER_REGIONS.items() for r in regions],
        )
        # Row-filter emulation: one view per (user, table). No view => no access (AccessDenied).
        for user, regions in USER_REGIONS.items():
            if not regions:
                continue
            for table in TABLES:
                con.execute(
                    f"CREATE VIEW cs.v_{table}__{user} AS SELECT t.* FROM cs.{table} t "
                    f"WHERE t.region IN (SELECT region FROM cs.user_region_access WHERE user_id = '{user}')"
                )
    return out


def _insert(con: duckdb.DuckDBPyConnection, table: str, rows: Sequence[tuple[object, ...]]) -> None:
    """Bulk insert through Arrow (row-by-row executemany is slow in DuckDB)."""
    columns = list(zip(*rows, strict=True))
    batch = pa.table({f"c{i}": list(col) for i, col in enumerate(columns)})  # noqa: F841 (read by DuckDB)
    con.execute(f"INSERT INTO {table} SELECT * FROM batch")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/lakehouse.duckdb"))
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    path = build(args.out, args.seed)
    print(f"seeded {path} (seed {args.seed}, {N_SUBSCRIPTIONS} synthetic subscriptions)")


if __name__ == "__main__":
    main()
