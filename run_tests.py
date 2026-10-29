"""Test runner: python run_tests.py [--verbose]

Six sections, each printed as an ASCII table:
  [1] KB verification            - the knowledge base passes all 8 consistency checks
  [2] Clinical cases             - cases written from WHO/CDC descriptions (tests/cases.json)
  [3] Regression                 - exact CFs from the design check (tests/regression.json)
  [4] CLI input parsing          - separators, synonyms and "did you mean"
  [5] Verifier self-tests        - the verifier catches deliberately broken KBs (in memory only)
  [6] Order independence         - shuffling rule order never changes the result

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
    """Run all six sections and print the summary; return the exit code."""
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
    ]
    for title, headers, function in sections:
        rows, passed, total, failures = function(kb)
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
