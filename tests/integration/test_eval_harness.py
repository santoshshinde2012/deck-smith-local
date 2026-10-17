from collections.abc import Callable

import pytest

from decksmith.bootstrap import Container
from decksmith.evaluation.harness import load_golden, make_predict, run_plain

pytestmark = pytest.mark.integration


def test_golden_set_deterministic_gates(make_container: Callable[..., Container]) -> None:
    rows = load_golden()
    assert len(rows) == 10
    result = run_plain(rows, make_predict(make_container().service))
    failing = [r for r in result["rows"] if not all(v for k, v in r.items() if k != "id")]
    assert not failing, failing
    assert all(v == 1.0 for v in result["summary"].values())
