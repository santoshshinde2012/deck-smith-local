from copy import deepcopy

from decksmith.bootstrap import Container
from decksmith.domain.principal import Principal
from decksmith.evaluation.scorers import fact_integrity, sources_cited


def test_scorers_reject_misaligned_charts_and_missing_appendix(container: Container, bob: Principal) -> None:
    run = container.service.start("Build the Q3 2026 retention review", bob)
    outputs = container.service.decide(run.run_id, "approve", bob).model_dump(mode="json")
    assert fact_integrity(outputs, {}) and sources_cited(outputs, {})

    mismatched = deepcopy(outputs)
    chart = mismatched["spec"]["slides"][2]["chart"]
    chart["series"].append({"name": "Segments", "fact_id": "f5"})
    assert not fact_integrity(mismatched, {})

    missing = deepcopy(outputs)
    missing["spec"]["slides"] = missing["spec"]["slides"][:-1]
    assert not fact_integrity(missing, {})
    assert not sources_cited(missing, {})

    altered = deepcopy(outputs)
    altered["spec"]["slides"][1]["layout"] = "bullets"
    assert not fact_integrity(altered, {})

    invalid = {**outputs, "spec": {}}
    assert not fact_integrity(invalid, {})
