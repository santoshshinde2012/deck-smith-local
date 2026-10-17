"""Wire the nodes into a LangGraph state machine (the design's agent graph)."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from decksmith.application.nodes import DeckNodes
from decksmith.application.state import DeckState


def build_graph(nodes: DeckNodes, checkpointer: Any) -> Any:
    g: StateGraph[DeckState] = StateGraph(DeckState)
    g.add_node("intake", nodes.intake)
    g.add_node("planner", nodes.planner)
    g.add_node("await_approval", nodes.await_approval)
    g.add_node("data_fetch", nodes.data_fetch)
    g.add_node("writer", nodes.writer)
    g.add_node("check", nodes.check)
    g.add_node("render", nodes.render)
    g.add_node("failed", nodes.failed)
    g.add_edge(START, "intake")
    g.add_edge("intake", "planner")
    g.add_edge("planner", "await_approval")
    g.add_conditional_edges(
        "await_approval", nodes.route_approval, {"data_fetch": "data_fetch", "planner": "planner", "__end__": END}
    )
    g.add_conditional_edges("data_fetch", nodes.route_fetch, {"writer": "writer", "__end__": END})
    g.add_edge("writer", "check")
    g.add_conditional_edges("check", nodes.route_check, {"render": "render", "writer": "writer", "failed": "failed"})
    g.add_edge("render", END)
    g.add_edge("failed", END)
    return g.compile(checkpointer=checkpointer)
