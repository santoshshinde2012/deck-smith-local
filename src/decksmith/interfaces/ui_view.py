"""Presentation models for the Streamlit workspace.

The page in ``ui.py`` renders these values. Nothing here imports Streamlit or calls the agent,
so the copy, structure and theme rules can be tested on their own.
"""

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from decksmith.domain.deckspec import FACT_PATTERN
from decksmith.domain.facts import FactFormat, format_value

DEMO_USERS: tuple[tuple[str, str, str, str], ...] = (
    ("alice (her region only)", "alice-token", "Alice", "Her region only"),
    ("bob (all regions)", "bob-token", "Bob", "All regions"),
    ("carol (no access)", "carol-token", "Carol", "No data access"),
)
DEFAULT_DEMO_LABEL = "bob (all regions)"
DEFAULT_REQUEST = "Build the quarterly customer retention review for the exec team"

DRAFT_LABEL = "Draft outline"
APPROVE_LABEL = "Approve"
EDIT_LABEL = "Edit"
REJECT_LABEL = "Reject"
DOWNLOAD_LABEL = "Download deck"
RESTART_LABEL = "Start another deck"
RETRY_DOWNLOAD_LABEL = "Try the download again"
BRIEF_LABEL = "What deck do you need?"
FEEDBACK_LABEL = "What should change?"
FEEDBACK_HELP = "Used only when you choose Edit."
DECISION_HELP = (
    "Approve reads the data and builds the deck. Edit sends your notes back into the outline. Reject stops here."
)
SIDEBAR_NOTE = "Local test identities. The deck runs as the person you choose."
WORKSPACE_NOTE = "Signed in through the workspace. This page does not switch users."
TAGLINE = "Request an outline, approve it, then download the deck."
INTRO = "Describe the audience, the period and the question. You will see the outline before any data is read."
HOW_IT_WORKS: tuple[tuple[str, str], ...] = (
    ("Request", "Write the brief in plain language."),
    ("Outline", "Review the slides and the data each one will use."),
    ("Deck", "Approve to build a PowerPoint file you can download."),
)
PPTX_MEDIA = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

StepState = Literal["complete", "current", "upcoming"]
BannerTone = Literal["neutral", "waiting", "progress", "success", "stopped", "error"]
Phase = Literal["request", "review", "ready", "stopped"]
FactKindLabel = Literal["Figure", "Series"]
ChartKind = Literal["", "line", "bar", "column"]
BodyKind = Literal["none", "list", "quote"]

_FORMATS: dict[str, FactFormat] = {
    "pct1": "pct1",
    "int": "int",
    "currency0": "currency0",
    "decimal2": "decimal2",
}
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_YEAR_MONTH = re.compile(r"^(\d{4})-(\d{2})(?:-\d{2})?$")
_PERIOD = re.compile(r"^(\d{4})-Q([1-4])$")
_LAYOUTS = {
    "title": "Title",
    "section": "Section",
    "agenda": "Agenda",
    "kpi": "Headline figures",
    "chart": "Chart",
    "bullets": "Key points",
    "two_content": "Two columns",
    "comparison": "Comparison",
    "timeline": "Timeline",
    "quote": "Quotation",
    "table": "Table",
    "summary": "Summary",
    "appendix_sources": "Sources",
}
_AUDIENCE = {"exec": "Executive team", "team": "Team", "board": "Board"}
_MARKDOWN_SPECIAL = set("\\`*_{}[]()#+-.!<>|")
_ERROR_COPY = {
    "authentication_failed": "Sign in again. This page could not confirm who you are.",
    "access_denied": "You do not have access to that data.",
    "run_not_found": "That deck is not available. It may belong to someone else, or it is no longer here.",
    "invalid_parameters": "That request could not be accepted. Try a shorter, clearer brief.",
    "unknown_template": "The plan referred to data this service does not recognise. Edit the outline or start again.",
    "no_data": "No data was available for this request, so no deck was produced.",
    "guardrail_violation": "The draft did not pass review. Start a new request.",
    "upstream_unavailable": "A service this page depends on is unavailable. Wait a moment and try again.",
    "configuration_error": (
        "The deck service is not set up correctly. The person who runs it needs to check the configuration."
    ),
    "internal_error": "Something went wrong while building the deck. Try again.",
}
_PROGRESS = {
    "intake": "Reading the brief.",
    "planning": "Updating the outline.",
    "fetching": "Reading the approved data.",
    "writing": "Writing the slides from the approved facts.",
    "rendering": "Preparing the PowerPoint file.",
}
_STEP_LABELS = ("Request", "Outline", "Build", "Deck")


@dataclass(frozen=True)
class DemoUser:
    label: str
    token: str
    name: str
    scope: str


@dataclass(frozen=True)
class IdentityView:
    name: str
    scope: str
    mode: str


@dataclass(frozen=True)
class Step:
    label: str
    state: StepState


@dataclass(frozen=True)
class Banner:
    tone: BannerTone
    title: str
    body: str


@dataclass(frozen=True)
class RequestChip:
    label: str
    template: str


@dataclass(frozen=True)
class OutlineSlideView:
    number: str
    layout: str
    title: str
    requests: tuple[RequestChip, ...]


@dataclass(frozen=True)
class OutlineView:
    title: str
    audience: str
    period: str
    slides: tuple[OutlineSlideView, ...]


@dataclass(frozen=True)
class SeriesPoint:
    label: str
    display: str
    magnitude: float


@dataclass(frozen=True)
class FactView:
    fact_id: str
    label: str
    kind: FactKindLabel
    display: str
    template: str
    tables: tuple[str, ...]
    queried_at: str
    points: tuple[SeriesPoint, ...]
    summary: str
    query: str
    parameters: str


@dataclass(frozen=True)
class KpiView:
    label: str
    display: str


@dataclass(frozen=True)
class SlidePreview:
    number: str
    layout: str
    title: str
    subtitle: str
    body: BodyKind
    lines: tuple[str, ...]
    quote: str
    attribution: str
    kpis: tuple[KpiView, ...]
    chart_kind: ChartKind
    chart_caption: str
    points: tuple[SeriesPoint, ...]
    summary: str
    sources: tuple[str, ...]


def demo_users() -> tuple[DemoUser, ...]:
    return tuple(DemoUser(*row) for row in DEMO_USERS)


def demo_user(label: str) -> DemoUser:
    for user in demo_users():
        if user.label == label:
            return user
    raise KeyError(label)


def demo_labels() -> tuple[str, ...]:
    return tuple(user.label for user in demo_users())


def identity_view(mode: str, demo_label: str, forwarded: Mapping[str, str]) -> IdentityView:
    """Who the page should say is signed in. Tokens never appear here."""
    if mode == "static":
        try:
            user = demo_user(demo_label)
        except KeyError:
            return IdentityView("Signed in", "Test user", "Test user")
        return IdentityView(user.name, user.scope, "Test user")
    lowered = {key.lower(): value for key, value in forwarded.items()}
    if mode == "databricks_apps":
        name = lowered.get("x-forwarded-preferred-username") or lowered.get("x-forwarded-email") or "Signed in"
        return IdentityView(name, "Workspace account", "Workspace")
    return IdentityView("Signed in", "Authorized session", "Signed in")


def actor_key(mode: str, demo_label: str) -> str:
    return f"{mode}:{demo_label}" if mode == "static" else mode


def actor_changed(previous: str | None, current: str) -> bool:
    return previous is not None and previous != current


def phase(status: str | None) -> Phase:
    if status == "awaiting_approval":
        return "review"
    if status == "done":
        return "ready"
    if status in {"rejected", "no_data", "failed", "error"}:
        return "stopped"
    if status in {"intake", "planning", "fetching", "writing", "rendering"}:
        return "review"
    return "request"


def show_brief_editor(status: str | None) -> bool:
    return phase(status) in {"request", "stopped"}


def show_outline(status: str | None) -> bool:
    return status == "awaiting_approval"


def show_deck(status: str | None) -> bool:
    return status == "done"


def show_restart(status: str | None) -> bool:
    return bool(status)


def steps_for(status: str | None) -> tuple[Step, ...]:
    cursor = _cursor(status)
    steps: list[Step] = []
    for index, label in enumerate(_STEP_LABELS):
        if index < cursor:
            state: StepState = "complete"
        elif index == cursor:
            state = "current"
        else:
            state = "upcoming"
        steps.append(Step(label, state))
    return tuple(steps)


def banner_for(run: Mapping[str, Any] | None) -> Banner | None:
    if run is None:
        return None
    status = str(run.get("status") or "")
    error = _plain(run.get("error"))
    if status == "awaiting_approval":
        return Banner(
            "waiting",
            "Waiting for your approval",
            "Nothing is read from the data source until you approve this outline.",
        )
    if status == "done":
        return Banner(
            "success",
            "The deck is ready",
            "Download the PowerPoint file. Every figure on the slides comes from the facts below.",
        )
    if status == "rejected":
        return Banner("stopped", "This outline was rejected", "No deck was produced. You can start another request.")
    if status == "no_data":
        return Banner("stopped", "No deck was produced", error or _ERROR_COPY["no_data"])
    if status == "failed":
        return Banner(
            "error",
            "The deck could not be finished",
            "The draft did not pass review after several attempts. Start a new request.",
        )
    if status == "error":
        return Banner("error", "The request did not go through", error or "Try again in a moment.")
    if status in _PROGRESS:
        return Banner("progress", "Still working", _PROGRESS[status])
    if error:
        return Banner("error", "The request did not go through", error)
    return Banner("neutral", "In progress", "The request is underway.")


def technical_detail(run: Mapping[str, Any]) -> str:
    """A support note, shown apart from the message a person should read first."""
    status = str(run.get("status") or "")
    if status == "failed":
        return _clip(_plain(run.get("error")))
    if status != "error":
        return ""
    detail = _plain(run.get("detail"))
    if not detail or detail == _plain(run.get("error")):
        return ""
    return _clip(detail)


def pending_copy(action: str) -> str:
    return {
        "draft": "Drafting the outline. No data is read until you approve it.",
        "approve": "Building the deck from the approved outline.",
        "edit": "Updating the outline with your notes.",
        "reject": "Closing this outline.",
    }.get(action, "Working on your request.")


def brief_problem(text: str) -> str:
    if len(text.strip()) < 3:
        return "Write a little more about the deck you need."
    return ""


def reference_label(run_id: object) -> str:
    text = str(run_id or "").strip()
    if not text:
        return ""
    return f"Reference {text[:8]}"


def download_name(run_id: object) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", str(run_id or "")[:8]) or "deck"
    return f"decksmith-{safe}.pptx"


def file_cache_key(run_id: object) -> str:
    return f"pptx:{run_id}"


def file_caption(size: int) -> str:
    kib = max(1, round(size / 1024))
    return f"PowerPoint file · {kib} KB"


def markdown_text(text: str) -> str:
    """Keep model text from being read as Markdown structure."""
    flat = " ".join(str(text).split())
    return "".join(f"\\{char}" if char in _MARKDOWN_SPECIAL else char for char in flat)


def outline_view(outline: object) -> OutlineView | None:
    if not isinstance(outline, dict):
        return None
    slides: list[OutlineSlideView] = []
    raw_slides = outline.get("slides")
    if isinstance(raw_slides, list):
        for index, raw in enumerate(raw_slides, start=1):
            slide = _outline_slide(raw, index)
            if slide is not None:
                slides.append(slide)
    title = _text(outline.get("deck_title"), "Untitled deck")
    return OutlineView(title, _audience(outline.get("audience")), _period(outline.get("period")), tuple(slides))


def fact_views(facts: object) -> tuple[FactView, ...]:
    if not isinstance(facts, list):
        return ()
    views: list[FactView] = []
    for raw in facts:
        view = _fact_view(raw)
        if view is not None:
            views.append(view)
    return tuple(views)


def slide_previews(spec: object, facts: object) -> tuple[SlidePreview, ...]:
    if not isinstance(spec, dict):
        return ()
    raw_slides = spec.get("slides")
    if not isinstance(raw_slides, list):
        return ()
    by_id = {fact.fact_id: fact for fact in fact_views(facts)}
    previews: list[SlidePreview] = []
    for index, raw in enumerate(raw_slides, start=1):
        preview = _slide_preview(raw, index, by_id)
        if preview is not None:
            previews.append(preview)
    return tuple(previews)


def coerce_run(status_code: int, body: object) -> dict[str, Any]:
    """Keep a successful run view. Turn anything else into a short error the page can show."""
    if isinstance(body, dict) and status_code < 400 and "run_id" in body and "status" in body:
        return dict(body)
    return {"status": "error", "error": failure_message(status_code, body), "detail": _support_detail(body)}


def failure_message(status_code: int, body: object) -> str:
    code = ""
    detail = ""
    if isinstance(body, dict):
        raw_code = body.get("error")
        if isinstance(raw_code, str):
            code = raw_code
        raw_detail = body.get("detail")
        if isinstance(raw_detail, str):
            detail = raw_detail.strip()
    if code == "no_data" and _plain_sentence(detail):
        return detail
    if code in _ERROR_COPY:
        return _ERROR_COPY[code]
    if status_code == 401:
        return _ERROR_COPY["authentication_failed"]
    if status_code == 403:
        return _ERROR_COPY["access_denied"]
    if status_code == 404:
        return _ERROR_COPY["run_not_found"]
    if status_code == 409:
        return _ERROR_COPY["no_data"]
    if status_code == 422:
        return _ERROR_COPY["invalid_parameters"]
    if status_code == 446:
        return _ERROR_COPY["guardrail_violation"]
    if status_code == 503:
        return _ERROR_COPY["upstream_unavailable"]
    if _plain_sentence(detail):
        return detail
    if status_code >= 500:
        return _ERROR_COPY["internal_error"]
    return "Something went wrong. Try again, or start another deck."


def connection_problem() -> dict[str, Any]:
    return {
        "status": "error",
        "error": "The deck service did not respond. Check that it is running, then try again.",
    }


def unreadable_response() -> dict[str, Any]:
    return {"status": "error", "error": "The deck service sent a response this page could not read. Try again."}


def masthead_html(identity: IdentityView) -> str:
    name = html.escape(identity.name)
    scope = html.escape(identity.scope)
    mode = html.escape(identity.mode)
    label = html.escape(f"Signed in as {identity.name}, {identity.scope}")
    return (
        '<header class="ds-masthead">'
        '<div class="ds-brand-block"><h1 class="ds-wordmark">DeckSmith</h1>'
        f'<p class="ds-tagline">{html.escape(TAGLINE)}</p></div>'
        f'<p class="ds-chip" aria-label="{label}">'
        f'<span class="ds-chip-kicker">{mode}</span>'
        f"<strong>{name}</strong><span>{scope}</span></p></header>"
    )


def sidebar_html(*, workspace: bool) -> str:
    note = WORKSPACE_NOTE if workspace else SIDEBAR_NOTE
    return (
        '<p class="ds-side-kicker">Workspace</p>'
        '<p class="ds-side-name">DeckSmith</p>'
        f'<p class="ds-side-note">{html.escape(note)}</p>'
    )


def stepper_html(steps: Sequence[Step]) -> str:
    items: list[str] = []
    for index, step in enumerate(steps, start=1):
        state = html.escape(step.state)
        label = html.escape(step.label)
        items.append(
            f'<li class="ds-step is-{state}"><span class="ds-step-index" aria-hidden="true">{index}</span>'
            f'<span class="ds-step-label">{label}</span><span class="ds-sr">{state}</span></li>'
        )
    opening = '<nav class="ds-progress" aria-label="Progress"><ol class="ds-steps">'
    return opening + "".join(items) + "</ol></nav>"


def stylesheet() -> str:
    """Chrome that follows whichever text colour the light or dark theme sets."""
    return """
<style>
.ds-masthead { display: flex; justify-content: space-between; align-items: flex-end;
  gap: 1.5rem; margin: 0 0 1.1rem; padding-bottom: 0.9rem;
  border-bottom: 1px solid color-mix(in srgb, currentColor 16%, transparent); }
.ds-wordmark, .ds-side-name { font-family: Georgia, "Iowan Old Style", Palatino, "Palatino Linotype", serif;
  font-weight: 500; letter-spacing: -0.03em; }
.stApp h1.ds-wordmark { font-size: 2.55rem; line-height: 1.02; margin: 0; padding: 0; }
.ds-tagline, .ds-side-note { margin: 0.35rem 0 0; opacity: 0.78; font-size: 0.95rem; }
.ds-chip { margin: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 0.05rem;
  padding: 0.5rem 0.85rem; border: 1px solid color-mix(in srgb, currentColor 22%, transparent);
  border-radius: 0.5rem; min-width: 9.5rem; line-height: 1.35; }
.ds-chip-kicker, .ds-side-kicker { font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase;
  opacity: 0.7; margin: 0; }
.ds-side-name { font-size: 1.45rem; margin: 0.1rem 0 0; }
.ds-side-note { margin: 0.35rem 0 1rem; font-size: 0.88rem; }
.ds-steps { display: flex; flex-wrap: wrap; gap: 0.45rem 1.2rem; list-style: none; padding: 0; margin: 0 0 1.15rem; }
.ds-step { display: flex; align-items: center; gap: 0.45rem; opacity: 0.48; }
.ds-step.is-complete, .ds-step.is-current { opacity: 1; }
.ds-step-index { width: 1.55rem; height: 1.55rem; display: inline-flex; align-items: center;
  justify-content: center; border: 1px solid color-mix(in srgb, currentColor 40%, transparent);
  border-radius: 999px; font-size: 0.75rem; }
.ds-step.is-current .ds-step-index { border-width: 2px; border-color: currentColor; font-weight: 650; }
.ds-step.is-complete .ds-step-index { background: color-mix(in srgb, currentColor 12%, transparent); }
.ds-sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
header[data-testid="stHeader"] { background: transparent; }
section.main .block-container { max-width: 1080px; }
@media (max-width: 720px) {
  .ds-masthead { flex-direction: column; align-items: flex-start; }
  .ds-chip { align-items: flex-start; }
  section.main .block-container { padding-left: 1rem; padding-right: 1rem; }
}
</style>
"""


def _cursor(status: str | None) -> int:
    if status in (None, "", "error"):
        return 0
    if status in {"awaiting_approval", "rejected", "intake", "planning"}:
        return 1
    if status in {"fetching", "writing", "rendering", "no_data", "failed"}:
        return 2
    if status == "done":
        return 3
    return 0


def _outline_slide(raw: object, index: int) -> OutlineSlideView | None:
    if not isinstance(raw, dict):
        return None
    requests: list[RequestChip] = []
    raw_requests = raw.get("data_requests")
    if isinstance(raw_requests, list):
        for item in raw_requests:
            chip = _request_chip(item)
            if chip is not None:
                requests.append(chip)
    slide_id = raw.get("slide_id")
    return OutlineSlideView(
        _number(slide_id if isinstance(slide_id, str) else "", index),
        layout_label(raw.get("layout")),
        _text(raw.get("title_hint"), "Untitled slide"),
        tuple(requests),
    )


def _request_chip(raw: object) -> RequestChip | None:
    if not isinstance(raw, dict):
        return None
    template = raw.get("template_id")
    return RequestChip(_text(raw.get("label"), "Data"), template if isinstance(template, str) else "")


def _fact_view(raw: object) -> FactView | None:
    if not isinstance(raw, dict):
        return None
    fact_id = raw.get("id")
    if not isinstance(fact_id, str) or not fact_id:
        return None
    source_raw = raw.get("source")
    source: dict[str, Any] = source_raw if isinstance(source_raw, dict) else {}
    fmt = _format_name(raw.get("format"))
    unit = _string(raw.get("unit"))
    points = _points(raw.get("categories"), raw.get("values"), fmt, unit)
    series = raw.get("kind") == "series" or bool(points)
    kind: FactKindLabel = "Series" if series else "Figure"
    value = _render_number(raw.get("value"), fmt, unit)
    if not points:
        display = "Series" if series else value
    elif len(points) == 1:
        display = "1 point"
    else:
        display = f"{len(points)} points"
    return FactView(
        fact_id,
        _text(raw.get("label"), fact_id),
        kind,
        display,
        _string(source.get("template_id")),
        _strings(source.get("tables")),
        _queried_at(source.get("as_of")),
        points,
        point_summary(points),
        _string(source.get("sql")).strip(),
        _parameters(source.get("params")),
    )


def _slide_preview(raw: object, index: int, facts: Mapping[str, FactView]) -> SlidePreview | None:
    if not isinstance(raw, dict):
        return None
    slide_id = raw.get("slide_id")
    layout = _string(raw.get("layout"))
    lines, quote, attribution, body = _body(raw, layout, facts)
    kpis = _kpis(raw.get("kpis"), facts)
    chart_kind, caption, points = _chart(raw.get("chart"), facts)
    sources = _source_labels(_strings(raw.get("sources")), facts)
    if layout == "appendix_sources" and not lines:
        lines = sources
        body = "list" if lines else "none"
    return SlidePreview(
        _number(slide_id if isinstance(slide_id, str) else "", index),
        layout_label(layout),
        _substitute(_text(raw.get("title"), "Untitled slide"), facts),
        _substitute(_text(raw.get("subtitle"), ""), facts),
        body,
        lines,
        quote,
        attribution,
        kpis,
        chart_kind,
        caption,
        points,
        point_summary(points),
        sources,
    )


def _body(
    raw: Mapping[str, Any], layout: str, facts: Mapping[str, FactView]
) -> tuple[tuple[str, ...], str, str, BodyKind]:
    if layout == "quote":
        quote = _substitute(_text(raw.get("quote"), ""), facts)
        attribution = _substitute(_text(raw.get("attribution"), ""), facts)
        return (), quote, attribution, "quote" if quote else "none"
    lines: list[str] = []
    for bullet in _strings(raw.get("bullets")):
        lines.append(_substitute(bullet, facts))
    columns = raw.get("columns")
    if isinstance(columns, list):
        for column in columns:
            if not isinstance(column, dict):
                continue
            heading = _substitute(_text(column.get("heading"), ""), facts)
            if heading:
                lines.append(heading)
            lines.extend(_substitute(item, facts) for item in _strings(column.get("bullets")))
    milestones = raw.get("milestones")
    if isinstance(milestones, list):
        for milestone in milestones:
            if not isinstance(milestone, dict):
                continue
            label = _substitute(_text(milestone.get("label"), ""), facts)
            detail = _substitute(_text(milestone.get("detail"), ""), facts)
            if label and detail:
                lines.append(f"{label} — {detail}")
            elif label or detail:
                lines.append(label or detail)
    table = raw.get("table")
    if isinstance(table, dict):
        heading = _text(table.get("row_heading"), "")
        if heading:
            lines.append(heading)
        columns = table.get("columns")
        if isinstance(columns, list):
            for column in columns:
                if not isinstance(column, dict):
                    continue
                name = _text(column.get("heading"), "Column")
                fact = facts.get(_string(column.get("fact_id")))
                lines.append(f"{name} ({fact.label})" if fact else name)
    if layout == "appendix_sources":
        return tuple(lines), "", "", "list" if lines else "none"
    return tuple(lines), "", "", "list" if lines else "none"


def _kpis(raw: object, facts: Mapping[str, FactView]) -> tuple[KpiView, ...]:
    if not isinstance(raw, list):
        return ()
    views: list[KpiView] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        fact = facts.get(_string(item.get("fact_id")))
        views.append(KpiView(_text(item.get("label"), fact.label if fact else "Figure"), fact.display if fact else "—"))
    return tuple(views)


def _chart(raw: object, facts: Mapping[str, FactView]) -> tuple[ChartKind, str, tuple[SeriesPoint, ...]]:
    if not isinstance(raw, dict):
        return "", "", ()
    kind = raw.get("type")
    chart_kind: ChartKind = kind if kind in {"line", "bar", "column"} else ""
    series = raw.get("series")
    if not isinstance(series, list) or not series:
        return chart_kind, "", ()
    first = series[0] if isinstance(series[0], dict) else {}
    name = _text(first.get("name"), "Series")
    fact = facts.get(_string(first.get("fact_id")))
    points = fact.points if fact else ()
    extra = sum(1 for item in series[1:] if isinstance(item, dict))
    kind_label = {"line": "Trend", "bar": "Bar chart", "column": "Column chart"}.get(chart_kind, "Chart")
    unit = ""
    if fact and fact.points:
        unit = _unit_caption(fact)
    more = f" {extra} more series on the slide." if extra else ""
    caption = " ".join(part for part in (f"{kind_label}: {name}.", unit, more.strip()) if part)
    return chart_kind, caption, points


def _unit_caption(fact: FactView) -> str:
    displays = [fact.display, *(point.display for point in fact.points)]
    if any(text.endswith("%") for text in displays):
        return "Values are percent."
    if any(text[:1] in {"€", "$", "£"} for text in displays):
        return "Values are currency."
    return ""


def _source_labels(ids: Sequence[str], facts: Mapping[str, FactView]) -> tuple[str, ...]:
    labels: list[str] = []
    for fact_id in ids:
        fact = facts.get(fact_id)
        labels.append(f"{fact_id} · {fact.label}" if fact else fact_id)
    return tuple(labels)


def _points(categories: object, values: object, fmt: FactFormat, unit: str) -> tuple[SeriesPoint, ...]:
    if not isinstance(categories, list) or not isinstance(values, list):
        return ()
    pairs: list[tuple[object, object]] = []
    for category, value in zip(categories, values, strict=False):
        if _as_float(value) is not None:
            pairs.append((category, value))
    if not pairs:
        return ()
    points: list[SeriesPoint] = []
    for category, value in pairs:
        number = _as_float(value)
        if number is None:
            continue
        points.append(SeriesPoint(category_label(category), format_value(number, fmt, unit), _magnitude(number, fmt)))
    return tuple(points)


def point_summary(points: Sequence[SeriesPoint]) -> str:
    if not points:
        return ""
    shown = [f"{point.label} {point.display}" for point in points[:8]]
    extra = len(points) - len(shown)
    if extra:
        shown.append(f"{extra} more")
    return " · ".join(shown)


def layout_label(layout: object) -> str:
    text = layout if isinstance(layout, str) and layout else "slide"
    return _LAYOUTS.get(text, text.replace("_", " ").capitalize())


def category_label(value: object) -> str:
    text = str(value)
    match = _YEAR_MONTH.match(text)
    if match is None:
        return text
    month = int(match.group(2))
    if not 1 <= month <= 12:
        return text
    return _MONTHS[month - 1]


def _audience(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    return _AUDIENCE.get(value, value)


def _period(value: object) -> str:
    if not isinstance(value, str):
        return ""
    match = _PERIOD.match(value)
    if match is None:
        return value
    return f"Q{match.group(2)} {match.group(1)}"


def _number(slide_id: str, index: int) -> str:
    if len(slide_id) == 3 and slide_id[0] == "s" and slide_id[1:].isdigit():
        return slide_id[1:]
    return f"{index:02d}"


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    return fallback


def _strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _format_name(value: object) -> FactFormat:
    if isinstance(value, str) and value in _FORMATS:
        return _FORMATS[value]
    return "decimal2"


def _render_number(value: object, fmt: FactFormat, unit: str) -> str:
    number = _as_float(value)
    if number is None:
        return "—"
    return format_value(number, fmt, unit)


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _magnitude(value: float, fmt: FactFormat) -> float:
    return value * 100 if fmt == "pct1" else value


def _substitute(text: str, facts: Mapping[str, FactView]) -> str:
    if not text:
        return ""

    def replace(match: re.Match[str]) -> str:
        fact = facts.get(match.group(1))
        return fact.display if fact and fact.kind == "Figure" else "—"

    return FACT_PATTERN.sub(replace, text)


def _queried_at(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime("%d %b %Y, %H:%M UTC")


def _parameters(value: object) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    parts = [f"{key} = {item}" for key, item in value.items() if isinstance(key, str) and isinstance(item, str)]
    return ", ".join(parts)


def _plain(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _clip(text: str) -> str:
    if len(text) <= 500:
        return text
    return text[:500].rstrip() + "…"


def _plain_sentence(text: str) -> bool:
    if not text or len(text) > 400 or "\n" in text:
        return False
    lowered = text.lower()
    return not any(token in lowered for token in ("traceback", "decksmith_", "exception", "{", "}", "<", ">"))


def _support_detail(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    detail = body.get("detail")
    if not isinstance(detail, str) or not _plain_sentence(detail.strip()):
        return ""
    return detail.strip()
