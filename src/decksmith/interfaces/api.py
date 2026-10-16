"""FastAPI server: the local stand-in for the Databricks App front door."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from decksmith.application.service import Action, RunView
from decksmith.bootstrap import Container, build_container
from decksmith.domain.errors import (
    AuthenticationError,
    DeckSmithError,
    InvalidParameters,
    RunNotFound,
    UnknownTemplate,
)
from decksmith.domain.principal import Principal

PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class StartRequest(BaseModel):
    request: str = Field(min_length=3, max_length=2000)


class DecisionRequest(BaseModel):
    action: Action
    feedback: str = Field(default="", max_length=2000)


def current_user(request: Request) -> Principal:
    """Resolve the caller through the configured IdentityProvider (OBO headers on Databricks)."""
    try:
        return request.app.state.container.identity.authenticate(dict(request.headers))  # type: ignore[no-any-return]
    except AuthenticationError as exc:
        raise HTTPException(401, str(exc)) from exc


User = Annotated[Principal, Depends(current_user)]


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(title="DeckSmith (local)", version="0.1.0")
    app.state.container = container or build_container()

    @app.exception_handler(DeckSmithError)
    async def _errors(_: Request, exc: DeckSmithError) -> JSONResponse:
        code = (
            404
            if isinstance(exc, RunNotFound)
            else 422
            if isinstance(exc, InvalidParameters | UnknownTemplate)
            else getattr(exc, "status_code", 500)
        )
        return JSONResponse({"error": type(exc).__name__, "detail": str(exc)}, status_code=code)

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        s = app.state.container.settings
        return {
            "ok": True,
            "adapters": {
                "llm": s.llm,
                "data_source": s.data_source,
                "catalog": s.catalog,
                "state_store": s.state_store,
                "tracer": s.tracer,
                "identity": s.identity,
            },
        }

    @app.post("/v1/decks", response_model=RunView)
    def start(body: StartRequest, user: User) -> RunView:
        return app.state.container.service.start(body.request, user)  # type: ignore[no-any-return]

    @app.post("/v1/decks/{run_id}/decision", response_model=RunView)
    def decide(run_id: str, body: DecisionRequest, user: User) -> RunView:
        return app.state.container.service.decide(run_id, body.action, user, body.feedback)  # type: ignore[no-any-return]

    @app.get("/v1/decks/{run_id}", response_model=RunView)
    def get(run_id: str, user: User) -> RunView:
        return app.state.container.service.get(run_id, user)  # type: ignore[no-any-return]

    @app.get("/v1/decks/{run_id}/file")
    def download(run_id: str, user: User) -> FileResponse:
        view: RunView = app.state.container.service.get(run_id, user)
        if not view.artifact:
            raise HTTPException(409, f"run is {view.status}; no deck yet")
        path = Path(view.artifact["path"])
        return FileResponse(path, media_type=PPTX, filename=f"decksmith-{run_id[:8]}.pptx")

    @app.post("/responses")
    def responses(body: dict[str, Any], request: Request) -> dict[str, Any]:
        from mlflow.types.responses import ResponsesAgentRequest

        from decksmith.interfaces.responses_agent import DeckSmithResponsesAgent

        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        body.setdefault("custom_inputs", {}).setdefault("access_token", token)
        agent = DeckSmithResponsesAgent(app.state.container.service, app.state.container.identity)
        try:
            return agent.predict(ResponsesAgentRequest(**body)).model_dump(mode="json")  # type: ignore[no-any-return]
        except AuthenticationError as exc:
            raise HTTPException(401, str(exc)) from exc

    return app


def app() -> FastAPI:
    """Factory for `uvicorn --factory decksmith.interfaces.api:app`."""
    return create_app()
