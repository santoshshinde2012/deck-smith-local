# Error taxonomy

Every error extends `DeckSmithError` (`src/decksmith/domain/errors.py`) and carries:

- a stable `code`;
- a `category`;
- an HTTP `status_code`;
- a `retryable` flag.

The API returns the same JSON shape for all of them:

```json
{ "error": "access_denied", "category": "policy", "retryable": false, "detail": "..." }
```

| Code | Class | Category | HTTP | Retryable | Raised when |
| --- | --- | --- | --- | --- | --- |
| `internal_error` | `DeckSmithError` | internal | 500 | no | Fallback for an unclassified failure |
| `authentication_failed` | `AuthenticationError` | auth | 401 | no | The token is missing, unknown or invalid |
| `access_denied` | `AccessDenied` | policy | 403 | no | The catalog or warehouse refuses a table to this user |
| `run_not_found` | `RunNotFound` | client | 404 | no | The run doesn't exist or belongs to someone else |
| `invalid_parameters` | `InvalidParameters` | client | 422 | no | A template parameter fails its type or pattern, or the request is too long |
| `unknown_template` | `UnknownTemplate` | client | 422 | no | The planner named a template that doesn't exist |
| `no_data` | `NoDataAvailable` | data | 409 | no | No requested data is visible to the user |
| `guardrail_violation` | `GuardrailViolation` | policy | 446 | no | LLM output contains a bare number (Portkey's deny status) |
| `upstream_unavailable` | `UpstreamError` | upstream | 503 | yes | The warehouse, gateway or catalog failed or timed out |
| `configuration_error` | `ConfigurationError` | internal | 500 | no | Settings select adapters that can't work together |

There are three rules:

- Adapters translate SDK and HTTP errors into these classes. Application code never catches SDK exceptions.
- Interfaces map errors only from these attributes, so adding an error needs no interface change (open/closed).
- Logs record the `code`, never the token, the prompt or row data. A unit test fails if a code is missing from this table.
