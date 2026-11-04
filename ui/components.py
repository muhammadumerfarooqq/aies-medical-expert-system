"""Render functions for the Shifa wizard UI. Display only.

One consultation object lives in st.session_state and is rendered from state:
    step 1 SYMPTOMS -> step 2 SEVERITY -> step 3 REASONING -> step 4 DIAGNOSIS.

Every number and name comes from the engine, the backward-chaining module or the knowledge
base. All motion is CSS (see ui/theme.py); there are no timers and no streaming. Every string
that holds user text or KB text goes through html.escape before it enters HTML.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

import streamlit as st

from expert_system.backward import (CLOSE_MARGIN, apply_answer, close_call, next_step,
                                    rules_supporting, top_two_gap)
from expert_system.cli import (CONFIDENCE_NOTE, OUTCOME_TEXT, below_threshold_text, join_names,
                               no_diagnosis_message, required_hints, why_asking)
from expert_system.engine import diagnose, display_name, fmt
from expert_system.text_parser import intensity_levels, parse_text
from ui.theme import (APP_NAME, CSS, FOOTER, KB_SHOWCASE, MARK_SVG, MAX_CHAIN_SECONDS,
                      MAX_GAP_SECONDS, REQUIREMENTS, STEPS, TAGLINE, VIEWS)

EXAMPLES = ["I have fever, headache, nausea and body aches", "bukhar aur khansi hai",
            "chest pain and shortness of breath"]
SHOW_OPTIONS = ["Why this?", "Treatment", "Prevention"]
ANIM_SECONDS = 0.5          # duration of one step animation (added to the last delay)
PRIORITY_LINE = "Listed first because severe conditions take priority over less severe ones."
TIER_CAPTION = "Severe conditions are listed first, even if a less severe one has higher confidence."


def esc(text: object) -> str:
    """HTML-escape any value."""
    return html.escape(str(text), quote=True)


def chip(text: str, css: str = "") -> str:
    """One chip (text escaped)."""
    return f'<span class="chip {css}">{esc(text)}</span>'


def tag(text: str, css: str = "") -> str:
    """Bold tag chip that starts a chain step."""
    return f'<span class="tagc {css}">{esc(text)}</span>'


def inject_css() -> None:
    """Add the theme CSS (a static string from ui/theme.py)."""
    st.markdown(CSS, unsafe_allow_html=True)


def brand_html() -> str:
    """Logo mark + name + tagline."""
    return (f'<div class="brand">{MARK_SVG}<div><div class="name">{esc(APP_NAME)}</div>'
            f'<div class="tag">{esc(TAGLINE)}</div></div></div>')


def steps_html(step: int) -> str:
    """Display-only 4-step strip; the current step is highlighted, done steps are ticked."""
    parts = []
    for i, name in enumerate(STEPS, 1):
        state = "now" if i == step else "done" if i < step else ""
        mark = "✓ " if state == "done" else ""
        parts.append(f'<span class="s {state}">{mark}{i} {esc(name)}</span>')
    return f'<div class="stepsbar">{"".join(parts)}</div>'


# ------------------------------------------------------------------ state

def init_state(S) -> None:
    """Create the session-state slots once."""
    S.setdefault("consult", None)
    S.setdefault("seq", 0)
    S.setdefault("kb_tile", None)


def new_consult(S) -> dict:
    """Create a fresh consultation object (the ONE state object of a consultation)."""
    S["seq"] += 1
    consult = {"id": f"c{S['seq']}", "step": 1, "reached": 1, "text": "", "symptoms": {},
               "negated": [], "unknown": [], "read_from": {}, "defaulted": [], "hyb": None,
               "played": set(), "nonce": {}, "adding": False, "msg": ""}
    S["consult"] = consult
    return consult


def clear_widget_keys(S, prefixes=("sev_", "ask_pills", "add_pills")) -> None:
    """Forget severity selectors and chip selections."""
    for key in list(S.keys()):
        if key.startswith(prefixes) or key.endswith("-nodx-pills"):
            del S[key]


def new_consultation(S) -> None:
    """'New consultation': back to an empty step 1."""
    clear_widget_keys(S)
    S["consult"] = None


def default_level(kb: dict) -> str:
    """The middle intensity level (used when the user states none)."""
    levels = intensity_levels(kb)
    return levels[len(levels) // 2]


def add_symptom(kb: dict, consult: dict, sid: str) -> None:
    """Add one symptom (and the parent it depends on) to a consultation."""
    symptom = kb["symptoms"][sid]
    if sid not in consult["symptoms"]:
        if symptom["input"] == "intensity":
            consult["symptoms"][sid] = default_level(kb)
            consult["defaulted"].append(sid)
        else:
            consult["symptoms"][sid] = "yes"
    if sid in consult["negated"]:
        consult["negated"].remove(sid)
    parent = symptom.get("ask_only_if")
    if parent:
        add_symptom(kb, consult, parent)


def discard_result(consult: dict) -> None:
    """Forget the diagnosis, the backward answers and everything reached after step 2."""
    consult["hyb"] = None
    consult["reached"] = min(consult["reached"], 2)
    consult["played"] = set()
    consult["nonce"] = {}


def goto_severity(S, consult: dict) -> None:
    """Show step 2 with every selector preloaded from the consultation."""
    clear_widget_keys(S, ("sev_",))
    consult["step"] = 2
    consult["reached"] = max(consult["reached"], 2)
    consult["adding"] = False


def start_from_text(kb: dict, S, text: str) -> None:
    """A typed (or example) sentence: parse it, then go to step 2."""
    parsed = parse_text(kb, text)
    consult = new_consult(S)
    clear_widget_keys(S)
    consult.update(text=text, symptoms=dict(parsed.symptoms), negated=list(parsed.negated),
                   unknown=list(parsed.unknown), read_from=dict(parsed.read_from),
                   defaulted=list(parsed.defaulted))
    if parsed.symptoms:
        goto_severity(S, consult)
    else:
        consult["msg"] = "nomatch"


def merge_picked(kb: dict, S, key: str, replace: bool) -> None:
    """Continue from the chips. replace=True: the chips ARE the symptom list (step 1);
    replace=False: the chips are added to the current list (Add more symptoms)."""
    picked = S.get(key) or []
    consult = S["consult"] or new_consult(S)
    if not picked and replace:
        consult["msg"] = "empty"
        return
    before = set(consult["symptoms"])
    if replace:
        for sid in list(consult["symptoms"]):
            if sid not in picked:
                del consult["symptoms"][sid]
    for sid in picked:
        add_symptom(kb, consult, sid)
    consult["msg"] = ""
    consult["text"] = consult["text"] or "Picked: " + ", ".join(
        kb["symptoms"][s]["label"] for s in consult["symptoms"])
    changed = set(consult["symptoms"]) != before
    clear_widget_keys(S, ("ask_pills", "add_pills"))
    if changed or consult["hyb"] is None:
        clear_widget_keys(S, ("sev_",))
        discard_result(consult)
    consult["step"] = 2
    consult["reached"] = max(consult["reached"], 2)
    consult["adding"] = False


def save_severity(kb: dict, S, consult: dict) -> bool:
    """Copy the severity selectors into the consultation; True if any level changed."""
    changed = False
    for sid in consult["symptoms"]:
        if kb["symptoms"][sid]["input"] == "intensity":
            value = S.get(f"sev_{sid}") or consult["symptoms"][sid]
            if value != consult["symptoms"][sid]:
                changed = True
                consult["symptoms"][sid] = value
    return changed


def severity_dirty(kb: dict, S, consult: dict) -> bool:
    """True if a selector on step 2 differs from the saved consultation."""
    return any(kb["symptoms"][sid]["input"] == "intensity"
               and (S.get(f"sev_{sid}") or consult["symptoms"][sid]) != consult["symptoms"][sid]
               for sid in consult["symptoms"])


def do_diagnose(kb: dict, S) -> None:
    """'Diagnose': keep the old result if nothing changed, else run the engine afresh."""
    consult = S["consult"]
    changed = save_severity(kb, S, consult)
    if changed or consult["hyb"] is None:
        symptoms = {sid: consult["symptoms"][sid] if kb["symptoms"][sid]["input"] == "intensity" else "yes"
                    for sid in consult["symptoms"]}
        first = diagnose(kb, symptoms)
        consult["hyb"] = {"known": dict(symptoms), "denied": set(), "steps": [],
                          "initial": first, "result": first}
        consult["played"] = set()
        consult["nonce"] = {}
    consult["step"] = 3
    consult["reached"] = max(consult["reached"], 3)


def go(kb: dict, S, delta: int) -> None:
    """Back / forward icon buttons: move one step; never runs the engine, never replays."""
    consult = S["consult"]
    if consult is None:
        return
    if consult["step"] == 2:
        save_severity(kb, S, consult)
    consult["step"] = max(1, min(consult["reached"], consult["step"] + delta))


def go_diagnosis(consult: dict) -> None:
    """'See diagnosis' button."""
    consult["step"] = 4
    consult["reached"] = max(consult["reached"], 4)


def toggle_adding(consult: dict) -> None:
    """'Add more symptoms' button."""
    consult["adding"] = not consult["adding"]


def submit_answer(kb: dict, consult: dict, question, option: str) -> None:
    """Answer button of the backward-chaining question."""
    answer = {"No": "no", "Yes": "yes"}.get(option, option)
    hyb = consult["hyb"]
    step = apply_answer(kb, hyb["known"], hyb["denied"], question, answer)
    hyb["steps"].append(step)
    hyb["result"] = step.result_after
    consult["reached"] = 3


def replay(consult: dict, name: str) -> None:
    """Replay: forget that a block was played and remount it (new container key)."""
    consult["played"].discard(name)
    consult["nonce"][name] = consult["nonce"].get(name, 0) + 1


# ------------------------------------------------------------------ top bar

def render_topbar(kb: dict, S) -> str:
    """One compact bar: logo | back, 4-step strip, forward | view switch, new consultation."""
    consult = S["consult"]
    step = consult["step"] if consult else 1
    reached = consult["reached"] if consult else 1
    can_forward = consult is not None and step < reached and not (
        step == 2 and severity_dirty(kb, S, consult))
    with st.container(key="topbar"):
        left, centre, right = st.columns([3, 6.2, 3.6], vertical_alignment="center")
        left.markdown(brand_html(), unsafe_allow_html=True)
        back, strip, forward = centre.columns([1.1, 8, 1.1], vertical_alignment="center")
        back.button(":material/arrow_back:", key="nav_back", help="Back", disabled=step <= 1,
                    on_click=go, args=(kb, S, -1), use_container_width=True)
        strip.markdown(steps_html(step), unsafe_allow_html=True)
        forward.button(":material/arrow_forward:", key="nav_forward", help="Forward",
                       disabled=not can_forward, on_click=go, args=(kb, S, 1),
                       use_container_width=True)
        switch, new = right.columns([6, 1.2], vertical_alignment="center")
        view = switch.segmented_control("View", VIEWS, key="view",
                                        label_visibility="collapsed") or VIEWS[0]
        new.button(":material/restart_alt:", key="new_consultation", help="New consultation",
                   on_click=new_consultation, args=(S,), use_container_width=True)
    return view


# ----------------------------------------------------------- step 1 and 2

def symptom_chips(kb: dict, key: str, button: str, replace: bool, S, with_button: bool = True) -> None:
    """Large chip group of every KB symptom, plus a primary button unless with_button is False."""
    st.pills("Symptoms", list(kb["symptoms"]), selection_mode="multi", key=key,
             format_func=lambda sid: kb["symptoms"][sid]["label"], label_visibility="collapsed")
    if with_button:
        st.button(button, type="primary", key=f"{key}-go", on_click=merge_picked,
                  args=(kb, S, key, replace))


def render_step1(kb: dict, S, consult: dict | None) -> None:
    """Step 1: chips on the left, 'Or type it' card on the right."""
    msg = consult["msg"] if consult else ""
    if consult and "ask_pills" not in S:
        S["ask_pills"] = list(consult["symptoms"])
    with st.container(key="grow"):
        left, right = st.columns([3, 2])
    with left:
        st.markdown('<div class="h-big">What are you feeling?</div>', unsafe_allow_html=True)
        if msg == "nomatch":
            phrases = ", ".join(f"'{p}'" for p in consult["unknown"]) or "that"
            st.markdown(f'<div class="muted-card">I couldn\'t match {esc(phrases)}. I work from '
                        f'symptoms (what you feel), not disease names. Try \'fever\' or '
                        f'\'sore throat\', or tap below.</div>', unsafe_allow_html=True)
        elif msg == "empty":
            st.markdown('<div class="muted-card">Tap at least one symptom, or type how you feel.</div>',
                        unsafe_allow_html=True)
        symptom_chips(kb, "ask_pills", "Continue", True, S, with_button=False)
    with right:
        with st.container(key="card-type"):
            st.markdown('<div class="h-big" style="font-size:26px">Or type it</div>',
                        unsafe_allow_html=True)
            st.caption("English or Roman Urdu. Use the box at the bottom, or tap an example:")
            for i, text in enumerate(EXAMPLES):
                st.button(text, key=f"ex{i}", on_click=start_from_text, args=(kb, S, text),
                          use_container_width=True)
    with st.container(key="bar"):
        st.button("Continue", type="primary", key="ask_pills-go", on_click=merge_picked,
                  args=(kb, S, "ask_pills", True))


def render_step2(kb: dict, S, consult: dict) -> None:
    """Step 2: one card per symptom with Mild | Moderate | Severe; side card for the rest."""
    levels = intensity_levels(kb)
    for sid, value in consult["symptoms"].items():
        if kb["symptoms"][sid]["input"] == "intensity":
            S.setdefault(f"sev_{sid}", value)
    with st.container(key="grow"):
        grid, side = st.columns([3, 1])
    with grid:
        st.markdown('<div class="h-big">How severe is each symptom?</div>', unsafe_allow_html=True)
        ids = list(consult["symptoms"])
        for start in range(0, len(ids), 3):
            for col, sid in zip(st.columns(3), ids[start:start + 3]):
                symptom = kb["symptoms"][sid]
                with col.container(key=f"card-sev-{sid}"):
                    name = esc(symptom["label"])
                    if sid in consult["read_from"]:
                        name += f' <span class="small">(read from \'{esc(consult["read_from"][sid])}\')</span>'
                    st.markdown(f"<b>{name}</b>", unsafe_allow_html=True)
                    if symptom["input"] == "intensity":
                        st.segmented_control(symptom["label"], levels, key=f"sev_{sid}",
                                             format_func=str.capitalize, label_visibility="collapsed")
                        if sid in consult["defaulted"]:
                            st.caption("default (not stated)")
                    else:
                        st.markdown(chip("present"), unsafe_allow_html=True)
    with side:
        with st.container(key="card-side"):
            if consult["text"]:
                st.caption("You said:")
                st.text(consult["text"])
            if consult["negated"]:
                st.markdown("<b>Ruled out</b>", unsafe_allow_html=True)
                st.markdown("".join(
                    f'<span class="chip out"><s>{esc(kb["symptoms"][s]["label"])}</s></span> '
                    for s in consult["negated"]), unsafe_allow_html=True)
            if consult["unknown"]:
                st.markdown("<b>Not in my knowledge base</b>", unsafe_allow_html=True)
                st.markdown(esc(", ".join(consult["unknown"])))
            if consult["read_from"]:
                st.markdown("<b>Read from your words</b>", unsafe_allow_html=True)
                for sid, word in consult["read_from"].items():
                    st.markdown(f'{esc(kb["symptoms"][sid]["label"])} <span class="small">'
                                f"(read from '{esc(word)}')</span>", unsafe_allow_html=True)
            if not (consult["negated"] or consult["unknown"] or consult["read_from"]):
                st.caption("Nothing was ruled out or unclear.")
    with st.container(key="bar"):
        if consult["adding"]:
            symptom_chips(kb, "add_pills", "Add selected", False, S)
        first, second, _ = st.columns([2, 2, 5])
        first.button("Diagnose", type="primary", key="diagnose", on_click=do_diagnose, args=(kb, S),
                     use_container_width=True)
        second.button("Add more symptoms", key="add_more", on_click=toggle_adding, args=(consult,),
                      use_container_width=True)


# ------------------------------------------------------------ result helpers

def supporting_symptoms(kb: dict, result, fact: str) -> list[str]:
    """Reported symptoms behind a fact, read from the firing trace."""
    by_fact: dict[str, list] = {}
    for firing in result.trace:
        if firing.concluded_fact:
            by_fact.setdefault(firing.concluded_fact, []).append(firing)
    found: list[str] = []

    def walk(item: str) -> None:
        """Collect root symptoms below one fact."""
        for firing in by_fact.get(item, []):
            for premise in firing.premises:
                if premise in kb["symptoms"]:
                    if premise not in found:
                        found.append(premise)
                else:
                    walk(premise)

    walk(fact)
    return found


def contributing_firings(result, disease_id: str) -> list:
    """The latest firing of every rule that contributed to a disease, in firing order."""
    latest = {f.rule_id: f for f in result.trace if f.concluded_fact}
    by_fact: dict[str, list] = {}
    for firing in latest.values():
        by_fact.setdefault(firing.concluded_fact, []).append(firing)
    chosen: dict[str, object] = {}

    def walk(fact: str) -> None:
        """Follow the premises of the rules that concluded a fact."""
        for firing in by_fact.get(fact, []):
            if firing.rule_id not in chosen:
                chosen[firing.rule_id] = firing
                for premise in firing.premises:
                    walk(premise)

    walk(disease_id)
    return sorted(chosen.values(), key=lambda f: f.cycle)


def rule_line(kb: dict, f) -> str:
    """'R5 · <premises joined by +> → <fact> (<contribution>)'."""
    prem = " + ".join(display_name(kb, p) for p in f.premises)
    return f"{f.rule_id} · {prem} → {display_name(kb, f.concluded_fact)} ({fmt(f.contribution, 2)})"


def alert_html(kb: dict, alert: dict) -> str:
    """Red banner for a fired red flag: its name (rule id + conditions) and the KB advice."""
    flag = next(f for f in kb["red_flags"] if f["id"] == alert["id"])
    name = " + ".join(display_name(kb, p) for p in flag["if"])
    return (f'<div class="alert" role="alert"><b>RED FLAG · {esc(alert["id"])} · {esc(name)}'
            f'</b> — {esc(alert["message"])}</div>')


@dataclass
class Panel:
    """HTML of an animated panel and the time it needs to finish."""
    html: str
    total: float


def gap_for(steps: int) -> float:
    """Delay between steps so the whole panel takes at most MAX_CHAIN_SECONDS."""
    gap = min(MAX_GAP_SECONDS, MAX_CHAIN_SECONDS / max(steps, 1))
    return int(gap * 1000) / 1000     # round DOWN so gap * steps never exceeds the limit


def chain_div(kind: str, rows: list, consult: dict, name: str, static: bool,
              head: str = "") -> Panel:
    """Wrap rows into an animated chain: --i per step, --gap, --total, a slim progress bar."""
    gap = gap_for(len(rows))
    total = gap * len(rows) + ANIM_SECONDS
    nonce = consult["nonce"].get(name, 0)
    body = "".join(f'<div class="step {css}" style="--i:{i}">{row}</div>'
                   for i, (row, css) in enumerate(rows))
    cls = "static" if static else "play"
    return Panel(f'{head}<div class="chain {kind} {cls} r{nonce}" style="--gap:{gap:.3f}s;--total:{total:.2f}s">'
                 f'<!--replay {nonce}--><div class="pbar"><span></span></div>{body}</div>', total)


def forward_panel(kb: dict, consult: dict, result, static: bool) -> Panel:
    """Forward chaining: FACTS -> (RULE FIRES, NEW FACT)* -> RESULT, one step at a time."""
    evidence = "".join(chip(kb["symptoms"][s]["label"] + (
        f" · {v}" if kb["symptoms"][s]["input"] == "intensity" else ""))
        for s, v in consult["symptoms"].items())
    ruled_out = "".join(f'<span class="chip out"><s>{esc(kb["symptoms"][s]["label"])}</s> ruled out</span>'
                        for s in consult["negated"])
    rows = [(f'{tag("FACTS")}{evidence}{ruled_out}', "facts")]
    produced: dict[str, str] = {}
    for f in result.trace:
        prem = []
        for p in f.premises:
            if p in kb["symptoms"]:
                prem.append(chip(kb["symptoms"][p]["label"]))
            else:
                prem.append(f'<span class="chip derived">{esc(display_name(kb, p))}'
                            f'<span class="tag">↳{esc(produced.get(p, ""))}</span></span>')
        if f.kind == "red_flag":
            ending = f'{tag("ALERT")}{chip("EMERGENCY", "danger glow")}'
        else:
            produced[f.concluded_fact] = f.rule_id
            ending = (f'{tag("NEW FACT")}'
                      f'{chip(display_name(kb, f.concluded_fact) + " " + fmt(f.cf_after, 2), "ok glow")}')
        rows.append((f'{tag("RULE FIRES")}{"".join(prem)}<span class="rbadge">{esc(f.rule_id)}</span>'
                     f'<span class="arrow">→</span>{ending}'
                     f'<div class="cap">matched {esc(", ".join(f.conflict_set))} → fired {esc(f.rule_id)}</div>',
                     "fires"))
    final = "".join(chip(f"{d.name} {fmt(d.cf, 2)}", "ok") for d in result.diseases)
    rows.append((f'{tag("RESULT")}{final or "no condition reached the threshold"}', "result"))
    head = ('<div class="pf"><div class="pheader">FORWARD CHAINING ▶'
            '<span>from facts to conclusions</span></div></div>')
    return chain_div("pf", rows, consult, "chain", static, head)


def backward_panel(kb: dict, consult: dict, step, previous, name: str, static: bool) -> Panel:
    """One answered question: GOAL -> NEEDS -> ASK -> YOU SAID -> PROVEN / NOT PROVEN."""
    q = step.question
    rules = {r["id"]: r for r in kb["rules"]}
    threshold = kb["meta"]["cf_conventions"]["rule_fire_threshold"]
    rows = [(f'{tag("GOAL")}{esc(q.path[0])}?', "goal")]
    for part in q.path[1:]:
        rule_id, target = part.split(" needs ", 1)
        items = []
        for premise in rules[rule_id]["if"]:
            label = display_name(kb, premise)
            known = previous.working_memory.get(premise, 0.0) >= threshold and label != target
            items.append(f"{esc(label)} {'✓ known' if known else '?'}")
        rows.append((f'{tag("NEEDS")}<span class="rbadge">{esc(rule_id)}</span> {", ".join(items)}', "needs"))
    rows.append((f'{tag("ASK")}{esc(q.label)}?', "ask"))
    said = {"no": "No", "yes": "Yes"}.get(step.answer, step.answer.capitalize())
    rows.append((f'{tag("YOU SAID")}{chip(said, "no" if step.answer == "no" else "ok")}', "answer"))
    if step.answer == "no":
        rows.append((f'{tag("NOT PROVEN ✗", "fail")}{esc(q.label)}: No — this path cannot support '
                     f'{esc(display_name(kb, q.goal))}.', "proof fail"))
    else:
        for part in reversed(q.path[1:]):
            fact = rules[part.split(" needs ", 1)[0]]["then"]
            after = step.result_after.working_memory.get(fact, 0.0)
            if fact == q.goal:
                before = previous.working_memory.get(fact, 0.0)
                arrow = "↑" if after > before + 1e-9 else "→"
                rows.append((f'{tag("PROVEN ✓")}{arrow} <b>{esc(display_name(kb, fact))} {fmt(after, 2)}</b>', "proof"))
            else:
                rows.append((f'{tag("PROVEN ✓")}↑ {esc(display_name(kb, fact))} ✓ ({fmt(after, 2)})', "proof"))
    return chain_div("pb", rows, consult, name, static)


def panel_block(consult: dict, name: str, panel: Panel, key_part: str) -> None:
    """Render a panel in a container whose key changes on Replay (a new key remounts it)."""
    cid = consult["id"]
    nonce = consult["nonce"].get(name, 0)
    with st.container(key=f"{cid}-{key_part}-r{nonce}"):
        st.markdown(panel.html, unsafe_allow_html=True)
    st.button(":material/replay: Replay", key=f"{cid}-replay-{name}", help="Replay the animation",
              on_click=replay, args=(consult, name))


# --------------------------------------------------------------- step 3

def render_question(kb: dict, consult: dict) -> None:
    """Right column: the close-call question (or why backward chaining is not needed)."""
    cid, hyb = consult["id"], consult["hyb"]
    call = close_call(hyb["initial"])
    if call is None:
        gap = top_two_gap(hyb["initial"])
        why = (f"the top condition is clearly ahead (gap {fmt(gap, 1)}% > {CLOSE_MARGIN:g}%)"
               if gap is not None else "fewer than two conditions reached the threshold")
        st.markdown(f'<div class="muted-card">Backward chaining not needed: {esc(why)}.</div>',
                    unsafe_allow_html=True)
        return
    versus = (f"{call.first.name} {fmt(call.first.percent, 1)}% vs "
              f"{call.second.name} {fmt(call.second.percent, 1)}% "
              f"(gap {fmt(call.gap, 1)} <= {CLOSE_MARGIN:g})")
    asked = len(hyb["steps"])
    question, outcome = next_step(kb, hyb["result"], hyb["known"], hyb["denied"], asked)
    if asked == 0 and question is None:
        st.warning(f"Close call: {versus}. Every symptom that could separate them has "
                   f"already been reported, so backward chaining has nothing to ask.")
    elif asked > 0:
        st.warning(f"Close call at the start: {versus}. Backward chaining asked {asked} question(s).")
    if question is None:
        show = st.success if outcome == "separated" else st.info
        show("Outcome: " + OUTCOME_TEXT[outcome])
        return
    with st.container(key=f"card-question-{cid}"):
        st.markdown(f"**Close call: {esc(call.first.name)} vs {esc(call.second.name)}. "
                    f"One question to settle it.**")
        st.markdown(f"Do you have **{esc(question.label.lower())}**?")
        st.caption(why_asking(question))
        options = ["No"] + (intensity_levels(kb) if question.input_type == "intensity" else ["Yes"])
        for col, (i, option) in zip(st.columns(len(options)), enumerate(options)):
            col.button(option.capitalize(), key=f"ans_{cid}_{asked}_{i}", on_click=submit_answer,
                       args=(kb, consult, question, option), use_container_width=True)


def render_step3(kb: dict, S, consult: dict) -> None:
    """Step 3: forward chaining (blue, left) and backward chaining (violet, right)."""
    hyb, played, cid = consult["hyb"], consult["played"], consult["id"]
    chain = forward_panel(kb, consult, hyb["result"], static="chain" in played)
    panels, previous = [], hyb["initial"]
    for k, step in enumerate(hyb["steps"]):
        name = f"bw{k}"
        panels.append((name, backward_panel(kb, consult, step, previous, name, name in played)))
        previous = step.result_after
    with st.container(key="grow"):
        left, right = st.columns(2)
    with left:
        with st.container(key=f"col-f-{cid}"):
            panel_block(consult, "chain", chain, "fchain")
            with st.expander("Engine details"):
                st.dataframe([{
                    "Cycle": f.cycle, "Conflict set": ", ".join(f.conflict_set), "Fired": f.rule_id,
                    "Kind": f.kind,
                    "Concluded": display_name(kb, f.concluded_fact) if f.concluded_fact else "-",
                    "CF before": fmt(f.cf_before, 3) if f.cf_before is not None else "-",
                    "CF after": fmt(f.cf_after, 3) if f.cf_after is not None else "-",
                    "Re-fire": "yes" if f.refire else "no"} for f in hyb["result"].trace],
                    hide_index=True, width="stretch")
    with right:
        with st.container(key=f"col-b-{cid}"):
            st.markdown('<div class="pb"><div class="pheader">BACKWARD CHAINING ◀'
                        '<span>from a goal back to facts</span></div></div>', unsafe_allow_html=True)
            if panels:
                name, panel = panels[-1]
                panel_block(consult, name, panel, name)
            render_question(kb, consult)
            for name, panel in reversed(panels[:-1]):
                panel_block(consult, name, panel, name)
    with st.container(key="bar"):
        st.button("See diagnosis", type="primary", key="see_diagnosis", on_click=go_diagnosis,
                  args=(consult,))
    consult["played"] |= {"chain", *[name for name, _ in panels]}


# --------------------------------------------------------------- step 4

def card_html(kb: dict, rank: int, disease, tied: bool, animate: bool) -> str:
    """Compact disease card: rank, name, severity pill, 48px confidence, bar, evidence strength."""
    sev = kb["meta"]["severity_rank"][disease.severity]
    width = min(max(disease.percent, 0.0), 100.0)
    tag_html = '<span class="tied">tied</span>' if tied else ""
    return (f'<div class="card{" fade" if animate else ""}"><div class="top"><div>'
            f'<span class="rank">#{rank}</span><span class="name">{esc(disease.name)}</span>{tag_html}'
            f'</div><span class="pill sev{sev}">{esc(disease.severity.capitalize())}</span></div>'
            f'<div class="big">{fmt(disease.percent, 1)}% <span class="small">confidence</span></div>'
            f'<div class="bar sev{sev}"><span style="width:{width:.1f}%"></span></div>'
            f'<div class="small">Evidence strength {fmt(disease.cf, 2)} (CF)</div></div>')


def render_panel(kb: dict, result, disease, choice: str) -> None:
    """The panel chosen with the card's segmented control (Why / Treatment / Prevention)."""
    if choice == "Why this?":
        labels = [kb["symptoms"][s]["label"] for s in supporting_symptoms(kb, result, disease.disease_id)]
        lines = [rule_line(kb, f) for f in contributing_firings(result, disease.disease_id)]
        items = "".join(f"<li>{esc(line)}</li>" for line in lines)
        st.markdown(f'<div class="panel">Suggested because you reported {esc(", ".join(labels))}.'
                    f'<ul class="why">{items}</ul><b>Combined certainty '
                    f'{fmt(result.working_memory[disease.disease_id], 2)}</b></div>',
                    unsafe_allow_html=True)
    else:
        items = disease.treatment if choice == "Treatment" else disease.prevention
        st.markdown(f'<div class="panel"><b>{esc(choice)}</b><ul>'
                    + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul></div>",
                    unsafe_allow_html=True)


def verdict_html(kb: dict, result) -> str:
    """Big verdict banner: label, disease name, confidence, severity pill, 'Because' line."""
    top = result.diseases[0]
    tied = [d for d in result.diseases if abs(d.cf - top.cf) < 1e-9]
    if len(tied) > 1:
        name = join_names([d.name for d in tied])
        conf = f"equally likely · {fmt(top.percent, 1)}% each"
        pill = ""
    else:
        name = top.name
        conf = f"{fmt(top.percent, 1)}%"
        pill = f'<span class="vsev">{esc(top.severity.capitalize())}</span>'
    because = ", ".join(kb["symptoms"][s]["label"] for s in supporting_symptoms(kb, result, top.disease_id))
    sub = f"Because: {because}." if because else ""
    if any(d.cf > top.cf + 1e-9 for d in result.diseases[1:]):
        sub += " " + PRIORITY_LINE
    return (f'<div class="verdict"><div class="lbl">MOST LIKELY</div><div class="row">'
            f'<span class="vname">{esc(name)}</span><span class="vconf">{esc(conf)}</span>{pill}</div>'
            f'<div class="sub">{esc(sub)}</div></div>')


def tiers_of(result) -> list:
    """Group the engine's ordered diseases into consecutive severity tiers."""
    tiers: list = []
    for disease in result.diseases:
        if tiers and tiers[-1][0].severity == disease.severity:
            tiers[-1].append(disease)
        else:
            tiers.append([disease])
    return tiers


def render_step4(kb: dict, S, consult: dict) -> None:
    """Step 4: banners on top, then the conditions grouped by priority tier."""
    cid, played = consult["id"], consult["played"]
    result = consult["hyb"]["result"]
    version = len(consult["hyb"]["steps"])
    animate = f"dx{version}" not in played
    for alert in result.alerts:
        st.markdown(alert_html(kb, alert), unsafe_allow_html=True)
    if not result.diseases:
        st.markdown('<div class="verdict none"><div class="lbl">RESULT</div><div class="row">'
                    '<span class="vname">Not enough evidence to name a condition</span></div></div>',
                    unsafe_allow_html=True)
        st.info(no_diagnosis_message(kb))
        for hint in required_hints(result):
            st.info(hint)
        if result.below_threshold:
            st.info(below_threshold_text(result))
        symptom_chips(kb, f"{cid}-nodx-pills", "Add selected symptoms", False, S)
    else:
        st.markdown(verdict_html(kb, result), unsafe_allow_html=True)
        if result.below_threshold:
            st.info(below_threshold_text(result))
        tiers = tiers_of(result)
        rank = 0
        with st.container(key="grow"):
            columns = st.columns([len(t) for t in tiers])
        for number, (column, tier) in enumerate(zip(columns, tiers), 1):
            with column:
                st.markdown(f'<div class="tier">Priority {number} · '
                            f'{esc(tier[0].severity.capitalize())} conditions</div>', unsafe_allow_html=True)
                for start in range(0, len(tier), 3):
                    chunk = tier[start:start + 3]
                    for col, disease in zip(st.columns(len(chunk)), chunk):
                        rank += 1
                        tied = any(o is not disease and abs(o.cf - disease.cf) < 1e-9 for o in result.diseases)
                        with col:
                            st.markdown(card_html(kb, rank, disease, tied, animate), unsafe_allow_html=True)
                            choice = st.segmented_control(
                                "Details", SHOW_OPTIONS, key=f"{cid}-tab-{disease.disease_id}",
                                label_visibility="collapsed")
                            if choice:
                                render_panel(kb, result, disease, choice)
        st.caption(TIER_CAPTION + " " + CONFIDENCE_NOTE)
    with st.container(key="bar"):
        first, second, _ = st.columns([2, 2, 5])
        first.button("Edit symptoms", key="edit_symptoms", on_click=goto_severity, args=(S, consult),
                     use_container_width=True)
        second.button("New consultation", key="new_consultation_bottom", on_click=new_consultation,
                      args=(S,), use_container_width=True)
    consult["played"].add(f"dx{version}")


# ---------------------------------------------------------------- wizard

def render_wizard(kb: dict, S) -> None:
    """Draw the current step."""
    consult = S["consult"]
    step = consult["step"] if consult else 1
    with st.container(key="stage"):
        if step == 1:
            render_step1(kb, S, consult)
        elif step == 2:
            render_step2(kb, S, consult)
        elif step == 3:
            render_step3(kb, S, consult)
        else:
            render_step4(kb, S, consult)


# ---------------------------------------------------- knowledge-base view

def root_symptoms(kb: dict, disease_id: str) -> list:
    """Root symptoms of a disease: walk its rule premises through intermediate facts."""
    roots: list = []
    for rule in rules_supporting(kb, disease_id):
        for premise in rule["if"]:
            if premise in kb["symptoms"] and premise not in roots:
                roots.append(premise)
    return roots


def chain_lines(kb: dict, disease_id: str) -> list:
    """'IF a AND b THEN fact (CF) → ... → Disease' for every rule that leads to a disease."""
    rules = rules_supporting(kb, disease_id)
    uses: dict[str, dict] = {}
    for rule in rules:
        for premise in rule["if"]:
            if premise not in kb["symptoms"]:
                uses.setdefault(premise, rule)
    lines = []
    for rule in rules:
        tail, fact = [], rule["then"]
        while fact != disease_id and fact in uses:
            fact = uses[fact]["then"]
            tail.append(display_name(kb, fact))
        text = (f"IF {' AND '.join(display_name(kb, p) for p in rule['if'])} "
                f"THEN {display_name(kb, rule['then'])} ({fmt(rule['cf'], 2)})")
        lines.append(text + "".join(f" → {t}" for t in tail))
    return lines


def more(items: list, shown: int = 3) -> str:
    """First bullets as HTML list items plus '+N more'."""
    out = "".join(f"<li>{esc(i)}</li>" for i in items[:shown])
    if len(items) > shown:
        out += f'<li class="small">+{len(items) - shown} more</li>'
    return out


def showcase_card(kb: dict, disease_id: str, levels: list) -> str:
    """One 'example per severity level' card, built only from the knowledge base."""
    disease = kb["diseases"][disease_id]
    sev = kb["meta"]["severity_rank"][disease["severity"]]
    words = "/".join(levels)
    roots = root_symptoms(kb, disease_id)
    chips = "".join(chip(kb["symptoms"][s]["label"] + " · " + (
        words if kb["symptoms"][s]["input"] == "intensity" else "present")) for s in roots)
    rules = "".join(f"<li>{esc(line)}</li>" for line in chain_lines(kb, disease_id))
    flags = [f for f in kb["red_flags"] if set(f["if"]) <= set(roots)]
    flag_html = "".join(f'<div class="alert" style="font-size:max(15px,.68rem);padding:.25rem .7rem;margin:.25rem 0">'
                        f'<b>{esc(f["id"])}</b> {esc(f["message"])}</div>' for f in flags)
    small_list = 'style="font-size:max(15px,.68rem);margin:.1rem 0;padding-left:1.1rem"'
    return (f'<div class="card kbcard"><div class="top"><span class="name">{esc(disease["name"])}</span>'
            f'<span class="pill sev{sev}">{esc(disease["severity"].capitalize())}</span></div>'
            f'<div class="small">Symptoms used</div><div class="chips">{chips}</div>'
            f'<div class="small">Rules that lead to it</div><ul {small_list}>{rules}</ul>{flag_html}'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem">'
            f'<div><b>Treatment</b><ul {small_list}>{more(disease["treatment"])}</ul></div>'
            f'<div><b>Prevention</b><ul {small_list}>{more(disease["prevention"])}</ul></div></div></div>')


def kb_tiles(kb: dict, stats: dict) -> list:
    """(key, title, value line) for the five requirement tiles, all computed from the KB."""
    n_sym, n_dis = stats["symptoms"], stats["diseases"]

    def tick(ok: bool) -> str:
        """A green tick when a requirement is met."""
        return " ✓" if ok else ""

    ranks = kb["meta"]["severity_rank"]
    levels = " · ".join(s.capitalize() for s in sorted(ranks, key=ranks.get))
    complete = sum(bool(d["treatment"]) and bool(d["prevention"]) for d in kb["diseases"].values())
    return [
        ("symptoms", "Symptoms", f"{n_sym} (min {REQUIREMENTS['symptoms']}-10){tick(n_sym >= REQUIREMENTS['symptoms'])}"),
        ("diseases", "Diseases", f"{n_dis} (min {REQUIREMENTS['diseases']}-4){tick(n_dis >= REQUIREMENTS['diseases'])}"),
        ("rules", "Rules", f"{len(kb['rules'])} rules + {len(kb['red_flags'])} red flags (symptom-disease relationships)"),
        ("severity", "Severity levels", f"{levels} (weights from the KB)"),
        ("treatments", "Treatments", f"all diseases have treatment + prevention{tick(complete == n_dis)}"
         if complete == n_dis else f"{complete} of {n_dis} diseases have treatment + prevention"),
    ]


def tile_table(kb: dict, key: str) -> list:
    """Compact table behind a selected tile."""
    if key == "symptoms":
        return [{"Symptom": s["label"], "Input": s["input"]} for s in kb["symptoms"].values()]
    if key == "diseases":
        return [{"Disease": d["name"], "Severity": d["severity"], "Sources": ", ".join(d["sources"])}
                for d in kb["diseases"].values()]
    if key == "rules":
        return [{"Rule": r["id"], "IF": " AND ".join(display_name(kb, p) for p in r["if"]),
                 "THEN": display_name(kb, r["then"]), "CF": fmt(r["cf"], 2)} for r in kb["rules"]]
    if key == "severity":
        weights = kb["meta"]["cf_conventions"]["intensity_cf"]
        return [{"Symptom strength": k, "Weight": str(w)} for k, w in weights.items()] + [
            {"Symptom strength": f"disease: {k}", "Weight": f"rank {v}"}
            for k, v in kb["meta"]["severity_rank"].items()]
    return [{"Disease": d["name"], "Treatment items": len(d["treatment"]),
             "Prevention items": len(d["prevention"])} for d in kb["diseases"].values()]


def select_tile(S, key: str) -> None:
    """Callback of a tile button (click again to close)."""
    S["kb_tile"] = None if S.get("kb_tile") == key else key


def render_kb_view(kb: dict, S, stats: dict) -> None:
    """Read-only knowledge-base view, drawn inside a stage that fills the window."""
    with st.container(key="stage"):
        kb_body(kb, S, stats)


def kb_body(kb: dict, S, stats: dict) -> None:
    """Tiles, one example per severity level, the strength strip and the full-KB expander."""
    ranks = kb["meta"]["severity_rank"]
    expected = sorted(ranks, key=ranks.get, reverse=True)
    shown = [kb["diseases"][d]["severity"] for d in KB_SHOWCASE]
    if shown != expected:
        st.error(f"KB_SHOWCASE must be ordered {expected}, got {shown}")
        return
    tiles = kb_tiles(kb, stats)
    for column, (key, title, value) in zip(st.columns(len(tiles)), tiles):
        with column:
            st.button(f"**{title}**  {chr(10)}{value}", key=f"kbtile-{key}", on_click=select_tile,
                      args=(S, key), use_container_width=True, help="Show the table")
    st.markdown('<div class="h-big" style="font-size:1.4rem">One example per severity level</div>',
                unsafe_allow_html=True)
    levels = intensity_levels(kb)
    with st.container(key="grow"):
        example_columns = st.columns(3)
    for column, did in zip(example_columns, KB_SHOWCASE):
        column.markdown(showcase_card(kb, did, levels), unsafe_allow_html=True)
    weights = kb["meta"]["cf_conventions"]["intensity_cf"]
    strength = " · ".join(f"{k.capitalize()} {w:g}" for k, w in weights.items() if k != "yes")
    st.markdown(f'<div class="strip">{esc(strength)} → symptom strength. '
                f'Disease severity decides ranking.</div>', unsafe_allow_html=True)
    if S.get("kb_tile"):
        st.dataframe(tile_table(kb, S["kb_tile"]), hide_index=True, width="stretch")
    with st.expander("Show the full knowledge base"):
        st.caption(f"Version {kb['meta']['version']} · {stats['diseases']} diseases · "
                   f"{stats['symptoms']} symptoms · {stats['intermediate_facts']} intermediate facts · "
                   f"{stats['rules']} rules")
        st.markdown("**Symptoms**")
        for symptom in kb["symptoms"].values():
            st.markdown(f"- **{symptom['label']}**: {', '.join(symptom['synonyms'])}")
        st.markdown("**Rules**")
        query = st.text_input("Search rules", key="kb_search").strip().lower()
        for rule in kb["rules"]:
            line = (f"{rule['id']} · {' AND '.join(display_name(kb, p) for p in rule['if'])} "
                    f"→ {display_name(kb, rule['then'])}, CF {fmt(rule['cf'], 2)}")
            if query in line.lower():
                st.markdown(f"- {line}")
        st.markdown("**Red flags**")
        for flag in kb["red_flags"]:
            st.markdown(f"- {flag['id']} · {' AND '.join(display_name(kb, p) for p in flag['if'])}: "
                        f"{flag['message']}")
        st.markdown("**Sources**")
        for source in kb["meta"]["sources"]:
            st.markdown(f"- {source['name']}")
        st.caption(kb["meta"]["disclaimer"])


def render_footer() -> None:
    """One small line at the bottom of the page."""
    st.markdown(f'<div class="footer">{esc(FOOTER)}</div>', unsafe_allow_html=True)
