from types import MappingProxyType

import pytest

from decksmith.domain.errors import AuthenticationError
from decksmith.interfaces.ui_auth import identity_mode, request_headers


def test_demo_identity_is_available_only_locally() -> None:
    assert identity_mode({}, {}) == "static"
    assert request_headers("static", {}, "bob-token") == {"Authorization": "Bearer bob-token"}
    with pytest.raises(AuthenticationError):
        identity_mode({"DECKSMITH_ENV": "production"}, {})
    assert identity_mode({"DECKSMITH_IDENTITY": "databricks_apps"}, {}) == "databricks_apps"


def test_databricks_hosting_disables_demo_users_even_without_a_forwarded_token() -> None:
    assert identity_mode({"DATABRICKS_APP_NAME": "decksmith"}, {}) == "databricks_apps"
    with pytest.raises(AuthenticationError):
        request_headers("databricks_apps", {}, "bob-token")


def test_forwarded_identity_headers_are_allowlisted_and_refreshed() -> None:
    forwarded = MappingProxyType(
        {
            "X-Forwarded-Access-Token": "dummy-first-token",
            "X-Forwarded-Email": "bob@example.com",
            "X-Forwarded-Preferred-Username": "Bob",
            "Authorization": "Bearer unrelated-app-token",
            "Cookie": "unrelated-session-cookie",
        }
    )
    assert identity_mode({}, forwarded) == "databricks_apps"
    assert request_headers("databricks_apps", forwarded) == {
        "x-forwarded-access-token": "dummy-first-token",
        "x-forwarded-email": "bob@example.com",
        "x-forwarded-preferred-username": "Bob",
    }
    refreshed = {**forwarded, "X-Forwarded-Access-Token": "dummy-refreshed-token"}
    assert request_headers("databricks_apps", refreshed)["x-forwarded-access-token"] == "dummy-refreshed-token"
    assert forwarded["X-Forwarded-Access-Token"] == "dummy-first-token"


@pytest.mark.parametrize("forwarded", [{"x-forwarded-email": "bob"}, {"x-forwarded-access-token": "dummy"}])
def test_incomplete_forwarded_identity_is_refused(forwarded: dict[str, str]) -> None:
    with pytest.raises(AuthenticationError):
        request_headers("databricks_apps", forwarded)


def test_jwt_ui_uses_the_http_authorization_header() -> None:
    assert request_headers("jwt", {"authorization": "Bearer dummy-jwt"}) == {"Authorization": "Bearer dummy-jwt"}
    with pytest.raises(AuthenticationError):
        request_headers("jwt", {})
