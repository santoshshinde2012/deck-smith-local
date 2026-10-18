"""Select UI credentials without putting tokens into Streamlit session state or model requests."""

from collections.abc import Mapping

from decksmith.domain.errors import AuthenticationError

FORWARDED_HEADERS = ("x-forwarded-access-token", "x-forwarded-email", "x-forwarded-preferred-username")


def identity_mode(environ: Mapping[str, str], headers: Mapping[str, str]) -> str:
    """Databricks hosting or OBO headers always disable local demo impersonation."""
    lowered = {k.lower(): v for k, v in headers.items()}
    if environ.get("DATABRICKS_APP_NAME") or lowered.get("x-forwarded-access-token"):
        return "databricks_apps"
    mode = environ.get("DECKSMITH_IDENTITY", "static")
    if mode == "static" and environ.get("DECKSMITH_ENV", "local") != "local":
        raise AuthenticationError("Demo users are available only in the local environment")
    return mode


def request_headers(mode: str, forwarded: Mapping[str, str], demo_token: str = "") -> dict[str, str]:
    lowered = {k.lower(): v for k, v in forwarded.items()}
    if mode == "databricks_apps":
        headers = {key: lowered[key] for key in FORWARDED_HEADERS if lowered.get(key)}
        if not headers.get("x-forwarded-access-token") or not (
            headers.get("x-forwarded-email") or headers.get("x-forwarded-preferred-username")
        ):
            raise AuthenticationError("Databricks did not forward your user authorization. Sign in again.")
        return headers
    if mode == "static" and demo_token:
        return {"Authorization": f"Bearer {demo_token}"}
    if mode == "jwt" and lowered.get("authorization"):
        return {"Authorization": lowered["authorization"]}
    raise AuthenticationError("No user authorization was provided")
