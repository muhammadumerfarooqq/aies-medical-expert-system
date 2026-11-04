"""Shifa: wizard-style Streamlit app.  Run: python -m streamlit run app.py

PRESENTATION ONLY. Reasoning comes from the expert_system package and every name and
number from the knowledge base; the drawing code lives in ui/theme.py and ui/components.py.
Steps: 1 Symptoms -> 2 Severity -> 3 Reasoning -> 4 Diagnosis.
"""

from __future__ import annotations

import streamlit as st

from expert_system.kb_verify import load_kb, verify_kb
from ui.components import (init_state, inject_css, render_footer, render_kb_view,
                           render_topbar, render_wizard, start_from_text)
from ui.theme import APP_NAME, OFFICIAL_TITLE, VIEWS

st.set_page_config(page_title=f"{APP_NAME} - {OFFICIAL_TITLE}", page_icon=":material/ecg_heart:",
                   layout="wide")
inject_css()


@st.cache_data
def load_verified() -> tuple[dict, bool, list[str], dict]:
    """Load the knowledge base once and verify it."""
    kb = load_kb()
    ok, errors, stats = verify_kb(kb)
    return kb, ok, errors, stats


kb, kb_ok, kb_errors, kb_stats = load_verified()
if not kb_ok:
    st.error("The knowledge base failed verification: " + "; ".join(kb_errors))
    st.stop()

S = st.session_state
init_state(S)
view = render_topbar(kb, S)

if view == VIEWS[0]:
    # Typing is only offered on step 1. (chat_input stays in the main body so it is pinned.)
    if S["consult"] is None or S["consult"]["step"] == 1:
        prompt = st.chat_input("Describe how you feel, e.g. 'bukhar aur sir dard'")
        if prompt:
            start_from_text(kb, S, prompt)
            st.rerun()
    render_wizard(kb, S)
else:
    render_kb_view(kb, S, kb_stats)

render_footer()
