"""Streamlit UI: pick a test user, request a deck, approve the outline, download the file.

Run: streamlit run src/decksmith/interfaces/ui.py  (talks to the API at DECKSMITH_API_URL)
"""

from __future__ import annotations

import os

import httpx
import streamlit as st

from decksmith.domain.errors import AuthenticationError
from decksmith.interfaces.ui_auth import identity_mode, request_headers

API = os.environ.get("DECKSMITH_API_URL", "http://localhost:8000")
USERS = {"alice (her region only)": "alice-token", "bob (all regions)": "bob-token", "carol (no access)": "carol-token"}

st.set_page_config(page_title="DeckSmith", layout="centered")
st.title("DeckSmith")
try:
    forwarded = st.context.headers
    mode = identity_mode(os.environ, forwarded)
    demo_token = ""
    if mode == "static":
        user = st.sidebar.selectbox("Act as", list(USERS))
        demo_token = USERS[user]
    headers = request_headers(mode, forwarded, demo_token)
except AuthenticationError as exc:
    st.error(str(exc))
    st.stop()
client = httpx.Client(base_url=API, headers=headers, timeout=120)

prompt = st.text_area("What deck do you need?", "Build the Q3 2026 customer retention review for the exec team")
if st.button("Draft outline"):
    st.session_state["run"] = client.post("/v1/decks", json={"request": prompt}).json()

run = st.session_state.get("run")
if run:
    st.caption(f"run {run.get('run_id', '')} · status {run.get('status', run.get('error'))}")
    if run.get("status") == "awaiting_approval":
        for slide in run["outline"]["slides"]:
            st.write(f"**{slide['slide_id']}** · {slide['layout']} · {slide['title_hint']}")
        feedback = st.text_input("Feedback (for Edit)")
        cols = st.columns(3)
        for col, action in zip(cols, ("approve", "edit", "reject"), strict=True):
            if col.button(action.title()):
                st.session_state["run"] = client.post(
                    f"/v1/decks/{run['run_id']}/decision", json={"action": action, "feedback": feedback}
                ).json()
                st.rerun()
    elif run.get("status") == "done":
        data = client.get(f"/v1/decks/{run['run_id']}/file").content
        st.download_button("Download deck", data, file_name="decksmith.pptx")
        st.dataframe(
            [
                {
                    "fact": f["id"],
                    "label": f["label"],
                    "template": f["source"]["template_id"],
                    "tables": ", ".join(f["source"]["tables"]),
                }
                for f in run["facts"]
            ]
        )
    elif run.get("error"):
        st.warning(run["error"])
