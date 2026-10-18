"""Streamlit workspace: choose a test user, request a deck, approve the outline, download the file.

Run: streamlit run src/decksmith/interfaces/ui.py  (talks to the API at DECKSMITH_API_URL)

Presentation rules live in ui_view.py. This module only draws them and calls the API.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

from decksmith.domain.errors import AuthenticationError
from decksmith.interfaces.ui_auth import identity_mode, request_headers
from decksmith.interfaces.ui_view import (
    APPROVE_LABEL,
    BRIEF_LABEL,
    DECISION_HELP,
    DEFAULT_DEMO_LABEL,
    DEFAULT_REQUEST,
    DOWNLOAD_LABEL,
    DRAFT_LABEL,
    EDIT_LABEL,
    FEEDBACK_HELP,
    FEEDBACK_LABEL,
    HOW_IT_WORKS,
    INTRO,
    PPTX_MEDIA,
    REJECT_LABEL,
    RESTART_LABEL,
    RETRY_DOWNLOAD_LABEL,
    Banner,
    FactView,
    IdentityView,
    SlidePreview,
    actor_changed,
    actor_key,
    banner_for,
    brief_problem,
    coerce_run,
    connection_problem,
    demo_labels,
    demo_user,
    download_name,
    fact_views,
    file_cache_key,
    file_caption,
    identity_view,
    markdown_text,
    masthead_html,
    outline_view,
    pending_copy,
    reference_label,
    show_brief_editor,
    show_deck,
    show_outline,
    show_restart,
    sidebar_html,
    slide_previews,
    stepper_html,
    steps_for,
    stylesheet,
    technical_detail,
    unreadable_response,
)

API = os.environ.get("DECKSMITH_API_URL", "http://localhost:8000")
_ICON = Path(__file__).with_name("mark.png")


def main() -> None:
    _configure_page()
    st.markdown(stylesheet(), unsafe_allow_html=True)
    try:
        forwarded = {str(key): str(value) for key, value in st.context.headers.items()}
        mode = identity_mode(os.environ, forwarded)
    except AuthenticationError as exc:
        _auth_problem(str(exc))
        return

    demo_label = _sidebar(mode, _current_status())
    identity = identity_view(mode, demo_label, forwarded)
    _sync_actor(actor_key(mode, demo_label))
    token = demo_user(demo_label).token if mode == "static" else ""
    with httpx.Client(base_url=API, headers=request_headers(mode, forwarded, token), timeout=120) as client:
        _workspace(client, identity)


def _configure_page() -> None:
    st.set_page_config(
        page_title="DeckSmith",
        page_icon=str(_ICON),
        layout="wide",
        initial_sidebar_state="auto",
        menu_items={"About": "DeckSmith prepares a PowerPoint deck from an outline you approve."},
    )


def _auth_problem(message: str) -> None:
    st.error(message)
    st.caption("Refresh the page after signing in again.")


def _sidebar(mode: str, status: str | None) -> str:
    with st.sidebar:
        st.markdown(sidebar_html(workspace=mode != "static"), unsafe_allow_html=True)
        label = ""
        if mode == "static":
            labels = demo_labels()
            label = str(
                st.selectbox(
                    "Act as",
                    labels,
                    index=labels.index(DEFAULT_DEMO_LABEL),
                    help="Each person sees only their own decks.",
                )
            )
        if show_restart(status) and st.button(RESTART_LABEL):
            _clear_run()
            st.rerun()
        return label


def _sync_actor(current: str) -> None:
    previous = st.session_state.get("actor")
    previous_text = previous if isinstance(previous, str) else None
    if actor_changed(previous_text, current):
        _clear_run()
    st.session_state["actor"] = current


def _current_status() -> str | None:
    run = st.session_state.get("run")
    if isinstance(run, dict) and run.get("status"):
        return str(run["status"])
    return None


def _workspace(client: httpx.Client, identity: IdentityView) -> None:
    st.markdown(masthead_html(identity), unsafe_allow_html=True)
    run = st.session_state.get("run")
    status = _current_status()
    st.markdown(stepper_html(steps_for(status)), unsafe_allow_html=True)
    if isinstance(run, dict):
        _show_banner(banner_for(run))
        detail = technical_detail(run)
        if detail:
            with st.expander("Details for support"):
                st.text(detail)
        reference = reference_label(run.get("run_id"))
        if reference:
            st.caption(reference)
    if show_brief_editor(status):
        _brief(client, status)
    elif isinstance(run, dict):
        _brief_summary()
    if isinstance(run, dict) and show_outline(status):
        _outline(client, run)
    elif isinstance(run, dict) and show_deck(status):
        _deck(client, run)


def _brief(client: httpx.Client, status: str | None) -> None:
    if status is None:
        st.caption(INTRO)
        columns = st.columns(len(HOW_IT_WORKS))
        for column, (title, body) in zip(columns, HOW_IT_WORKS, strict=True):
            with column.container(border=True):
                st.markdown(f"**{title}**")
                st.caption(body)
    prompt = st.text_area(BRIEF_LABEL, DEFAULT_REQUEST, height=120, key="brief")
    if st.button(DRAFT_LABEL, type="primary"):
        problem = brief_problem(str(prompt))
        if problem:
            st.warning(problem)
            return
        _store(client, "draft", "POST", "/v1/decks", {"request": str(prompt)})


def _brief_summary() -> None:
    brief = st.session_state.get("brief", DEFAULT_REQUEST)
    st.caption("Brief")
    st.markdown(markdown_text(str(brief)))


def _outline(client: httpx.Client, run: Mapping[str, object]) -> None:
    view = outline_view(run.get("outline"))
    if view is None:
        st.warning("The outline could not be shown. Start another request.")
        return
    count = f"{len(view.slides)} slides" if view.slides else "No slides yet"
    meta = " · ".join(part for part in (view.audience, view.period, count) if part)
    st.subheader(view.title)
    if meta:
        st.caption(meta)
    if not view.slides:
        st.info("This outline has no slides yet. Add a note and choose Edit, or start another request.")
    for slide in view.slides:
        with st.container(border=True):
            st.caption(f"{slide.number}  ·  {slide.layout}")
            st.markdown(f"**{markdown_text(slide.title)}**")
            if not slide.requests:
                st.caption("No data requested")
                continue
            st.caption("Data this slide needs")
            for request in slide.requests:
                template = f" · {request.template}" if request.template else ""
                st.markdown(f"- {markdown_text(request.label)}{markdown_text(template)}")
    st.subheader("Your decision")
    feedback = st.text_area(FEEDBACK_LABEL, key="feedback", height=80, help=FEEDBACK_HELP)
    st.caption(DECISION_HELP)
    approve, edit, reject = st.columns(3)
    run_id = str(run.get("run_id") or "")
    if approve.button(APPROVE_LABEL, type="primary", width="stretch"):
        _decide(client, run_id, "approve", str(feedback))
    if edit.button(EDIT_LABEL, width="stretch"):
        _decide(client, run_id, "edit", str(feedback))
    if reject.button(REJECT_LABEL, type="tertiary", width="stretch"):
        _decide(client, run_id, "reject", str(feedback))


def _deck(client: httpx.Client, run: Mapping[str, object]) -> None:
    _download(client, run)
    previews = slide_previews(run.get("spec"), run.get("facts"))
    facts = fact_views(run.get("facts"))
    if previews:
        st.subheader("Slides")
        st.caption("A reading view of the file. The download is the editable PowerPoint deck.")
        for slide in previews:
            _slide(slide)
    if facts:
        st.subheader("Facts and sources")
        st.caption("Every figure on the slides is one of these. The deck does not invent numbers.")
        _facts(facts)


def _download(client: httpx.Client, run: Mapping[str, object]) -> None:
    run_id = str(run.get("run_id") or "")
    key = file_cache_key(run_id)
    if key not in st.session_state:
        st.session_state[key] = _file(client, run_id)
    data = st.session_state.get(key)
    st.subheader("Download")
    if not isinstance(data, bytes) or not data:
        st.warning("The file is not ready to download yet.")
        if st.button(RETRY_DOWNLOAD_LABEL):
            st.session_state.pop(key, None)
            st.rerun()
        return
    st.download_button(
        DOWNLOAD_LABEL,
        data,
        file_name=download_name(run_id),
        mime=PPTX_MEDIA,
        type="primary",
    )
    st.caption(file_caption(len(data)))


def _slide(slide: SlidePreview) -> None:
    with st.container(border=True):
        st.caption(f"{slide.number}  ·  {slide.layout}")
        st.markdown(f"**{markdown_text(slide.title)}**")
        if slide.subtitle:
            st.caption(markdown_text(slide.subtitle))
        if slide.kpis:
            columns = st.columns(len(slide.kpis))
            for column, kpi in zip(columns, slide.kpis, strict=True):
                column.metric(kpi.label, kpi.display)
        if slide.body == "quote" and slide.quote:
            st.markdown(f"> {markdown_text(slide.quote)}")
            if slide.attribution:
                st.caption(markdown_text(slide.attribution))
        for line in slide.lines:
            st.markdown(f"- {markdown_text(line)}")
        if slide.points:
            if slide.chart_caption:
                st.caption(slide.chart_caption)
            _chart(slide)
            if slide.summary:
                st.caption(slide.summary)
        if slide.sources:
            st.caption("Sources: " + ", ".join(slide.sources))


def _chart(slide: SlidePreview) -> None:
    data = {"category": [point.label for point in slide.points], "value": [point.magnitude for point in slide.points]}
    if slide.chart_kind == "line":
        st.line_chart(data, x="category", y="value", height=240)
        return
    st.bar_chart(data, x="category", y="value", height=240, horizontal=slide.chart_kind == "bar")


def _facts(facts: tuple[FactView, ...]) -> None:
    columns = st.columns(2 if len(facts) > 1 else 1)
    for index, fact in enumerate(facts):
        with columns[index % len(columns)].container(border=True):
            st.markdown(f"**{markdown_text(fact.label)}**")
            kind = f"{fact.fact_id} · {fact.kind}"
            template = f" · {fact.template}" if fact.template else ""
            st.caption(kind + template)
            if fact.kind == "Figure":
                st.metric("Value", fact.display)
            elif fact.summary:
                st.caption(fact.summary)
            if fact.tables:
                st.caption("Tables: " + ", ".join(fact.tables))
            if fact.queried_at:
                st.caption(f"Queried {fact.queried_at}")
    queries = [fact for fact in facts if fact.query]
    if not queries:
        return
    with st.expander("Approved queries"):
        for fact in queries:
            st.markdown(f"**{markdown_text(fact.label)}**")
            if fact.parameters:
                st.caption(fact.parameters)
            st.code(fact.query, language="sql")


def _decide(client: httpx.Client, run_id: str, action: str, feedback: str) -> None:
    _store(client, action, "POST", f"/v1/decks/{run_id}/decision", {"action": action, "feedback": feedback})


def _store(client: httpx.Client, action: str, method: str, path: str, payload: dict[str, object]) -> None:
    with st.spinner(pending_copy(action)):
        st.session_state["run"] = _call(client, method, path, payload)
    st.rerun()


def _call(client: httpx.Client, method: str, path: str, payload: dict[str, object]) -> dict[str, Any]:
    try:
        response = client.request(method, path, json=payload)
    except httpx.HTTPError:
        return connection_problem()
    try:
        body: object = response.json()
    except ValueError:
        return unreadable_response()
    return coerce_run(response.status_code, body)


def _file(client: httpx.Client, run_id: str) -> bytes | None:
    try:
        response = client.get(f"/v1/decks/{run_id}/file")
    except httpx.HTTPError:
        return None
    if response.status_code != 200 or not response.content:
        return None
    return response.content


def _show_banner(banner: Banner | None) -> None:
    if banner is None:
        return
    text = f"{banner.title}. {banner.body}"
    {"waiting": st.info, "progress": st.info, "success": st.success, "stopped": st.warning, "error": st.error}.get(
        banner.tone, st.info
    )(text)


def _clear_run() -> None:
    st.session_state.pop("run", None)
    st.session_state.pop("feedback", None)
    for key in [name for name in st.session_state if str(name).startswith("pptx:")]:
        del st.session_state[key]


main()
