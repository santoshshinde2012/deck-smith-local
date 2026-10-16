"""Run the golden set end to end (auto-approving outlines) and score it.

python -m decksmith.evaluation.harness [--mlflow]   # plain run by default; --mlflow logs to MLflow 3
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from decksmith.application.service import DeckService
from decksmith.domain.principal import Principal
from decksmith.evaluation.scorers import SCORERS

GOLDEN = Path(__file__).resolve().parents[3] / "evals" / "golden" / "golden.jsonl"


def load_golden(path: Path = GOLDEN) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def make_predict(service: DeckService) -> Callable[..., dict[str, Any]]:
    def predict(request: str, user: str, action: str = "approve", feedback: str = "") -> dict[str, Any]:
        principal = Principal(user_id=user, token=f"{user}-token")
        view = service.start(request, principal)
        if view.status == "awaiting_approval":
            view = service.decide(view.run_id, action, principal, feedback)  # type: ignore[arg-type]
        return view.model_dump(mode="json")

    return predict


def run_plain(rows: list[dict[str, Any]], predict: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    results = []
    for row in rows:
        outputs = predict(**row["inputs"])
        scores = {s.__name__: s(outputs, row["expectations"]) for s in SCORERS}
        results.append({"id": row["id"], **scores})
    summary = {s.__name__: sum(r[s.__name__] for r in results) / len(results) for s in SCORERS}
    return {"rows": results, "summary": summary}


def run_mlflow(rows: list[dict[str, Any]], predict: Callable[..., dict[str, Any]]) -> Any:
    import mlflow
    from mlflow.genai.scorers import scorer

    wrapped = [scorer(name=s.__name__)(lambda outputs, expectations, _s=s: _s(outputs, expectations)) for s in SCORERS]
    return mlflow.genai.evaluate(
        data=[{"inputs": r["inputs"], "expectations": r["expectations"]} for r in rows],
        predict_fn=predict,
        scorers=wrapped,
    )


def main() -> None:
    from decksmith.bootstrap import build_container

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mlflow", action="store_true")
    args = parser.parse_args()
    container = build_container()
    predict = make_predict(container.service)
    rows = load_golden()
    if args.mlflow:
        print(run_mlflow(rows, predict).metrics)
    else:
        print(json.dumps(run_plain(rows, predict)["summary"], indent=2))


if __name__ == "__main__":
    main()
