"""Streamlit GUI: python -m streamlit run app.py

PRESENTATION ONLY. All reasoning, ranking, symptom matching and text come from
the expert_system package and the knowledge base; this file only draws them.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from expert_system.backward import (CLOSE_MARGIN, MAX_QUESTIONS, apply_answer, close_call,
                                    next_step, rules_supporting)
from expert_system.cli import (OUTCOME_TEXT, SAFETY_NOTE, below_threshold_text, default_value,
                               no_diagnosis_message, required_hints, resolve_symptom,
                               severity_outranks_confidence, split_entries, why_asking)
from expert_system.engine import diagnose, display_name, fmt
from expert_system.kb_verify import format_success, load_kb, verify_kb

ROOT = Path(__file__).resolve().parent
NO_EXAMPLE = "-"

st.set_page_config(page_title="Medical Diagnosis Expert System", layout="wide")


@st.cache_data
def load_verified() -> tuple[dict, bool, list[str], dict]:
    """Load the knowledge base once and verify it."""
    kb = load_kb()
    ok, errors, stats = verify_kb(kb)
    return kb, ok, errors, stats


@st.cache_data
def load_examples() -> list[dict]:
    """Clinical example cases from tests/cases.json."""
    with open(ROOT / "tests" / "cases.json", "r", encoding="utf-8") as f:
        return json.load(f)


kb, kb_ok, kb_errors, kb_stats = load_verified()
if not kb_ok:
    st.error("The knowledge base failed verification:\n\n" + "\n".join(f"- {e}" for e in kb_errors))
    st.stop()

S = st.session_state
S.setdefault("chosen", [])
S.setdefault("typed", "")
S.setdefault("example", NO_EXAMPLE)
S.setdefault("hyb", None)

SYMPTOMS = kb["symptoms"]
LEVELS = [k for k in kb["meta"]["cf_conventions"]["intensity_cf"] if k != "yes"]
EXAMPLES = {f"{c['id']} {c['name']}": c for c in load_examples()}
MAIN_SYMPTOMS = [sid for sid, sym in SYMPTOMS.items() if not sym.get("ask_only_if")]


def severity_color(severity: str) -> str:
    """Badge colour by severity rank: lowest green, middle orange, highest red."""
    ranks = sorted(kb["meta"]["severity_rank"], key=kb["meta"]["severity_rank"].get)
    palette = ["green", "orange", "red"]
    return palette[ranks.index(severity)] if len(ranks) == 3 else "blue"


# ------------------------------------------------------------------ callbacks

def reset_inputs() -> None:
    """Forget all symptom inputs and results."""
    for key in list(S.keys()):
        if key.startswith(("int_", "fu_", "ans_")):
            del S[key]
    S["chosen"] = []
    S["typed"] = ""
    S["hyb"] = None


def load_example() -> None:
    """Fill the inputs from the selected example case."""
    if S["example"] == NO_EXAMPLE:
        return
    case = EXAMPLES[S["example"]]
    reset_inputs()
    chosen = []
    for sid, value in case["input"].items():
        if sid not in SYMPTOMS:
            continue
        if SYMPTOMS[sid].get("ask_only_if"):
            S[f"fu_{sid}"] = value != "no"
        else:
            chosen.append(sid)
            if SYMPTOMS[sid]["input"] == "intensity":
                S[f"int_{sid}"] = value if value in LEVELS else default_value(kb, sid)
    S["chosen"] = chosen


def clear_all() -> None:
    """Clear button: reset inputs and the example selector."""
    reset_inputs()
    S["example"] = NO_EXAMPLE


def add_symptom(sid: str) -> None:
    """'Add X' button for a did-you-mean suggestion."""
    if SYMPTOMS[sid].get("ask_only_if"):
        S[f"fu_{sid}"] = True
    elif sid not in S["chosen"]:
        S["chosen"] = S["chosen"] + [sid]


def submit_answer(hyb: dict, question, key: str) -> None:
    """Submit the answer to the current backward-chaining question."""
    choice = S[key]
    answer = {"No": "no", "Yes": "yes"}.get(choice, choice)
    step = apply_answer(kb, hyb["known"], hyb["denied"], question, answer)
    hyb["steps"].append(step)
    hyb["result"] = step.result_after


# ------------------------------------------------------------------- sidebar

with st.sidebar:
    st.title("Intelligent Medical Diagnosis Expert System")
    st.write("AIES CCP, Fall 2026, NED University")
    st.write("Muhammad Umer Farooq (CTGA-021), Fizza Aman (CTGA-018)")
    st.success(format_success(kb_stats))
    with st.expander("How it works"):
        st.markdown(
            "**Forward chaining (5 steps)**\n"
            "1. Start with the reported symptoms as facts.\n"
            "2. Match: find every rule whose conditions all hold.\n"
            "3. Conflict resolution: priority, then shallow rules, then JSON order.\n"
            "4. Act: fire one rule and update the certainty factor of its conclusion.\n"
            "5. Repeat until no rule can fire.\n\n"
            "**Backward chaining (5 steps)**\n"
            "1. Start with a goal: each of the two close diseases.\n"
            "2. Search for rules that conclude the goal.\n"
            "3. Check each condition: reported symptoms are true.\n"
            "4. Unknown: a fact becomes a sub-goal, an unreported symptom becomes a question.\n"
            "5. Repeat until every sub-goal is explored.")
    st.caption(kb["meta"]["disclaimer"])

tab_dx, tab_trace, tab_why, tab_bc, tab_kb = st.tabs(
    ["Diagnosis", "Reasoning trace", "Why not", "Backward chaining", "Knowledge base"])


# ------------------------------------------------------------- Diagnosis: inputs

def render_inputs() -> tuple[list[str], list[str]]:
    """Draw the input widgets; return (selected symptom ids, notes about typed text)."""
    left, right = st.columns([3, 1])
    left.selectbox("Try an example", [NO_EXAMPLE] + list(EXAMPLES), key="example",
                   on_change=load_example)
    right.write("")
    right.button("Clear", on_click=clear_all, key="clear")

    st.multiselect("Symptoms", MAIN_SYMPTOMS, key="chosen",
                   format_func=lambda sid: SYMPTOMS[sid]["label"])
    st.text_input("Or type symptoms (English or Roman Urdu, e.g. bukhar aur sir dard, ulti)",
                  key="typed")

    typed_ids, notes = [], []
    for entry in split_entries(S["typed"], kb):
        sid, suggestion = resolve_symptom(entry, kb)
        if sid is not None:
            if sid not in typed_ids:   # keep first-seen order, no duplicates
                typed_ids.append(sid)
        elif suggestion is not None:
            label = SYMPTOMS[suggestion]["label"]
            st.write(f"Did you mean **{label}**? (you typed '{entry}')")
            st.button(f"Add {label}", key=f"add_{suggestion}", on_click=add_symptom,
                      args=(suggestion,))
        else:
            notes.append(f"'{entry}' is not in the knowledge base and was ignored.")
    if typed_ids:
        st.success("Recognised from text: " + ", ".join(SYMPTOMS[s]["label"] for s in typed_ids))
    for note in notes:
        st.warning(note)

    selected = list(S["chosen"]) + [s for s in typed_ids if s not in S["chosen"]]
    intensity_ids = [s for s in selected if SYMPTOMS[s]["input"] == "intensity"]
    if intensity_ids:
        st.write("How severe is each symptom?")
        columns = st.columns(3)
        for i, sid in enumerate(intensity_ids):
            S.setdefault(f"int_{sid}", default_value(kb, sid))
            with columns[i % 3]:
                st.segmented_control(SYMPTOMS[sid]["label"], LEVELS, key=f"int_{sid}")

    for sid, sym in SYMPTOMS.items():
        parent = sym.get("ask_only_if")
        if parent and parent in selected:
            S.setdefault(f"fu_{sid}", False)
            st.checkbox(sym["label"] + "?", key=f"fu_{sid}")
    return selected, notes


def build_symptoms(selected: list[str]) -> dict[str, str]:
    """Turn the widget state into the {symptom id: value} input of the engine."""
    symptoms = {}
    for sid in selected:
        if SYMPTOMS[sid]["input"] == "intensity":
            symptoms[sid] = S.get(f"int_{sid}") or default_value(kb, sid)
        else:
            symptoms[sid] = "yes"
    for sid, sym in SYMPTOMS.items():
        if sym.get("ask_only_if") and S.get(f"fu_{sid}") and sym["ask_only_if"] in selected:
            symptoms[sid] = "yes"
    return symptoms


# ------------------------------------------------------------ Diagnosis: results

def render_ranking(result) -> None:
    """Ranked table with a bar and a severity badge per disease."""
    if not result.diseases:
        st.info(no_diagnosis_message(kb))
        for hint in required_hints(result):
            st.info(hint)
    else:
        st.subheader("Possible diseases (ranked: severity first, then confidence)")
        header = st.columns([1, 3, 2, 6, 2])
        for column, title in zip(header, ["Rank", "Disease", "Severity", "Confidence %", "CF"]):
            column.markdown(f"**{title}**")
        for rank, d in enumerate(result.diseases, 1):
            row = st.columns([1, 3, 2, 6, 2])
            row[0].write(rank)
            row[1].write(d.name)
            with row[2]:
                st.badge(d.severity, color=severity_color(d.severity))
            row[3].progress(min(max(d.percent / 100, 0.0), 1.0), text=fmt(d.percent, 1) + "%")
            row[4].write(fmt(d.cf, 2))
        if severity_outranks_confidence(result):
            st.caption(SAFETY_NOTE)
    if result.below_threshold:
        st.info(below_threshold_text(result))


def render_hybrid(hyb: dict) -> None:
    """Backward-chaining panel: one question at a time."""
    call = close_call(hyb["initial"])
    if call is None:
        return
    versus = (f"{call.first.name} {fmt(call.first.percent, 1)}% vs "
              f"{call.second.name} {fmt(call.second.percent, 1)}% "
              f"(gap {fmt(call.gap, 1)} <= {CLOSE_MARGIN:g})")
    asked = len(hyb["steps"])
    question, outcome = next_step(kb, hyb["result"], hyb["known"], hyb["denied"], asked)
    if asked == 0 and question is None:
        # Close, but every symptom that could separate them was already reported.
        st.warning(f"Close call: {versus}. Every symptom that could separate them "
                   f"has already been reported, so backward chaining has nothing to ask.")
    elif asked == 0:
        st.warning(f"Close call: {versus}. Backward chaining will ask up to "
                   f"{MAX_QUESTIONS} questions.")
    else:
        # History line, shown above the answered questions (values from the initial result).
        st.warning(f"Close call at the start: {versus}. Backward chaining asked "
                   f"{asked} question(s).")
    for step in hyb["steps"]:
        st.markdown(f"- **{step.question.label}**: {step.answer}")
    if question is None:
        # Green only when the answers actually separated the diseases.
        show = st.success if outcome == "separated" else st.info
        show("Outcome: " + OUTCOME_TEXT[outcome])
        return
    key = f"ans_{len(hyb['steps'])}"
    options = ["No"] + (LEVELS if question.input_type == "intensity" else ["Yes"])
    st.markdown(f"**{why_asking(question)}**")
    st.radio(f"{question.label}?", options, key=key, horizontal=True)
    st.button("Submit answer", key=f"submit_{key}", on_click=submit_answer,
              args=(hyb, question, key))


def render_disease_details(result) -> None:
    """One expander per shown disease."""
    for rank, d in enumerate(result.diseases, 1):
        with st.expander(f"{rank}. {d.name} ({d.severity}) - {fmt(d.percent, 1)}%",
                         expanded=rank == 1):
            st.write(d.description)
            st.markdown("**Why this was suggested**")
            st.code("\n".join(d.justification), language=None)
            st.markdown("**Treatment**\n" + "\n".join(f"- {t}" for t in d.treatment))
            st.markdown("**Prevention**\n" + "\n".join(f"- {p}" for p in d.prevention))
            st.markdown("**Sources:** " + ", ".join(d.sources))


with tab_dx:
    selected, input_notes = render_inputs()
    if st.button("Diagnose", type="primary", key="diagnose"):
        symptoms = build_symptoms(selected)
        first = diagnose(kb, symptoms)
        S["hyb"] = {"known": dict(symptoms), "denied": set(), "steps": [], "initial": first,
                    "result": first, "notes": input_notes}
    hyb = S["hyb"]
    if hyb is not None:
        result = hyb["result"]
        st.divider()
        for alert in result.alerts:
            st.error(alert["message"], icon=":material/emergency:")
        render_ranking(result)
        render_hybrid(hyb)
        render_disease_details(result)
        for note in hyb["notes"] + result.warnings:
            st.warning(note)
    st.caption(kb["meta"]["disclaimer"])


# ------------------------------------------------------------------ other tabs

with tab_trace:
    if S["hyb"] is None:
        st.info("Run a diagnosis first.")
    else:
        trace = S["hyb"]["result"].trace
        st.dataframe([{
            "Cycle": f.cycle, "Conflict set": ", ".join(f.conflict_set), "Fired": f.rule_id,
            "Kind": f.kind,
            "Concluded": display_name(kb, f.concluded_fact) if f.concluded_fact else "-",
            "CF before": fmt(f.cf_before, 3) if f.cf_before is not None else "-",
            "CF after": fmt(f.cf_after, 3) if f.cf_after is not None else "-",
            "Re-fire": "yes" if f.refire else "no"} for f in trace],
            hide_index=True, width="stretch")

with tab_why:
    if S["hyb"] is None:
        st.info("Run a diagnosis first.")
    else:
        for did, lines in S["hyb"]["result"].why_not.items():
            with st.expander(display_name(kb, did)):
                st.code("\n".join(lines), language=None)

with tab_bc:
    hyb = S["hyb"]
    if hyb is None:
        st.info("Run a diagnosis first.")
    elif close_call(hyb["initial"]) is None:
        st.info("No close call: backward chaining was not needed.")
    else:
        call = close_call(hyb["initial"])
        st.write(f"Close call: {call.first.name} vs {call.second.name}, gap {fmt(call.gap, 1)} "
                 f"(limit {CLOSE_MARGIN:g}).")
        for i, step in enumerate(hyb["steps"], 1):
            st.markdown(f"**Q{i}. {step.question.label}** -> {step.answer}")
            st.caption(why_asking(step.question))
            ranking = ", ".join(f"{d.name} {fmt(d.percent, 1)}%" for d in step.result_after.diseases)
            gap = fmt(step.gap_after, 1) if step.gap_after is not None else "-"
            st.write(f"Ranking after: {ranking or 'no disease shown'} (gap {gap})")
        question, outcome = next_step(kb, hyb["result"], hyb["known"], hyb["denied"],
                                      len(hyb["steps"]))
        st.write("Outcome: " + (OUTCOME_TEXT[outcome] if outcome else "waiting for an answer"))

with tab_kb:
    counts = st.columns(4)
    for column, (title, key) in zip(counts, [("Diseases", "diseases"), ("Symptoms", "symptoms"),
                                              ("Intermediate facts", "intermediate_facts"),
                                              ("Rules", "rules")]):
        column.metric(title, kb_stats[key])
    st.caption(format_success(kb_stats))
    choice = st.selectbox("Filter rules by disease", ["All diseases"] + list(kb["diseases"]),
                          format_func=lambda d: d if d == "All diseases" else kb["diseases"][d]["name"])
    rules = kb["rules"] if choice == "All diseases" else rules_supporting(kb, choice)
    st.dataframe([{
        "ID": r["id"], "IF": " AND ".join(display_name(kb, p) for p in r["if"]),
        "THEN": display_name(kb, r["then"]), "CF": r["cf"], "Priority": r["priority"],
        "Knowledge type": r["knowledge_type"], "Source": r["source"]} for r in rules],
        hide_index=True, width="stretch")
    st.subheader("Diseases")
    st.dataframe([{"Name": d["name"], "Severity": d["severity"], "Sources": ", ".join(d["sources"])}
                  for d in kb["diseases"].values()], hide_index=True, width="stretch")
    st.subheader("Symptoms")
    st.dataframe([{"Label": s["label"], "Input": s["input"], "Synonyms": ", ".join(s["synonyms"])}
                  for s in SYMPTOMS.values()], hide_index=True, width="stretch")
    st.subheader("Red flags")
    st.dataframe([{"ID": f["id"], "IF": " AND ".join(display_name(kb, p) for p in f["if"]),
                   "Message": f["message"], "Source": f["source"]} for f in kb["red_flags"]],
                 hide_index=True, width="stretch")
    st.info("Factual knowledge (descriptions, severities, treatments, red flags) comes from WHO/CDC "
            "sources. Heuristic knowledge (rules and certainty factors) is expert judgement and is "
            "not clinically validated.")
