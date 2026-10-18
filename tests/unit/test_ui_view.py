"""Presentation rules for the Streamlit workspace. The page itself stays free of this logic."""

import tomllib
from pathlib import Path

import pytest

from decksmith.adapters.local.design.theme import contrast_ratio
from decksmith.interfaces.ui_view import (
    DEFAULT_DEMO_LABEL,
    DEFAULT_REQUEST,
    Banner,
    actor_changed,
    actor_key,
    banner_for,
    brief_problem,
    category_label,
    coerce_run,
    connection_problem,
    demo_labels,
    demo_user,
    download_name,
    fact_views,
    failure_message,
    file_cache_key,
    file_caption,
    identity_view,
    layout_label,
    markdown_text,
    masthead_html,
    outline_view,
    pending_copy,
    phase,
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

ROOT = Path(__file__).resolve().parents[2]
OUTLINE = {
    "deck_title": "Customer retention review",
    "audience": "exec",
    "period": "2026-Q3",
    "slides": [
        {"slide_id": "s01", "layout": "title", "title_hint": "Retention review", "data_requests": []},
        {
            "slide_id": "s02",
            "layout": "kpi",
            "title_hint": "Headline retention KPIs",
            "data_requests": [
                {"template_id": "churn_rate_quarter", "label": "Monthly churn (weighted)"},
                "skip",
            ],
        },
        {"slide_id": "bad", "layout": "chart", "title_hint": "The monthly path of churn", "data_requests": []},
    ],
}
FACTS = [
    {
        "id": "f1",
        "kind": "scalar",
        "label": "Monthly churn (weighted)",
        "unit": "ratio",
        "format": "pct1",
        "value": 0.018,
        "source": {
            "template_id": "churn_rate_quarter",
            "tables": ["main.cs.churn_monthly"],
            "as_of": "2026-10-18T10:38:59.402210Z",
            "sql": "SELECT 1",
            "params": {"start_month": "2026-07-01"},
        },
    },
    {
        "id": "f2",
        "kind": "scalar",
        "label": "Active subscriptions",
        "format": "int",
        "value": 6172,
        "source": {"template_id": "active_subscriptions", "tables": "main.cs.subscriptions", "as_of": "not-a-date"},
    },
    {
        "id": "f4",
        "kind": "series",
        "label": "Monthly churn",
        "format": "pct1",
        "categories": ["2026-07", "2026-13", "Enterprise"],
        "values": [0.024, "nope", 0.022],
        "source": {"template_id": "churn_trend_monthly", "as_of": "2026-10-18T10:38:59"},
    },
    {"id": "", "label": "ignored"},
    "skip",
]


def test_demo_users_keep_the_local_tokens_and_default_to_bob() -> None:
    assert demo_labels() == ("alice (her region only)", "bob (all regions)", "carol (no access)")
    assert DEFAULT_DEMO_LABEL == "bob (all regions)"
    assert demo_user("bob (all regions)").token == "bob-token"
    assert demo_user("alice (her region only)").scope == "Her region only"
    assert DEFAULT_REQUEST == "Build the quarterly customer retention review for the exec team"
    assert "2026" not in DEFAULT_REQUEST
    with pytest.raises(KeyError):
        demo_user("nobody")


def test_identity_view_names_the_person_and_hides_the_token() -> None:
    bob = identity_view("static", "bob (all regions)", {})
    assert bob == identity_view("static", "bob (all regions)", {})
    assert (bob.name, bob.scope, bob.mode) == ("Bob", "All regions", "Test user")
    assert "token" not in masthead_html(bob)
    unknown = identity_view("static", "missing", {})
    assert unknown.name == "Signed in"
    workspace = identity_view(
        "databricks_apps",
        "",
        {"X-Forwarded-Preferred-Username": "Bob <ops>", "X-Forwarded-Email": "bob@example.com"},
    )
    assert workspace.name == "Bob <ops>"
    assert "&lt;" in masthead_html(workspace)
    email_only = identity_view("databricks_apps", "", {"x-forwarded-email": "bob@example.com"})
    assert email_only.name == "bob@example.com"
    anonymous = identity_view("databricks_apps", "", {})
    assert anonymous.name == "Signed in"
    jwt = identity_view("jwt", "", {"authorization": "Bearer secret"})
    assert jwt.scope == "Authorized session"
    assert "secret" not in masthead_html(jwt)
    assert "token" not in sidebar_html(workspace=True)
    assert "workspace" in sidebar_html(workspace=True).lower()
    assert "test identities" in sidebar_html(workspace=False).lower()


def test_actor_switch_is_detected_without_clearing_the_first_visit() -> None:
    assert actor_key("static", "bob (all regions)") == "static:bob (all regions)"
    assert actor_key("jwt", "") == "jwt"
    assert actor_changed(None, "static:bob (all regions)") is False
    assert actor_changed("static:bob (all regions)", "static:bob (all regions)") is False
    assert actor_changed("static:alice (her region only)", "static:bob (all regions)") is True


@pytest.mark.parametrize(
    ("status", "phase_name", "editor", "outline", "deck"),
    [
        (None, "request", True, False, False),
        ("awaiting_approval", "review", False, True, False),
        ("done", "ready", False, False, True),
        ("rejected", "stopped", True, False, False),
        ("no_data", "stopped", True, False, False),
        ("failed", "stopped", True, False, False),
        ("error", "stopped", True, False, False),
        ("rendering", "review", False, False, False),
        ("mystery", "request", True, False, False),
    ],
)
def test_phase_decides_which_part_of_the_page_is_open(
    status: str | None, phase_name: str, editor: bool, outline: bool, deck: bool
) -> None:
    assert phase(status) == phase_name
    assert show_brief_editor(status) is editor
    assert show_outline(status) is outline
    assert show_deck(status) is deck
    assert show_restart(status) is bool(status)


def test_progress_marks_the_current_stage_in_words() -> None:
    assert [step.state for step in steps_for(None)] == ["current", "upcoming", "upcoming", "upcoming"]
    assert [step.state for step in steps_for("awaiting_approval")] == ["complete", "current", "upcoming", "upcoming"]
    assert [step.state for step in steps_for("rejected")] == ["complete", "current", "upcoming", "upcoming"]
    assert [step.state for step in steps_for("rendering")] == ["complete", "complete", "current", "upcoming"]
    assert [step.state for step in steps_for("done")] == ["complete", "complete", "complete", "current"]
    html = stepper_html(steps_for("done"))
    assert 'aria-label="Progress"' in html
    assert "is-current" in html and "Deck" in html
    assert "<script" not in html


@pytest.mark.parametrize(
    ("status", "title"),
    [
        ("awaiting_approval", "Waiting for your approval"),
        ("done", "The deck is ready"),
        ("rejected", "This outline was rejected"),
        ("no_data", "No deck was produced"),
        ("failed", "The deck could not be finished"),
        ("error", "The request did not go through"),
        ("writing", "Still working"),
        ("odd", "The request did not go through"),
        ("", "In progress"),
    ],
)
def test_banners_lead_with_a_plain_sentence(status: str, title: str) -> None:
    error = "None of the requested data is visible to you." if status in {"no_data", "odd"} else ""
    banner = banner_for({"status": status, "error": error})
    assert isinstance(banner, Banner)
    assert banner.title == title
    if status == "no_data":
        assert banner.body.startswith("None of the requested data")
    assert "traceback" not in banner.body.lower()
    assert banner_for(None) is None
    assert banner_for({}) is not None


def test_support_detail_stays_out_of_the_main_message() -> None:
    failed = {"status": "failed", "error": "QA failed after the maximum number of writer loops: s02 schema"}
    assert banner_for(failed) is not None
    assert "QA failed" not in (banner_for(failed) or Banner("error", "", "")).body
    assert technical_detail(failed).startswith("QA failed")
    assert technical_detail({"status": "failed", "error": "x" * 600}).endswith("…")
    assert technical_detail({"status": "done", "error": "hidden"}) == ""
    assert technical_detail({"status": "error", "error": "Same.", "detail": "Same."}) == ""
    assert technical_detail({"status": "error", "error": "Short.", "detail": "A longer note for support."}) == (
        "A longer note for support."
    )


def test_outline_is_a_slide_list_with_human_labels() -> None:
    view = outline_view(OUTLINE)
    assert view is not None
    assert view.title == "Customer retention review"
    assert view.audience == "Executive team"
    assert view.period == "Q3 2026"
    unnamed = outline_view({**OUTLINE, "period": "Last quarter"})
    assert unnamed is not None and unnamed.period == "Last quarter"
    assert [slide.number for slide in view.slides] == ["01", "02", "03"]
    assert view.slides[0].requests == ()
    assert view.slides[1].layout == "Headline figures"
    assert view.slides[1].requests[0].template == "churn_rate_quarter"
    assert outline_view(None) is None
    assert outline_view({"slides": "nope", "audience": "board", "period": "custom"}).slides == ()  # type: ignore[union-attr]
    assert layout_label("made_up") == "Made up"
    assert layout_label(None) == "Slide"


def test_facts_format_numbers_and_name_their_sources() -> None:
    views = fact_views(FACTS)
    assert [fact.fact_id for fact in views] == ["f1", "f2", "f4"]
    churn, active, series = views
    assert churn.display == "1.8%"
    assert churn.kind == "Figure"
    assert churn.tables == ("main.cs.churn_monthly",)
    assert churn.queried_at == "18 Oct 2026, 10:38 UTC"
    assert churn.parameters == "start_month = 2026-07-01"
    assert churn.query == "SELECT 1"
    assert active.display == "6,172"
    assert active.tables == ("main.cs.subscriptions",)
    assert active.queried_at == ""
    assert series.kind == "Series"
    assert series.display == "2 points"
    assert [point.label for point in series.points] == ["Jul", "Enterprise"]
    assert series.points[0].display == "2.4%"
    assert series.points[0].magnitude == pytest.approx(2.4)
    assert "Jul 2.4%" in series.summary
    assert fact_views(None) == ()
    currency = fact_views(
        [{"id": "f9", "kind": "scalar", "format": "currency0", "unit": "EUR", "value": 1200, "label": "Revenue"}]
    )[0]
    assert currency.display == "€1,200"
    unknown = fact_views([{"id": "f8", "format": "nope", "value": 1.5, "label": "Other"}])[0]
    assert unknown.display == "1.50"
    empty_series = fact_views([{"id": "f7", "kind": "series", "label": "Empty"}])[0]
    assert empty_series.display == "Series"
    one_point = fact_views([{"id": "f6", "kind": "series", "label": "One", "categories": ["A"], "values": [1]}])[0]
    assert one_point.display == "1 point"


def test_slide_preview_resolves_fact_references_and_charts() -> None:
    spec = {
        "slides": [
            {"slide_id": "s01", "layout": "title", "title": "Customer retention review", "subtitle": "For exec"},
            {
                "slide_id": "s02",
                "layout": "kpi",
                "title": "Where retention stands",
                "bullets": ["Weighted monthly churn was {{fact:f1}} and {{fact:f99}}"],
                "kpis": [{"label": "Monthly churn (weighted)", "fact_id": "f1"}, {"fact_id": "missing"}, "skip"],
                "sources": ["f1", "f4"],
            },
            {
                "slide_id": "s03",
                "layout": "chart",
                "title": "Monthly churn ended lower",
                "chart": {"type": "line", "series": [{"name": "Monthly churn", "fact_id": "f4"}, {"name": "Other"}]},
                "sources": ["f4"],
            },
            {
                "slide_id": "s04",
                "layout": "quote",
                "title": "A line",
                "quote": "Hold the line",
                "attribution": "Review",
            },
            {
                "slide_id": "s05",
                "layout": "comparison",
                "title": "Two readings",
                "columns": [
                    {"heading": "Path", "bullets": ["Read {{fact:f1}} first"]},
                    "skip",
                ],
            },
            {
                "slide_id": "s06",
                "layout": "timeline",
                "title": "Sequence",
                "milestones": [{"label": "Ask", "detail": "Brief"}, {"label": "Approve"}, "skip"],
            },
            {
                "slide_id": "s07",
                "layout": "table",
                "title": "By segment",
                "table": {"row_heading": "Segment", "columns": [{"heading": "Churn", "fact_id": "f4"}, "skip"]},
            },
            {"slide_id": "s08", "layout": "appendix_sources", "title": "Sources", "sources": ["f1"]},
            "skip",
        ]
    }
    slides = slide_previews(spec, FACTS)
    assert [slide.layout for slide in slides] == [
        "Title",
        "Headline figures",
        "Chart",
        "Quotation",
        "Comparison",
        "Timeline",
        "Table",
        "Sources",
    ]
    kpi, chart, quote = slides[1], slides[2], slides[3]
    assert kpi.kpis[0].display == "1.8%"
    assert kpi.kpis[1].display == "—"
    assert kpi.lines == ("Weighted monthly churn was 1.8% and —",)
    assert kpi.sources[0] == "f1 · Monthly churn (weighted)"
    assert chart.chart_kind == "line"
    assert chart.points[0].label == "Jul"
    assert "Values are percent." in chart.chart_caption
    assert "1 more series" in chart.chart_caption
    assert chart.summary.startswith("Jul ")
    assert quote.body == "quote" and quote.quote == "Hold the line"
    assert slides[4].lines == ("Path", "Read 1.8% first")
    assert slides[5].lines == ("Ask — Brief", "Approve")
    assert slides[6].lines == ("Segment", "Churn (Monthly churn)")
    assert slides[7].lines == ("f1 · Monthly churn (weighted)",)
    assert slide_previews(None, FACTS) == ()
    assert slide_previews({"slides": None}, FACTS) == ()
    bar = slide_previews(
        {"slides": [{"layout": "chart", "title": "Bars", "chart": {"type": "bar", "series": []}}]},
        [],
    )[0]
    assert bar.chart_kind == "bar" and bar.points == ()
    currency = slide_previews(
        {
            "slides": [
                {
                    "layout": "chart",
                    "title": "Revenue",
                    "chart": {"type": "column", "series": [{"name": "Revenue", "fact_id": "f9"}]},
                }
            ]
        },
        [
            {
                "id": "f9",
                "kind": "series",
                "format": "currency0",
                "unit": "USD",
                "label": "Revenue",
                "categories": ["A"],
                "values": [10],
            }
        ],
    )[0]
    assert "currency" in currency.chart_caption
    assert currency.points[0].display == "$10"


def test_api_errors_become_short_messages() -> None:
    run = {"run_id": "abc", "status": "awaiting_approval", "outline": {}}
    assert coerce_run(200, run)["run_id"] == "abc"
    assert coerce_run(200, run) is not run
    refused = coerce_run(403, {"error": "access_denied", "detail": "nope"})
    assert refused["status"] == "error"
    assert "do not have access" in str(refused["error"])
    visible = coerce_run(409, {"error": "no_data", "detail": "None of the requested data is visible to you."})
    assert visible["error"] == "None of the requested data is visible to you."
    assert "sign in" in failure_message(401, {"detail": [{"msg": "missing"}]}).lower()
    assert "no longer here" in failure_message(404, "html").lower()
    assert "shorter" in failure_message(422, {"detail": "request is longer than DECKSMITH_MAX_REQUEST_CHARS"})
    assert "review" in failure_message(446, {}).lower()
    assert "unavailable" in failure_message(503, {}).lower()
    assert "went wrong" in failure_message(500, {"detail": "Traceback (most recent call last)"}).lower()
    assert failure_message(418, {"detail": "The period has no rows yet."}) == "The period has no rows yet."
    assert "try again" in failure_message(418, {"detail": ""}).lower()
    assert connection_problem()["status"] == "error"
    assert unreadable_response()["status"] == "error"
    assert "DECKSMITH_" not in failure_message(422, {"error": "invalid_parameters", "detail": "DECKSMITH_MAX"})


def test_partial_payloads_stay_readable() -> None:
    bare = outline_view({"deck_title": "", "audience": 1, "period": None, "slides": ["skip", {"layout": "title"}]})
    assert bare is not None
    assert bare.title == "Untitled deck"
    assert bare.audience == "" and bare.period == ""
    assert len(bare.slides) == 1
    assert [step.state for step in steps_for("mystery")] == ["current", "upcoming", "upcoming", "upcoming"]
    assert failure_message(403, {}) == failure_message(403, {"error": "access_denied"})
    assert "no deck" in failure_message(409, None).lower()
    assert coerce_run(400, "html")["detail"] == ""
    assert coerce_run(400, {"detail": ["nope"]})["detail"] == ""
    assert coerce_run(400, {"detail": "has {brace}"})["detail"] == ""
    many = fact_views(
        [
            {
                "id": "f10",
                "kind": "series",
                "format": "int",
                "label": "Many",
                "categories": [f"c{i}" for i in range(9)],
                "values": list(range(9)),
            }
        ]
    )[0]
    assert many.summary.endswith("1 more")
    counts = slide_previews(
        {
            "slides": [
                {
                    "layout": "chart",
                    "title": "Counts",
                    "chart": {"type": "column", "series": [{"name": "Seats", "fact_id": "f10"}]},
                }
            ]
        },
        [
            {
                "id": "f10",
                "kind": "series",
                "format": "int",
                "label": "Seats",
                "categories": ["A"],
                "values": [3],
            }
        ],
    )[0]
    assert counts.chart_caption == "Column chart: Seats."


def test_small_copy_helpers() -> None:
    assert brief_problem("  ") == "Write a little more about the deck you need."
    assert brief_problem("A real brief") == ""
    assert pending_copy("approve").startswith("Building")
    assert pending_copy("nope") == "Working on your request."
    assert reference_label("") == ""
    assert reference_label("abcdef012345") == "Reference abcdef01"
    assert download_name("../../..") == "decksmith-deck.pptx"
    assert download_name("abc_def") == "decksmith-abc_def.pptx"
    assert file_cache_key("abc") == "pptx:abc"
    assert file_caption(0) == "PowerPoint file · 1 KB"
    assert file_caption(2048) == "PowerPoint file · 2 KB"
    assert markdown_text("**bold**\nnext") == r"\*\*bold\*\* next"
    assert category_label("2026-00") == "2026-00"
    assert category_label("SMB") == "SMB"
    assert "<style>" in stylesheet() and ".ds-masthead" in stylesheet()
    assert "script" not in stylesheet()


def test_theme_file_meets_contrast_for_text_and_charts() -> None:
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
    theme = config["theme"]
    _assert_slice(theme["light"], text=4.5, charts=3.0)
    _assert_slice(theme["dark"], text=4.5, charts=3.0)
    _assert_slice(theme["light"]["sidebar"], text=4.5, charts=None)
    _assert_slice(theme["dark"]["sidebar"], text=4.5, charts=None)
    assert contrast_ratio("#FFFFFF", theme["light"]["primaryColor"]) >= 4.5
    assert contrast_ratio("#FFFFFF", theme["dark"]["primaryColor"]) >= 4.5
    assert contrast_ratio(theme["light"]["borderColor"], theme["light"]["backgroundColor"]) >= 3
    assert contrast_ratio(theme["dark"]["borderColor"], theme["dark"]["backgroundColor"]) >= 3


def _assert_slice(section: dict[str, object], *, text: float, charts: float | None) -> None:
    background = str(section["backgroundColor"])
    assert contrast_ratio(str(section["textColor"]), background) >= text
    assert contrast_ratio(str(section["linkColor"]), background) >= text
    if charts is None:
        return
    colours = section["chartCategoricalColors"]
    assert isinstance(colours, list) and colours
    for colour in colours:
        assert contrast_ratio(str(colour), background) >= charts
