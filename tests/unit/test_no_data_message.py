import pytest

from decksmith.application.nodes import _no_data_message

BOTH = "Some requested data is not visible to you, and some requested queries returned no data"


@pytest.mark.parametrize(
    ("denied", "empty", "partial", "start", "advice"),
    [
        (True, False, False, "None of the requested data is visible to you", ""),
        (False, True, False, "None of the requested queries returned data for you", "row-level policies"),
        (True, True, False, BOTH, "approve a new outline"),
        (True, False, True, "Some requested data is not visible to you, so", "approve a new outline"),
        (False, True, True, "Some requested queries returned no data, so", "approve a new outline"),
        (True, True, True, BOTH, "approve a new outline"),
        (False, False, False, "The approved outline requests no data", ""),
    ],
)
def test_refusal_names_only_the_causes_that_occurred(
    denied: bool, empty: bool, partial: bool, start: str, advice: str
) -> None:
    message = _no_data_message(denied=denied, empty=empty, partial=partial)
    assert message.startswith(start)
    assert advice in message
