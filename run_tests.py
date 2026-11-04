"""Test runner: python run_tests.py [--verbose]

Nine sections, each printed as an ASCII table:
  [1] KB verification            - the knowledge base passes all 8 consistency checks
  [2] Clinical cases             - cases written from WHO/CDC descriptions (tests/cases.json)
  [3] Regression                 - exact CFs from the design check (tests/regression.json)
  [4] CLI input parsing          - separators, synonyms and "did you mean"
  [5] Verifier self-tests        - the verifier catches deliberately broken KBs (in memory only)
  [6] Order independence         - shuffling rule order never changes the result
  [7] Hybrid backward chaining   - questions are generated from rules and settle close calls
  [8] GUI smoke tests            - the chat app runs headless (skipped if streamlit is not installed)
  [9] Text parser                - free-text sentences become engine input

A failing test is a finding about the knowledge base, not something to hide.
Exit code is 1 if anything fails.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from pathlib import Path

from expert_system.backward import close_call, find_questions, run_session
from expert_system.cli import print_result, print_table, print_trace, resolve_symptom, split_entries
from expert_system.engine import DiagnosisResult, diagnose, fmt
from expert_system.kb_verify import load_kb, verify_kb

ROOT = Path(__file__).resolve().parent
CF_TOLERANCE = 0.001      # allowed difference for expected CFs
PERCENT_TOLERANCE = 0.05
SEEDS = range(50)         # fixed seeds for the shuffle test


def load_json(name: str):
    """Read a JSON file from the tests folder (utf-8)."""
    with open(ROOT / "tests" / name, "r", encoding="utf-8") as f:
        return json.load(f)


def pass_fail(problems: list[str]) -> str:
    """'PASS' when there are no problems, else 'FAIL'."""
    return "FAIL" if problems else "PASS"


def actual_text(result: DiagnosisResult, dp: int = 2) -> str:
    """One-line summary of a result: shown diseases with CF, alerts, extras."""
    shown = ", ".join(f"{d.disease_id} {fmt(d.cf, dp)}" for d in result.diseases) or "none shown"
    alerts = ",".join(a["id"] for a in result.alerts) or "none"
    text = f"{shown} | alerts: {alerts}"
    if result.below_threshold:
        text += " | below: " + ", ".join(
            f"{b['disease_id']} {fmt(b['cf'], 3)}" for b in result.below_threshold)
    if result.unknown_symptoms:
        text += " | unknown: " + ",".join(result.unknown_symptoms)
    return text


# ----------------------------------------------------------- [2] clinical cases

def expected_text(expect: dict) -> str:
    """Short readable form of an expectation dict."""
    parts = []
    for key, value in expect.items():
        if isinstance(value, list):
            parts.append(f"{key}=[{','.join(value)}]")
        elif value is True:
            parts.append(key)
        else:
            parts.append(f"{key}={value}")
    return "; ".join(parts)


def check_expect(expect: dict, result: DiagnosisResult) -> list[str]:
    """Compare a result with a clinical expectation; return the problems found."""
    problems = []
    shown = [d.disease_id for d in result.diseases]
    alert_ids = [a["id"] for a in result.alerts]
    if "most_likely" in expect:
        best = max(result.diseases, key=lambda d: d.cf).disease_id if result.diseases else None
        if best != expect["most_likely"]:
            problems.append(f"most likely is {best}, expected {expect['most_likely']}")
    if "first" in expect and shown[:1] != [expect["first"]]:
        problems.append(f"rank 1 is {shown[:1]}, expected {expect['first']}")
    for name in expect.get("shown_include", []):
        if name not in shown:
            problems.append(f"{name} should be shown but is not")
    for name in expect.get("shown_exclude", []):
        if name in shown:
            problems.append(f"{name} should not be shown but is")
    if "alerts" in expect and sorted(alert_ids) != sorted(expect["alerts"]):
        problems.append(f"alerts {alert_ids}, expected {expect['alerts']}")
    if "unknown" in expect and result.unknown_symptoms != expect["unknown"]:
        problems.append(f"unknown {result.unknown_symptoms}, expected {expect['unknown']}")
    if expect.get("none_shown") and shown:
        problems.append(f"no disease should be shown but got {shown}")
    weak = [b["disease_id"] for b in result.below_threshold]
    for name in expect.get("below_threshold_include", []):
        if name not in weak:
            problems.append(f"{name} should be below threshold but is not (below: {weak})")
    missing = [m["symptom_id"] for m in result.missing_required]
    for name in expect.get("missing_required_include", []):
        if name not in missing:
            problems.append(f"{name} should be reported as a missing required symptom (got {missing})")
    if expect.get("warning") and not result.warnings:
        problems.append("a warning was expected but none was given")
    return problems


def section_clinical(kb: dict):
    """Run tests/cases.json; return (rows, passed, total, failures)."""
    rows, failures, passed = [], [], 0
    cases = load_json("cases.json")
    for case in cases:
        result = diagnose(kb, case["input"])
        problems = check_expect(case["expect"], result)
        rows.append([case["id"], case["name"], expected_text(case["expect"]),
                     actual_text(result), pass_fail(problems)])
        if problems:
            failures.append((case["id"], case["input"], result, problems))
        else:
            passed += 1
    return rows, passed, len(cases), failures


# ------------------------------------------------------------- [3] regression

def check_regression(case: dict, result: DiagnosisResult) -> list[str]:
    """Compare a result with exact expected CFs, percents, alerts and extras."""
    problems = []
    got = [d.disease_id for d in result.diseases]
    want = [s["id"] for s in case["shown"]]
    if got != want:
        problems.append(f"shown {got}, expected {want}")
    else:
        for disease, expected in zip(result.diseases, case["shown"]):
            if abs(disease.cf - expected["cf"]) > CF_TOLERANCE:
                problems.append(f"{disease.disease_id} CF {fmt(disease.cf, 4)}, expected {expected['cf']}")
        for disease, percent in zip(result.diseases, case.get("percents", [])):
            if abs(disease.percent - percent) > PERCENT_TOLERANCE:
                problems.append(f"{disease.disease_id} {fmt(disease.percent, 1)}%, expected {percent}%")
    if [a["id"] for a in result.alerts] != case["alerts"]:
        problems.append(f"alerts {[a['id'] for a in result.alerts]}, expected {case['alerts']}")
    if result.unknown_symptoms != case["unknown"]:
        problems.append(f"unknown {result.unknown_symptoms}, expected {case['unknown']}")
    for name in case.get("not_concluded", []):
        if name in result.working_memory:
            problems.append(f"{name} should not be concluded at all")
    if "first_fired" in case:
        first = result.trace[0] if result.trace else None
        if first is None or first.rule_id != case["first_fired"] or first.cycle != 1:
            problems.append(f"{case['first_fired']} should fire in cycle 1")
    if "warnings_count" in case and len(result.warnings) != case["warnings_count"]:
        problems.append(f"{len(result.warnings)} warnings, expected {case['warnings_count']}")
    return problems


def section_regression(kb: dict):
    """Run tests/regression.json; return (rows, passed, total, failures)."""
    rows, failures, passed = [], [], 0
    cases = load_json("regression.json")
    for case in cases:
        result = diagnose(kb, case["input"])
        problems = check_regression(case, result)
        expected = ", ".join(f"{s['id']} {s['cf']}" for s in case["shown"]) or "none shown"
        rows.append([case["id"], case["name"], expected, actual_text(result, 4), pass_fail(problems)])
        if problems:
            failures.append((case["id"], case["input"], result, problems))
        else:
            passed += 1
    return rows, passed, len(cases), failures


# ------------------------------------------------------------ [4] CLI parsing

# (typed text, expected symptom ids in order). Ids appear here because these are tests.
PARSING_CASES = [
    ("bukhar aur sir dard, ulti & badan dard", ["fever", "headache", "nausea_vomiting", "body_aches"]),
    ("nausea or vomiting, fever", ["nausea_vomiting", "fever"]),
    ("khansi and runny nose", ["cough", "runny_nose"]),
]


def section_parsing(kb: dict):
    """Test split_entries + resolve_symptom; return (rows, passed, total, failures)."""
    rows, passed = [], 0
    for text, expected in PARSING_CASES:
        actual = [resolve_symptom(e, kb)[0] for e in split_entries(text, kb)]
        ok = actual == expected
        rows.append([text, ",".join(expected), ",".join(str(a) for a in actual), pass_fail([] if ok else ["x"])])
        passed += ok
    entries = split_entries("headche", kb)
    outcome = resolve_symptom(entries[0], kb) if len(entries) == 1 else None
    ok = outcome == (None, "headache")
    rows.append(["headche", "no match, suggest headache", f"{outcome}", pass_fail([] if ok else ["x"])])
    passed += ok
    return rows, passed, len(PARSING_CASES) + 1, []


# --------------------------------------------------------- [5] verifier self-tests

def section_verifier(kb: dict):
    """Break copies of the KB in memory and check the verifier notices."""
    broken_overcount = copy.deepcopy(kb)
    broken_overcount["rules"].append(
        {"id": "RX", "if": ["rash"], "then": "dengue_signs", "cf": 0.5, "priority": 30})
    broken_treatment = copy.deepcopy(kb)
    del broken_treatment["diseases"]["dengue"]["treatment"]
    broken_symptom = copy.deepcopy(kb)
    broken_symptom["rules"].append(
        {"id": "RY", "if": ["itching"], "then": "common_cold", "cf": 0.5, "priority": 10})
    checks = [
        ("Overcounting rule RX caught", broken_overcount, ["overcounting", "RX", "R4"]),
        ("Missing treatment caught", broken_treatment, ["dengue", "treatment"]),
        ("Unknown symptom caught", broken_symptom, ["itching", "RY"]),
    ]
    rows, passed = [], 0
    for label, bad_kb, words in checks:
        _, errors, _ = verify_kb(bad_kb)
        match = next((e for e in errors if all(w.lower() in e.lower() for w in words)), None)
        rows.append([label, "error naming " + ", ".join(words), match or "NOT CAUGHT",
                     pass_fail([] if match else ["x"])])
        passed += match is not None
    return rows, passed, len(checks), []


# ----------------------------------------------------------- [6] order independence

def signature(result: DiagnosisResult) -> tuple:
    """What must not change when rules are reordered: CFs, shown list, alerts."""
    return (result.working_memory, [d.disease_id for d in result.diseases],
            sorted(a["id"] for a in result.alerts))


def same_signature(a: tuple, b: tuple) -> bool:
    """Compare two signatures, allowing tiny floating-point differences."""
    if a[1] != b[1] or a[2] != b[2] or set(a[0]) != set(b[0]):
        return False
    return all(abs(a[0][k] - b[0][k]) < 1e-9 for k in a[0])


def section_order(kb: dict):
    """Shuffle rules/red flags with fixed seeds; every case must give identical CFs."""
    inputs = [c["input"] for c in load_json("cases.json")]
    inputs += [c["input"] for c in load_json("regression.json")]
    baseline = [signature(diagnose(kb, symptoms)) for symptoms in inputs]
    bad_seeds, passed = [], 0
    for seed in SEEDS:
        shuffled = copy.deepcopy(kb)
        rng = random.Random(seed)
        rng.shuffle(shuffled["rules"])
        rng.shuffle(shuffled["red_flags"])
        results = [signature(diagnose(shuffled, symptoms)) for symptoms in inputs]
        if all(same_signature(b, r) for b, r in zip(baseline, results)):
            passed += 1
        else:
            bad_seeds.append(seed)
    rows = [[f"{len(SEEDS)} seeds", f"{len(inputs)} cases each",
             f"mismatching seeds: {bad_seeds or 'none'}", pass_fail(bad_seeds)]]
    return rows, passed, len(SEEDS), []


# ------------------------------------------------------- [7] hybrid backward chaining

# Base close case: two diseases tie. Ids appear here because these are tests.
BASE_CLOSE = {"fever": "moderate", "headache": "moderate",
              "nausea_vomiting": "moderate", "body_aches": "moderate"}


def scripted(answers: dict):
    """Build an answer function that looks answers up by symptom id (None = stop)."""
    return lambda question: answers.get(question.symptom_id)


def case_input(case_id: str) -> dict:
    """Input of one clinical case from tests/cases.json."""
    return next(c["input"] for c in load_json("cases.json") if c["id"] == case_id)


def source_mentions_kb_names(kb: dict) -> list[str]:
    """KB disease/symptom ids, names and labels that appear in backward.py (should be none)."""
    text = (ROOT / "expert_system" / "backward.py").read_text(encoding="utf-8").lower()
    names = list(kb["diseases"]) + [d["name"] for d in kb["diseases"].values()]
    names += list(kb["symptoms"]) + [s["label"] for s in kb["symptoms"].values()]
    return sorted({n for n in names if n.lower() in text})


def section_hybrid(kb: dict):
    """Test close-call detection, generated questions and the question session."""
    rows, passed = [], 0

    def add(case_id: str, name: str, expected: str, actual: str, problems: list[str]) -> None:
        """Record one row and count it if it passed."""
        nonlocal passed
        rows.append([case_id, name, expected, actual, pass_fail(problems)])
        passed += not problems

    # H1: the base case is a close call; questions come from the rules.
    base = diagnose(kb, BASE_CLOSE)
    call = close_call(base)
    questions = find_questions(kb, base, BASE_CLOSE, set())
    ids = [q.symptom_id for q in questions[:3]]
    problems = []
    if call is None or {call.first.disease_id, call.second.disease_id} != {"dengue", "malaria"}:
        problems.append("expected a close call between dengue and malaria")
    elif call.gap > 0.05:
        problems.append(f"gap {fmt(call.gap, 1)}, expected 0.0")
    if ids != ["bleeding_gums", "chills", "sweating"]:
        problems.append(f"questions {ids}")
    elif not all(r in " ".join(questions[0].path) for r in ("R7", "R6")):
        problems.append(f"first path {questions[0].path}")
    add("H1", "Close call + generated questions", "dengue~malaria gap 0.0; bleeding_gums,chills,sweating",
        f"gap {fmt(call.gap, 1) if call else '-'}; {','.join(ids)}", problems)

    # H2-H4: scripted sessions.
    sessions = [
        ("H2", "Answer decides: bleeding gums yes", {"bleeding_gums": "yes"}, 1, "separated"),
        ("H3", "Answer decides: no bleeding, chills", {"bleeding_gums": "no", "chills": "moderate"}, 2, "separated"),
        ("H4", "All denied: question limit", {"bleeding_gums": "no", "chills": "no", "sweating": "no"}, 3, "max_questions"),
    ]
    hybrids = {}
    for case_id, name, answers, asked, outcome in sessions:
        hybrid = run_session(kb, BASE_CLOSE, scripted(answers))
        hybrids[case_id] = hybrid
        final = {d.disease_id: d.cf for d in hybrid.final_result.diseases}
        problems = []
        if len(hybrid.steps) != asked or hybrid.outcome != outcome:
            problems.append(f"asked {len(hybrid.steps)}, outcome {hybrid.outcome}")
        if case_id == "H2":
            if abs(final.get("dengue", 0) - 0.630) > CF_TOLERANCE or abs(final.get("malaria", 0) - 0.378) > CF_TOLERANCE:
                problems.append(f"final CFs {final}")
            if [a["id"] for a in hybrid.final_result.alerts] != ["RF1"]:
                problems.append("alert RF1 expected")
        if case_id == "H3":
            order = [d.disease_id for d in hybrid.final_result.diseases]
            if order != ["malaria", "dengue"] or abs(final.get("malaria", 0) - 0.597) > CF_TOLERANCE:
                problems.append(f"final {order} {final}")
        add(case_id, name, f"{asked} asked, {outcome}",
            f"{len(hybrid.steps)} asked, {hybrid.outcome}; " + actual_text(hybrid.final_result), problems)

    # H5: a clear case needs no questions.
    hybrid = run_session(kb, case_input("T01"), scripted({}))
    problems = [] if (hybrid.outcome == "not_close" and not hybrid.steps) else [f"{hybrid.outcome}"]
    add("H5", "Clear case: no questions", "not_close, 0 asked", f"{hybrid.outcome}, {len(hybrid.steps)} asked", problems)

    # H6: another close pair gets its own generated questions.
    typhoid_input = case_input("T03")
    result = diagnose(kb, typhoid_input)
    call = close_call(result)
    ids = [q.symptom_id for q in find_questions(kb, result, typhoid_input, set())]
    pair = {call.first.disease_id, call.second.disease_id} if call else set()
    problems = []
    if pair != {"typhoid", "malaria"}:
        problems.append(f"pair {sorted(pair)}")
    if ids != ["chills", "sweating"]:
        problems.append(f"questions {ids}")
    add("H6", "Other close pair", "typhoid~malaria; chills,sweating", f"{sorted(pair)}; {','.join(ids)}", problems)

    # H7: never ask a reported or denied symptom, never ask twice.
    problems = []
    for case_id, hybrid in hybrids.items():
        asked = [s.question.symptom_id for s in hybrid.steps]
        if len(asked) != len(set(asked)):
            problems.append(f"{case_id}: symptom asked twice")
        if set(asked) & set(BASE_CLOSE):
            problems.append(f"{case_id}: asked an already reported symptom")
    initial = [q.symptom_id for q in questions]
    if len(initial) != len(set(initial)) or set(initial) & set(BASE_CLOSE):
        problems.append("H1 question list has duplicates or reported symptoms")
    add("H7", "No repeated/reported questions", "none asked twice or already known", "checked H1-H4", problems)

    # H8: backward.py is generic - it names no disease or symptom.
    found = source_mentions_kb_names(kb)
    add("H8", "backward.py has no KB names", "no disease/symptom names", ",".join(found) or "none found",
        [f"found {found}"] if found else [])
    return rows, passed, 8, []


# ------------------------------------------------------------- [8] GUI smoke tests

def page_text(at) -> str:
    """All visible text of a headless Streamlit page (markdown, warnings, infos, expanders, buttons)."""
    parts = [m.value for m in at.markdown] + [w.value for w in at.warning]
    parts += [i.value for i in at.info] + [s.value for s in at.success] + [c.value for c in at.caption]
    parts += [e.label for e in at.expander] + [b.label for b in at.button]
    return " | ".join(parts)


BACK, FORWARD, NEW_TOP = ":material/arrow_back:", ":material/arrow_forward:", ":material/restart_alt:"
CLOSE_CASE = "I have fever, headache, nausea and body aches"
THREE_TIERS = "fever, rash, pain behind the eyes, cough, body aches, runny nose, sneezing"


def section_gui(kb: dict):
    """Run the wizard app headless with streamlit's AppTest; None if streamlit is missing."""
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError:
        return None
    import logging
    import re
    # Streamlit's headless test harness logs harmless "missing ScriptRunContext" warnings;
    # keep real errors visible.
    from streamlit import config as streamlit_config
    from streamlit import logger as streamlit_logger
    streamlit_config.set_option("logger.level", "error")
    streamlit_logger.set_log_level("ERROR")
    for name in list(logging.root.manager.loggerDict):
        if name.startswith("streamlit"):
            logging.getLogger(name).setLevel(logging.ERROR)

    def fresh():
        """A new headless run of app.py."""
        return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()

    def say(at, text: str):
        """Type a chat message and run."""
        at.chat_input[0].set_value(text).run()
        return at

    def click(at, label: str):
        """Click the first button with this label."""
        next(b for b in at.button if b.label == label).click().run()
        return at

    def button(at, label: str):
        """The first button with this label."""
        return next(b for b in at.button if b.label == label)

    def to_reasoning(text: str):
        """Type a sentence and press Diagnose (step 3)."""
        return click(say(fresh(), text), "Diagnose")

    def to_diagnosis(text: str):
        """Type a sentence, Diagnose, then See diagnosis (step 4)."""
        return click(to_reasoning(text), "See diagnosis")

    def html_blocks(at) -> list[str]:
        """Markdown elements rendered with unsafe_allow_html."""
        return [m.value for m in at.markdown if getattr(m, "allow_html", False)]

    def joined(at) -> str:
        """All unsafe-html text in one string."""
        return " ".join(html_blocks(at))

    def block(at, marker: str) -> str:
        """First html block containing a marker ('' if none)."""
        return next((b for b in html_blocks(at) if marker in b), "")

    def consult(at):
        """The one consultation state object (None before the first sentence)."""
        return at.session_state["consult"]

    def tags(chain: str) -> list[str]:
        """Tag texts of a chain panel in order, consecutive duplicates merged."""
        found = re.findall(r'class="tagc[^"]*">([^<]+)<', chain)
        return [t for i, t in enumerate(found) if i == 0 or t != found[i - 1]]

    rows, passed = [], 0

    def add(case_id: str, name: str, expected: str, problems: list[str]) -> None:
        """Record one row and count it if it passed."""
        nonlocal passed
        rows.append([case_id, name, expected, "ok" if not problems else problems[0], pass_fail(problems)])
        passed += not problems

    def errors(at) -> list[str]:
        """Exceptions raised by the app."""
        return [str(e.value) for e in at.exception]

    # ---- wizard flow
    at = fresh()
    problems = errors(at)
    if "Shifa" not in " ".join(html_blocks(at)):
        problems.append("brand name missing")
    if consult(at) is not None or len(at.chat_input) != 1:
        problems.append("step 1 should show the chat input and no consultation")
    if 'class="s now">1 Symptoms' not in block(at, 'class="stepsbar"'):
        problems.append("progress strip should highlight step 1")
    add("G1", "App loads on step 1", "no exception, brand, chat input", problems)

    at = say(fresh(), CLOSE_CASE)
    problems = errors(at)
    if consult(at)["step"] != 2:
        problems.append(f"step {consult(at)['step']}")
    if any('class="verdict' in b or 'class="card' in b for b in html_blocks(at)) or consult(at)["hyb"] is not None:
        problems.append("a diagnosis is shown before Diagnose was clicked")
    if len(at.chat_input) != 0:
        problems.append("typing must only be offered on step 1")
    if 'class="s now">2 Severity' not in block(at, 'class="stepsbar"'):
        problems.append("progress strip should highlight step 2")
    add("G2", "Typing goes to SEVERITY, no diagnosis yet", "step 2, no chat input", problems)

    at = fresh()
    at.pills(key="ask_pills").set_value(["fever", "headache"]).run()
    click(at, "Continue")
    problems = errors(at)
    if consult(at) is None or consult(at)["step"] != 2 or set(consult(at)["symptoms"]) != {"fever", "headache"}:
        problems.append("chips path should reach step 2 with the picked symptoms")
    add("G3", "Chips path", "same severity step", problems)

    at = to_reasoning(CLOSE_CASE)
    problems = errors(at)
    if consult(at)["step"] != 3 or 'class="chain pf' not in joined(at):
        problems.append("Diagnose should reach step 3 with the forward chain")
    if len(at.chat_input) != 0:
        problems.append("no chat input on step 3")
    click(at, "See diagnosis")
    if consult(at)["step"] != 4 or "Priority 1" not in joined(at):
        problems.append("See diagnosis should reach step 4")
    add("G4", "Diagnose then See diagnosis", "step 3 then step 4", problems)

    # ---- severity step
    def top_cf(level: str) -> float:
        """Evidence strength of the top condition when the fever is set to a level."""
        at = say(fresh(), "fever, cough, shortness of breath, chest pain")
        at.segmented_control(key="sev_fever").set_value(level).run()
        click(at, "Diagnose")
        return consult(at)["hyb"]["result"].diseases[0].cf

    moderate, severe = top_cf("moderate"), top_cf("severe")
    add("G5", "Severity changes the CF", f"moderate {fmt(moderate, 3)} != severe {fmt(severe, 3)}",
        [] if abs(moderate - severe) > 1e-6 else [f"CF unchanged: {moderate} vs {severe}"])

    at = say(fresh(), "bleeding gums and fever")
    keys = [s.key for s in at.segmented_control]
    problems = []
    if "sev_fever" not in keys:
        problems.append("fever should have a selector")
    if "sev_bleeding_gums" in keys:
        problems.append("presence-only symptom must not have a selector")
    if "present" not in joined(at):
        problems.append("'present' expected for the presence-only symptom")
    add("G6", "Presence-only symptoms", "no selector, shows 'present'", problems)

    at = say(fresh(), "no fever, only headache")
    problems = errors(at)
    if "ruled out" not in joined(at).lower() and "Ruled out" not in " ".join(m.value for m in at.markdown):
        problems.append("ruled-out list expected on step 2")
    click(at, "Diagnose")
    if "fever" in consult(at)["hyb"]["known"] or "fever" not in consult(at)["negated"]:
        problems.append("negated fever must not reach the engine")
    add("G7", "Negated symptom", "not passed to the engine", problems)

    at = say(fresh(), "im having bhukar and flu")
    text = joined(at) + " ".join(m.value for m in at.markdown)
    problems = errors(at)
    if "read from &#x27;bhukar&#x27;" not in text and "read from 'bhukar'" not in text:
        problems.append("'(read from bhukar)' expected")
    if "flu" not in text or "Not in my knowledge base" not in text:
        problems.append("unknown 'flu' expected")
    add("G8", "Fuzzy read + unknown phrase", "read from 'bhukar'; flu unknown", problems)

    at = say(fresh(), "flu")
    problems = errors(at)
    if "not disease names" not in joined(at):
        problems.append("'symptoms, not disease names' message expected")
    if consult(at)["step"] != 1 or consult(at)["hyb"] is not None:
        problems.append("no diagnosis and still on step 1 expected")
    add("G9", "Disease name typed", "friendly message, no diagnosis", problems)

    # ---- navigation
    at = to_reasoning(CLOSE_CASE)
    problems = errors(at)
    if not button(at, FORWARD).disabled:
        problems.append("forward must be disabled on the furthest step")
    result_before = consult(at)["hyb"]["result"]
    click(at, BACK)
    if consult(at)["step"] != 2 or button(at, FORWARD).disabled:
        problems.append("back should go to step 2 and enable forward")
    click(at, FORWARD)
    chain = block(at, 'class="chain pf')
    if consult(at)["step"] != 3 or 'class="chain pf static' not in chain:
        problems.append("forward should return to step 3 with a static chain")
    if consult(at)["hyb"]["result"] is not result_before:
        problems.append("navigation must not re-run the engine")
    click(at, BACK)
    click(at, BACK)
    if consult(at)["step"] != 1 or not button(at, BACK).disabled:
        problems.append("back must be disabled on step 1")
    if button(at, BACK).label != BACK or button(at, FORWARD).label != FORWARD:
        problems.append("icon labels expected")
    add("G10", "Back / forward icons", "bounded, no engine re-run, static", problems)

    at = to_reasoning(CLOSE_CASE)
    click(at, "Yes")
    problems = errors(at)
    if len(consult(at)["hyb"]["steps"]) != 1:
        problems.append("one answer expected")
    click(at, BACK)
    at.segmented_control(key="sev_fever").set_value("severe").run()
    click(at, "Diagnose")
    state = consult(at)
    if state["hyb"]["steps"] or state["reached"] != 3 or state["step"] != 3:
        problems.append("changing a severity must discard backward answers and restart step 3")
    if state["symptoms"]["fever"] != "severe":
        problems.append("the new severity should be kept")
    add("G11", "Change severity then Diagnose", "old answers discarded", problems)

    # ---- reasoning step
    at = to_reasoning(CLOSE_CASE)
    chain = block(at, 'class="chain pf')
    result = consult(at)["hyb"]["result"]
    wanted = ["FACTS"] + ["RULE FIRES", "NEW FACT"] * len(result.trace) + ["RESULT"]
    seen = re.findall(r'class="tagc[^"]*">([^<]+)<', chain)
    badges = re.findall(r'<span class="rbadge">(\w+)</span>', chain)
    indexes = [int(i) for i in re.findall(r"--i:(\d+)", chain)]
    gap = float(re.search(r"--gap:([0-9.]+)s", chain).group(1))
    problems = errors(at)
    if seen != wanted:
        problems.append(f"tags {seen}")
    if badges != [f.rule_id for f in result.trace]:
        problems.append(f"rows {badges} != fired rules {[f.rule_id for f in result.trace]}")
    if indexes != list(range(len(indexes))):
        problems.append(f"--i not increasing: {indexes}")
    if gap * len(indexes) > 4.0 + 1e-9:
        problems.append(f"chain would take {gap * len(indexes):.3f}s")
    if 'class="chain pf play' not in chain:
        problems.append("first render should animate ('play')")
    add("G12", "Forward panel tags, rows, timing", "FACTS, RULE FIRES, NEW FACT, RESULT; <= 4 s", problems)

    at = to_reasoning(CLOSE_CASE)
    problems = errors(at)
    if "One question to settle it" not in text_of(at):
        problems.append("question card expected for a close call")
    clear = to_reasoning("severe fever, rash, pain behind the eyes, bleeding gums, runny nose, sneezing")
    if "Backward chaining not needed: the top condition is clearly ahead (gap" not in joined(clear):
        problems.append("'clearly ahead (gap NN% > 15%)' expected for a clear two-condition case")
    single = to_reasoning("fever, cough, shortness of breath, chest pain")
    if "Backward chaining not needed" not in joined(single):
        problems.append("'Backward chaining not needed' expected when one condition is shown")
    add("G13", "Question card / not needed", "close call asks, clear case does not", problems)

    at = to_reasoning(CLOSE_CASE)
    click(at, "Yes")
    chain = block(at, 'class="chain pb')
    problems = errors(at)
    if tags(chain) != ["GOAL", "NEEDS", "ASK", "YOU SAID", "PROVEN ✓"]:
        problems.append(f"backward tags {tags(chain)}")
    css = __import__("ui.theme", fromlist=["CSS"]).CSS
    fw = re.search(r"--fw:(#\w+)", css).group(1).lower()
    bw = re.search(r"--bw:(#\w+)", css).group(1).lower()
    taken = {c.lower() for c in re.findall(r"--(?:accent|sev[123]|sev[123]-bg):(#\w+)", css)}
    if fw == bw or fw in taken or bw in taken:
        problems.append(f"forward {fw} / backward {bw} colours must be unique")
    if 'class="chain pb play' not in chain:
        problems.append("the new backward panel should animate")
    gap = float(re.search(r"--gap:([0-9.]+)s", chain).group(1))
    if gap * len(re.findall(r"--i:\d+", chain)) > 4.0 + 1e-9:
        problems.append("backward panel longer than 4 s")
    add("G14", "Backward panel tags and colours", "GOAL, NEEDS, ASK, YOU SAID, PROVEN; unique colours", problems)

    at = to_reasoning(CLOSE_CASE)
    before = block(at, 'class="chain pf')
    nonce_before = consult(at)["nonce"].get("chain", 0)
    click(at, ":material/replay: Replay")
    after = block(at, 'class="chain pf')
    problems = errors(at)
    if before == after or consult(at)["nonce"].get("chain", 0) != nonce_before + 1:
        problems.append("Replay must change the HTML and bump the replay counter (container key)")
    if 'class="chain pf play' not in after:
        problems.append("Replay should animate again")
    click(at, BACK)
    click(at, FORWARD)
    if 'class="chain pf static' not in block(at, 'class="chain pf'):
        problems.append("a later rerun must render the chain statically")
    add("G15", "Replay and play-once", "Replay differs; later reruns static", problems)

    # ---- diagnosis step
    at = to_diagnosis(CLOSE_CASE)
    text = joined(at)
    problems = errors(at)
    verdict = block(at, 'class="verdict')
    if "MOST LIKELY" not in verdict or 'class="vname">Dengue and Malaria<' not in verdict:
        problems.append("big verdict with both names expected")
    if "equally likely · 50.0% each" not in verdict:
        problems.append("tie wording expected")
    if 'class="tied"' not in text:
        problems.append("tied tags expected")
    add("G16", "Tie wording and tags", "equally likely, tied tags", problems)

    at = to_diagnosis("chest pain and shortness of breath")
    texts = [m.value for m in at.markdown]
    alert_at = next((i for i, t in enumerate(texts) if 'class="alert"' in t), None)
    verdict_at = next((i for i, t in enumerate(texts) if 'class="verdict' in t), None)
    problems = errors(at)
    if alert_at is None or verdict_at is None or alert_at > verdict_at:
        problems.append("the red-flag banner must come first")
    if "Chest pain with shortness of breath" not in " ".join(texts):
        problems.append("emergency advice missing")
    if "Not enough evidence to name a condition" not in " ".join(texts):
        problems.append("no-condition verdict expected")
    add("G17", "Red flag banner first", "banner above the verdict", problems)

    at = to_diagnosis("fever, rash, pain behind the eyes, runny nose, sneezing, sore throat")
    result = consult(at)["hyb"]["result"]
    heads = re.findall(r"Priority (\d) · (\w+) conditions", joined(at))
    expected, last = [], None
    for d in result.diseases:
        if d.severity != last:
            expected.append((str(len(expected) + 1), d.severity.capitalize()))
            last = d.severity
    problems = errors(at)
    if heads != expected or len(heads) < 2:
        problems.append(f"tier headers {heads}, engine order {expected}")
    cfs = {d.disease_id: d.cf for d in result.diseases}
    if not cfs.get("common_cold", 0) > cfs.get("dengue", 1):
        problems.append("mixed case should have the mild condition at higher confidence")
    ids = [d.disease_id for d in result.diseases]
    if ids[:1] != ["dengue"] or set(ids) != {"dengue", "common_cold"}:
        problems.append(f"order {ids}")
    if "Listed first because severe conditions take priority over less severe ones." not in text_of(at):
        problems.append("corrected 'Listed first because...' line expected")
    if "even if a less severe one has higher confidence" not in " ".join(c.value for c in at.caption):
        problems.append("corrected tier caption expected")
    add("G18", "Priority tiers (mixed case)", "severe tier first, corrected wording", problems)

    at = to_diagnosis(CLOSE_CASE)
    cid = consult(at)["id"]
    default_html = joined(at)
    problems = errors(at)
    if "Suggested because" in default_html or "No specific medicine" in default_html:
        problems.append("panels must be closed by default")
    at.segmented_control(key=f"{cid}-tab-dengue").set_value("Treatment").run()
    if "No specific medicine" not in joined(at):
        problems.append("Treatment panel should open")
    at.segmented_control(key=f"{cid}-tab-dengue").set_value("Prevention").run()
    if "Repellents" not in joined(at):
        problems.append("Prevention panel should open")
    at.segmented_control(key=f"{cid}-tab-dengue").set_value("Why this?").run()
    why = next((b for b in html_blocks(at) if "Suggested because" in b), "")
    shown = re.findall(r"<li>(R\d+) ·", why)
    result = consult(at)["hyb"]["result"]
    latest = {f.rule_id: f for f in result.trace if f.concluded_fact}
    wanted_rules, frontier = set(), ["dengue"]
    while frontier:
        fact = frontier.pop()
        for f in latest.values():
            if f.concluded_fact == fact and f.rule_id not in wanted_rules:
                wanted_rules.add(f.rule_id)
                frontier += [p for p in f.premises if p not in kb["symptoms"]]
    if set(shown) != wanted_rules or not wanted_rules:
        problems.append(f"Why panel rules {shown}, trace says {sorted(wanted_rules)}")
    if "Combined certainty" not in why:
        problems.append("combined certainty line expected")
    add("G19", "Why / Treatment / Prevention", "closed by default; Why = traced rules", problems)

    at = to_reasoning(CLOSE_CASE)
    click(at, "Yes")
    click(at, "See diagnosis")
    texts = [m.value for m in at.markdown]
    problems = errors(at)
    if "RED FLAG" not in " ".join(texts) or "Bleeding gums or nose can be a warning sign" not in " ".join(texts):
        problems.append("red alert expected after Yes")
    cards = [t for t in texts if 'class="card' in t]
    if not cards or "Dengue" not in cards[0]:
        problems.append("Dengue should be the first card")
    add("G20", "Answer Yes", "alert, Dengue first", problems)

    at = to_reasoning(CLOSE_CASE)
    for _ in range(3):
        click(at, "No")
    problems = errors(at)
    if len(consult(at)["hyb"]["steps"]) != 3:
        problems.append(f"{len(consult(at)['hyb']['steps'])} questions asked")
    if not any("Outcome:" in i.value for i in at.info):
        problems.append("st.info outcome expected")
    if any("Outcome:" in s.value for s in at.success):
        problems.append("green box only for 'separated'")
    add("G21", "All No", "3 asked, info box", problems)

    at = to_diagnosis("fever and cough")
    saved = dict(consult(at)["symptoms"])
    click(at, "Edit symptoms")
    problems = errors(at)
    if consult(at)["step"] != 2 or consult(at)["symptoms"] != saved:
        problems.append("Edit symptoms should return to step 2 with the same symptoms")
    click(at, BACK)
    click(at, FORWARD)
    click(at, "Diagnose")
    click(at, "See diagnosis")
    click(at, "New consultation")
    if consult(at) is not None:
        problems.append("New consultation should clear the state")
    at = to_reasoning("fever and cough")
    click(at, NEW_TOP)
    if consult(at) is not None:
        problems.append("the top icon button should clear the state too")
    add("G22", "Edit symptoms / New consultation", "back to step 2; state cleared", problems)

    # ---- knowledge-base view
    at = fresh()
    at.segmented_control(key="view").set_value("Knowledge base").run()
    problems = errors(at)
    tiles = {b.key: b.label for b in at.button if b.key and b.key.startswith("kbtile-")}
    n_flags = len(kb["red_flags"])
    checks = {"kbtile-symptoms": str(len(kb["symptoms"])), "kbtile-diseases": str(len(kb["diseases"])),
              "kbtile-rules": f"{len(kb['rules'])} rules + {n_flags} red flags",
              "kbtile-severity": "Mild · Moderate · Severe", "kbtile-treatments": "treatment + prevention"}
    for key, needle in checks.items():
        if needle not in tiles.get(key, ""):
            problems.append(f"tile {key}: '{needle}' not in '{tiles.get(key)}'")
    cards = [b for b in html_blocks(at) if 'class="card kbcard"' in b]
    names = [re.search(r'class="name">([^<]+)<', c).group(1) for c in cards]
    sevs = [re.search(r'class="pill sev\d">([^<]+)<', c).group(1) for c in cards]
    if names != ["Dengue", "Influenza", "Common Cold"] or sevs != ["Severe", "Moderate", "Mild"]:
        problems.append(f"showcase {names} {sevs}")
    for card in cards:
        for needle in ("Symptoms used", "IF ", "THEN", "Treatment", "Prevention"):
            if needle not in card:
                problems.append(f"showcase card lacks '{needle}'")
    roots, frontier, seen = set(), ["dengue"], set()
    while frontier:
        fact = frontier.pop()
        for rule in kb["rules"]:
            if rule["then"] == fact and rule["id"] not in seen:
                seen.add(rule["id"])
                for p in rule["if"]:
                    (roots.add(p) if p in kb["symptoms"] else frontier.append(p))
    missing = [kb["symptoms"][s]["label"] for s in roots if kb["symptoms"][s]["label"] not in cards[0]]
    if missing:
        problems.append(f"Dengue card lacks root symptoms {missing}")
    if not any("Show the full knowledge base" in e.label for e in at.expander):
        problems.append("full-KB expander missing")
    if f"{len(kb['rules'])} rules" not in joined(at) + " ".join(c.value for c in at.caption) + " ".join(tiles.values()):
        problems.append("rule count expected")
    add("G23", "Knowledge base view", "5 tiles, 3 examples (severe, moderate, mild), expander", problems)

    # ---- brand, safety, sources
    old_name = "Dr." + " Rule"
    files = [ROOT / "app.py", ROOT / "README.md", ROOT / "run_tests.py"] + sorted((ROOT / "ui").glob("*.py")) \
        + sorted((ROOT / "docs").glob("*.md")) + sorted((ROOT / "expert_system").glob("*.py"))
    hits = [f.name for f in files if old_name in f.read_text(encoding="utf-8")]
    at = fresh()
    if "Shifa" not in " ".join(html_blocks(at)):
        hits.append("Shifa missing from the page")
    add("G24", "Brand", "'Shifa' present, old name absent everywhere", hits)

    at = say(fresh(), "<script>alert(1)</script> fever")
    problems = errors(at)
    if any("<script" in b.lower() for b in html_blocks(at)):
        problems.append("raw <script> found in unsafe html")
    add("G25", "Script text is escaped", "no raw tag in html", problems)

    scanned = [ROOT / "app.py"] + sorted((ROOT / "ui").glob("*.py"))
    banned = ["http://", "https://", "@import", "<script", "fonts.googleapis", "sleep", "write_stream"]
    hits = [f"{f.name}: {b}" for f in scanned for b in banned if b in f.read_text(encoding="utf-8")]
    from ui.theme import CSS
    if "prefers-reduced-motion" not in CSS:
        hits.append("prefers-reduced-motion CSS missing")
    add("G26", "No external loads, no timers", "none of " + ", ".join(banned), hits)

    # ---- bold verdict and one scale variable (Phase 6E)
    at = to_diagnosis("fever, rash, pain behind the eyes, bleeding gums, runny nose, sneezing")
    verdict = block(at, 'class="verdict')
    result = consult(at)["hyb"]["result"]
    top = result.diseases[0]
    problems = errors(at)
    for needle in ("MOST LIKELY", f'class="vname">{top.name}<', f'class="vconf">{fmt(top.percent, 1)}%<',
                   f'class="vsev">{top.severity.capitalize()}<', "Because:"):
        if needle not in verdict:
            problems.append(f"verdict lacks {needle}")
    from ui.theme import CSS
    rules = {"--u:clamp(": "one scale variable", "html{font-size:var(--u)": "root font from the scale",
             ".verdict .vname{font-size:2.8rem;font-weight:800": "name ~64px at 1920",
             ".verdict .vconf{font-size:2.45rem;font-weight:800": "confidence ~56px",
             ".big{font-size:2.8rem;font-weight:800": "card confidence ~64px",
             ".card .name{font-size:1.4rem;font-weight:800": "card name ~32px"}
    for needle, label in rules.items():
        if needle not in CSS:
            problems.append(f"CSS lacks {label}")
    if re.search(r"font-size:\s*[0-9.]+px", CSS):
        problems.append("fixed px font sizes found; sizes must come from the scale (15px floors use max())")
    add("G27", "Bold verdict + scale", "big name/confidence/pill, one scale variable", problems)

    # ---- crowded cases (Phase 6F): all 20 symptoms, 6 conditions, 3 red flags
    everything = ", ".join(("severe " + sym["label"]) if sym["input"] == "intensity" else sym["label"]
                           for sym in kb["symptoms"].values())
    unstated = ", ".join(sym["label"] for sym in kb["symptoms"].values())
    at = say(fresh(), unstated)
    problems = errors(at)
    html = joined(at)
    if len(consult(at)["symptoms"]) != len(kb["symptoms"]):
        problems.append("all symptoms should be understood")
    if html.count("sevnote") != 1 or "default (not stated)" not in html:
        problems.append("exactly one 'default (not stated)' note expected above the grid")
    if any("default (not stated)" in c.value for c in at.caption):
        problems.append("no per-card default line in the compact grid")
    if f"{len(kb['symptoms'])} symptoms selected" not in html:
        problems.append("one-line 'N symptoms selected' expected")
    if "You said:" in " ".join(c.value for c in at.caption):
        problems.append("the side panel must collapse when many symptoms are selected")
    add("G28", "Crowded severity step", "one default note, one-line count, no per-card default", problems)

    at = to_diagnosis(everything)
    result = consult(at)["hyb"]["result"]
    html = joined(at)
    banners = [b for b in html_blocks(at) if 'class="alert' in b]
    problems = errors(at)
    if len(banners) != 1 or 'class="alert multi"' not in banners[0]:
        problems.append(f"{len(banners)} red-flag banners, one combined banner expected")
    else:
        for flag in result.alerts:
            if flag["id"] not in banners[0] or flag["message"] not in banners[0]:
                problems.append(f"banner lacks {flag['id']}")
        if banners[0].count("<li>") != len(result.alerts) or len(result.alerts) != 3:
            problems.append("one line per fired flag (3) expected")
    compact = html.count('class="card compact')
    if len(result.diseases) <= 3 or compact != len(result.diseases):
        problems.append(f"{len(result.diseases)} conditions but {compact} compact cards")
    add("G29", "Crowded diagnosis step", "one banner with 3 flags; compact cards for > 3 conditions", problems)

    at = to_diagnosis(CLOSE_CASE)
    html = joined(at)
    problems = errors(at)
    if 'class="card compact' in html:
        problems.append("3 or fewer conditions must keep the normal cards")
    at = to_diagnosis("fever, rash, pain behind the eyes, bleeding gums, runny nose, sneezing")
    banners = [b for b in html_blocks(at) if 'class="alert' in b]
    if len(banners) != 1 or 'class="alert multi"' in banners[0] or 'class="alert"' not in banners[0]:
        problems.append("a single red flag keeps the single-banner look")
    add("G30", "Normal layout unchanged", "no compact class, single-flag banner as before", problems)

    at = say(fresh(), "fever, headache, cough, chills, sweating, fatigue, sore throat")
    html = joined(at)
    captions = [c.value for c in at.caption if "default (not stated)" in c.value]
    problems = errors(at)
    if len(consult(at)["symptoms"]) != 7 or "7 symptoms selected" not in html or "You said:" in " ".join(c.value for c in at.caption):
        problems.append("7 symptoms: side panel should be one line")
    if len(captions) != 7 or "sevnote" in html:
        problems.append("7 symptoms keep the normal cards with a default line each")
    at = say(fresh(), "fever, headache, cough")
    if "You said:" not in " ".join(c.value for c in at.caption) or "symptoms selected" in joined(at):
        problems.append("6 or fewer symptoms: the side panel shows the full list")
    add("G31", "Side panel and normal severity cards", "7: one line; 3: full list", problems)
    return rows, passed, 31, []


def text_of(at) -> str:
    """Unsafe-html markdown plus captions, infos and warnings, as one string."""
    return " ".join([m.value for m in at.markdown] + [c.value for c in at.caption]
                    + [i.value for i in at.info] + [w.value for w in at.warning])


# ------------------------------------------------------------------ [9] text parser

def section_text_parser(kb: dict):
    """Test expert_system/text_parser.py (free-text input)."""
    from expert_system.text_parser import parse_text
    rows, passed = [], 0

    def add(case_id: str, name: str, expected: str, actual: str, problems: list[str]) -> None:
        """Record one row and count it if it passed."""
        nonlocal passed
        rows.append([case_id, name, expected, actual, pass_fail(problems)])
        passed += not problems

    def ids(text: str) -> set:
        """Symptom ids found in a text."""
        return set(parse_text(kb, text).symptoms)

    # P1: every synonym, label and id of every symptom parses back to its symptom.
    misses = [(sid, name) for sid, s in kb["symptoms"].items()
              for name in s["synonyms"] + [s["label"], sid] if sid not in ids(name)]
    total = sum(len(s["synonyms"]) + 2 for s in kb["symptoms"].values())
    add("P1", "Every KB phrase parses back", f"{total} phrases", f"{total - len(misses)} ok",
        [f"misses: {misses[:3]}"] if misses else [])

    got = ids("I have fever and headache")
    add("P2", "English sentence", "fever, headache", ",".join(sorted(got)),
        [] if got == {"fever", "headache"} else ["wrong symptoms"])

    fever_ru, head_ru = kb["symptoms"]["fever"]["synonyms"][-1], kb["symptoms"]["headache"]["synonyms"][-1]
    sentence = f"mujhe {fever_ru} aur {head_ru} hai"
    got = ids(sentence)
    add("P3", "Roman Urdu sentence", sentence, ",".join(sorted(got)),
        [] if got == {"fever", "headache"} else ["wrong symptoms"])

    problems = []
    a = parse_text(kb, "no fever, only headache")
    b = parse_text(kb, f"{fever_ru} nahi hai")
    if set(a.symptoms) != {"headache"} or a.negated != ["fever"]:
        problems.append(f"'no fever, only headache' -> {a.symptoms} {a.negated}")
    if b.symptoms or b.negated != ["fever"]:
        problems.append(f"'{fever_ru} nahi hai' -> {b.symptoms} {b.negated}")
    add("P4", "Negation", "ruled out, not diagnosed", "ok" if not problems else problems[0], problems)

    problems = []
    a = parse_text(kb, "severe headache").symptoms.get("headache")
    b = parse_text(kb, f"halka {fever_ru}").symptoms.get("fever")
    if a != "severe" or b != "mild":
        problems.append(f"severe headache -> {a}, halka {fever_ru} -> {b}")
    add("P5", "Intensity words", "severe / mild", f"{a} / {b}", problems)

    follow_up = next(sid for sid, s in kb["symptoms"].items() if s.get("ask_only_if"))
    outcomes = {n: follow_up in parse_text(kb, f"fever for {n} days").symptoms for n in (2, 3, 4, 5)}
    problems = [] if outcomes == {2: False, 3: False, 4: True, 5: True} else [str(outcomes)]
    add("P6", "Duration", "only > 3 days is prolonged", str(outcomes), problems)

    problems = []
    for text in ["asdf qwer zxcv", "", "!!!", "   "]:
        try:
            if parse_text(kb, text).symptoms:
                problems.append(f"'{text}' gave symptoms")
        except Exception as error:               # a crash is a failure
            problems.append(f"'{text}' crashed: {error}")
    add("P7", "Gibberish / empty", "empty symptoms, no crash", "ok" if not problems else problems[0], problems)

    parsed = parse_text(kb, "fever and itching")
    problems = [] if (set(parsed.symptoms) == {"fever"} and "itching" in parsed.unknown) else [str(parsed)]
    add("P8", "Unknown phrase reported", "fever parsed, itching unknown",
        f"{sorted(parsed.symptoms)} / {parsed.unknown}", problems)

    clauses = ["severe headache", "no cough", "fever for 5 days", "chest pain", "sore throat"]
    reference = None
    problems = []
    for seed in range(50):
        order = clauses[:]
        random.Random(seed).shuffle(order)
        p = parse_text(kb, ", ".join(order))
        signature = (sorted(p.symptoms.items()), sorted(p.negated), sorted(p.unknown), p.duration_days)
        if reference is None:
            reference = signature
        elif signature != reference:
            problems.append(f"seed {seed} differs")
            break
    add("P9", "Clause order independence", "50 shuffles identical", "ok" if not problems else problems[0], problems)

    text = (ROOT / "expert_system" / "text_parser.py").read_text(encoding="utf-8").lower()
    names = list(kb["diseases"]) + [d["name"] for d in kb["diseases"].values()]
    names += list(kb["symptoms"]) + [s["label"] for s in kb["symptoms"].values()]
    found = sorted({n for n in names if n.lower() in text})
    add("P10", "No KB names in text_parser.py", "none", ",".join(found) or "none found",
        [f"found {found}"] if found else [])

    p = parse_text(kb, "im having bhukar and flu")
    problems = []
    if set(p.symptoms) != {"fever"} or p.read_from != {"fever": "bhukar"} or p.unknown != ["flu"]:
        problems.append(f"{p.symptoms} {p.read_from} {p.unknown}")
    add("P11", "Typo + unknown in one sentence", "fever (read from bhukar), unknown flu",
        f"{sorted(p.symptoms)} {p.read_from} {p.unknown}", problems)

    p = parse_text(kb, "I have a bad headche")
    problems = [] if ("headache" in p.symptoms and p.read_from.get("headache") == "headche") else [str(p)]
    add("P12", "Typo inside a longer sentence", "headache read from headche",
        f"{sorted(p.symptoms)} {p.read_from}", problems)

    problems = []
    for text in ["the a my im having", "i am having been", "m"]:
        p = parse_text(kb, text)
        if p.symptoms or p.unknown:
            problems.append(f"'{text}' -> {p.symptoms} {p.unknown}")
    add("P13", "Filler-only text", "empty, nothing unknown", "ok" if not problems else problems[0], problems)

    p = parse_text(kb, "I have fever and headche")
    problems = [] if p.read_from == {"headache": "headche"} else [f"read_from {p.read_from}"]
    add("P14", "read_from only for fuzzy matches", "{headache: headche}", str(p.read_from), problems)
    return rows, passed, 14, []


# ------------------------------------------------------------------------- main

def print_section(title: str, headers: list[str], rows: list[list[str]], failures: list,
                  kb: dict, verbose: bool) -> None:
    """Print one section: table, then problems (and full diagnoses if --verbose)."""
    print(f"\n{title}")
    print_table(headers, rows)
    for case_id, symptoms, result, problems in failures:
        for problem in problems:
            print(f"  ! {case_id}: {problem}")
        if verbose:
            known = {k: v for k, v in symptoms.items() if k in kb["symptoms"]}
            print_result(kb, result, known, [], False)
            print_trace(kb, result)


def main() -> int:
    """Run all nine sections and print the summary; return the exit code."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Run the expert system tests")
    parser.add_argument("--verbose", action="store_true", help="print full diagnosis of failing cases")
    verbose = parser.parse_args().verbose

    kb = load_kb()
    ok, errors, stats = verify_kb(kb)
    summary = []

    print("[1] KB verification")
    line = (f"{stats['diseases']} diseases, {stats['symptoms']} symptoms, "
            f"{stats['intermediate_facts']} intermediate facts, {stats['rules']} rules")
    print_table(["Check", "Result", "Detail"],
                [["8 consistency checks", pass_fail([] if ok else errors), line if ok else f"{len(errors)} errors"]])
    for error in errors:
        print(f"  ! {error}")
    summary.append(("[1] KB verification", int(ok), 1))

    clinical_headers = ["ID", "Case", "Expected", "Actual", "Result"]
    sections = [
        ("[2] Clinical cases (WHO/CDC)", clinical_headers, section_clinical),
        ("[3] Regression (exact CFs)", ["ID", "Case", "Expected", "Actual", "Result"], section_regression),
        ("[4] CLI input parsing", ["Typed", "Expected", "Actual", "Result"], section_parsing),
        ("[5] Verifier self-tests", ["Test", "Expected", "Actual", "Result"], section_verifier),
        ("[6] Order independence", ["Shuffles", "Cases", "Outcome", "Result"], section_order),
        ("[7] Hybrid backward chaining", ["ID", "Case", "Expected", "Actual", "Result"], section_hybrid),
        ("[8] GUI smoke tests", ["ID", "Case", "Expected", "Actual", "Result"], section_gui),
        ("[9] Text parser", ["ID", "Case", "Expected", "Actual", "Result"], section_text_parser),
    ]
    for title, headers, function in sections:
        outcome = function(kb)
        if outcome is None:
            print()
            print(f"{title.split(' ', 1)[0]} skipped (streamlit not installed)")
            continue
        rows, passed, total, failures = outcome
        print_section(title, headers, rows, failures, kb, verbose)
        summary.append((title, passed, total))

    print("\nSummary")
    print_table(["Section", "Passed", "Total"], [[t, str(p), str(n)] for t, p, n in summary])
    passed_all = sum(p for _, p, _ in summary)
    total_all = sum(n for _, _, n in summary)
    print(f"\nTOTAL: {passed_all}/{total_all} passed")
    return 0 if passed_all == total_all else 1


if __name__ == "__main__":
    sys.exit(main())
