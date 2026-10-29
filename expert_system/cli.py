"""Command-line interface for the expert system.

Two modes share one result format:
  * interactive:      python main.py
  * non-interactive:  python main.py --symptoms "bukhar:moderate, rash:yes" [--trace] [--why-not]

The CLI is generic: every symptom name, label, synonym, disease and message is
read from the knowledge base. Nothing medical is written in this file.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
import textwrap
from typing import Optional

from expert_system.engine import DiagnosisResult, diagnose, display_name, fmt

CLOSE_MATCH_CUTOFF = 0.75   # difflib similarity needed for a "did you mean" hint
LINE_WIDTH = 72


# ------------------------------------------------------------- symptom matching

def normalize(text: str) -> str:
    """Lowercase, trim, turn '_' and '-' into spaces and collapse repeated spaces."""
    text = text.lower().strip().replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def build_name_index(kb: dict) -> dict[str, str]:
    """Map every normalized symptom id, label and synonym to its symptom id."""
    index: dict[str, str] = {}
    for sid, symptom in kb["symptoms"].items():
        for name in [sid, symptom["label"]] + symptom.get("synonyms", []):
            index.setdefault(normalize(name), sid)
    return index


def resolve_symptom(text: str, kb: dict) -> tuple[Optional[str], Optional[str]]:
    """Match free text to a symptom: returns (symptom_id, suggestion_id).

    Exact match on id/label/synonym -> (id, None). A close (fuzzy) match is only
    a suggestion -> (None, id). Nothing close -> (None, None).
    """
    key = normalize(text)
    index = build_name_index(kb)
    if key in index:
        return index[key], None
    close = difflib.get_close_matches(key, list(index), n=1, cutoff=CLOSE_MATCH_CUTOFF)
    if close:
        return None, index[close[0]]
    return None, None


# Words that join two symptoms: " and ", " aur " (Roman Urdu), "&" and "+".
# " or " is deliberately NOT here: labels such as "Nausea or vomiting" contain it.
SEPARATOR_WORDS = re.compile(r"\s+(?:and|aur)\s+|\s*[&+]\s*", re.IGNORECASE)


def split_entries(text: str, kb: dict) -> list[str]:
    """Split typed text into one entry per symptom (used by both CLI modes).

    Pieces are first cut at commas, semicolons and newlines. Each piece is then
    checked as a whole: if it already names a symptom (ignoring a trailing
    one-word ':value'), it is kept whole, so a KB name that happens to contain a
    separator word is never torn apart. Only a piece that does not resolve is
    split further at the separator words.
    """
    entries: list[str] = []
    for piece in re.split(r"[,;\n]", text):
        piece = piece.strip()
        if not piece:
            continue
        name, _, value = piece.partition(":")
        # Keep whole only for "name" or "name:oneword"; "rash:yes and fever" is two entries.
        if resolve_symptom(name, kb)[0] is not None and len(value.split()) <= 1:
            entries.append(piece)
            continue
        entries.extend(part.strip() for part in SEPARATOR_WORDS.split(piece) if part.strip())
    return entries


def default_value(kb: dict, sid: str) -> str:
    """Value used when the user gives none: 'moderate' for intensity, 'yes' for yes/no."""
    return "moderate" if kb["symptoms"][sid]["input"] == "intensity" else "yes"


# ---------------------------------------------------------------- output helpers

def paint(text: str, code: str, color: bool) -> str:
    """Wrap text in an ANSI colour code when colour is enabled."""
    return f"\033[{code}m{text}\033[0m" if color else text


def color_enabled(args: argparse.Namespace) -> bool:
    """Use colour only on a real terminal, unless --no-color or NO_COLOR is set."""
    if args.no_color or os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        os.system("")   # switches on ANSI escape handling in Windows consoles
    return True


def bullet(text: str) -> str:
    """Format one wrapped '- item' line."""
    return textwrap.fill(text, width=LINE_WIDTH, initial_indent="  - ",
                         subsequent_indent="    ")


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print an aligned ASCII table."""
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    print("  " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  " + "-+-".join("-" * w for w in widths))
    for row in rows:
        print("  " + " | ".join(c.ljust(w) for c, w in zip(row, widths)))


def severity_outranks_confidence(result: DiagnosisResult) -> bool:
    """True if some disease is ranked below another one that has a lower CF."""
    diseases = result.diseases
    for i, higher in enumerate(diseases):
        for lower in diseases[i + 1:]:
            if lower.cf > higher.cf + 1e-9:
                return True
    return False


def print_result(kb: dict, result: DiagnosisResult, accepted: dict[str, str],
                 notes: list[str], color: bool) -> None:
    """Print the full result: alerts, symptoms, ranked diseases, details, notes, disclaimer."""
    conv = kb["meta"]["cf_conventions"]
    print()
    print(paint("=" * LINE_WIDTH + "\n RESULT\n" + "=" * LINE_WIDTH, "1;36", color))

    # 1. Red-flag alerts come first and stand out.
    for alert in result.alerts:
        bar = "!" * LINE_WIDTH
        message = textwrap.fill("EMERGENCY: " + alert["message"], width=LINE_WIDTH)
        print(paint(f"{bar}\n{message}\n{bar}", "1;31", color))

    # 2. Recognised symptoms.
    print("\nRecognised symptoms:")
    shown = [f"  - {kb['symptoms'][s]['label']} ({v})" for s, v in accepted.items() if v != "no"]
    print("\n".join(shown) if shown else "  (none)")

    # 3. Ranked table, or the "not enough evidence" message.
    if result.diseases:
        print("\nPossible diseases (ranked: severity first, then confidence):")
        rows = [[str(i), d.name, d.severity, fmt(d.percent, 1), fmt(d.cf, 2)]
                for i, d in enumerate(result.diseases, 1)]
        print_table(["Rank", "Disease", "Severity", "Confidence %", "CF"], rows)
        if severity_outranks_confidence(result):
            print("Note: severe diseases are listed first even when a milder disease "
                  "has higher confidence (safety-first ranking).")
    else:
        percent = round(conv["display_threshold"] * 100)
        print(f"\nNo disease reached the {percent}% confidence threshold. "
              "Not enough evidence for a diagnosis.")

    if result.below_threshold:
        weak = ", ".join(f"{b['name']} (CF {fmt(b['cf'], 3)})" for b in result.below_threshold)
        print(f"Below threshold (not enough evidence): {weak}")

    # 4. Details per disease.
    for i, d in enumerate(result.diseases, 1):
        print(paint(f"\n--- {i}. {d.name} ({d.severity}) ---", "1", color))
        print(textwrap.fill(d.description, width=LINE_WIDTH))
        print("Why this was suggested:")
        print("\n".join("  " + line for line in d.justification))
        print("Treatment:")
        print("\n".join(bullet(item) for item in d.treatment))
        print("Prevention:")
        print("\n".join(bullet(item) for item in d.prevention))
        print("Sources: " + ", ".join(d.sources))

    # 5. Unknown symptoms and warnings.
    all_notes = notes + [f"Unknown symptom '{u}'." for u in result.unknown_symptoms] + result.warnings
    if all_notes:
        print("\nNotes:")
        print("\n".join(bullet(n) for n in all_notes))

    # 7. Disclaimer is always last.
    print("\n" + textwrap.fill("DISCLAIMER: " + result.disclaimer, width=LINE_WIDTH))


def print_trace(kb: dict, result: DiagnosisResult) -> None:
    """Print one line per forward-chaining cycle."""
    print("\nReasoning trace (forward chaining, one rule fires per cycle):")
    if not result.trace:
        print("  (no rule fired)")
    for f in result.trace:
        line = f"  Cycle {f.cycle}: conflict set [{', '.join(f.conflict_set)}] -> fired {f.rule_id}"
        if f.kind == "red_flag":
            line += " -> ALERT"
        else:
            line += (f": {display_name(kb, f.concluded_fact)} "
                     f"{fmt(f.cf_before, 3)} -> {fmt(f.cf_after, 3)}")
            if f.refire:
                line += " (re-fire)"
        print(line)


def print_why_not(kb: dict, result: DiagnosisResult) -> None:
    """Print why each disease that was not shown was ruled out."""
    print("\nWhy the other diseases were ruled out:")
    if not result.why_not:
        print("  (every disease was shown)")
    for did, lines in result.why_not.items():
        print(f"\n  {display_name(kb, did)}:")
        print("\n".join("    " + line for line in lines))


# ------------------------------------------------------------- non-interactive mode

def parse_symptom_arg(kb: dict, text: str) -> tuple[dict[str, str], list[str]]:
    """Parse '--symptoms' text 'name[:value], ...' into ({id: value}, problems).

    Close matches are never auto-accepted; they are reported as suggestions.
    """
    valid_values = list(kb["meta"]["cf_conventions"]["intensity_cf"]) + ["no"]
    accepted: dict[str, str] = {}
    problems: list[str] = []
    for entry in split_entries(text, kb):
        name, _, value = entry.partition(":")
        name, value = name.strip(), value.strip().lower()
        sid, suggestion = resolve_symptom(name, kb)
        if sid is None:
            if suggestion is not None:
                label = kb["symptoms"][suggestion]["label"]
                problems.append(f"Unknown symptom '{name}' - did you mean '{label}'?")
            else:
                problems.append(f"Unknown symptom '{name}' - not in the knowledge base.")
            continue
        if not value:
            value = default_value(kb, sid)
        elif value not in valid_values:
            problems.append(f"Invalid value '{value}' for '{name}' "
                            f"(use {', '.join(valid_values)}).")
            continue
        accepted[sid] = value
    return accepted, problems


def run_once(kb: dict, args: argparse.Namespace, color: bool) -> int:
    """Non-interactive consultation from --symptoms."""
    accepted, problems = parse_symptom_arg(kb, args.symptoms)
    result = diagnose(kb, accepted)
    print_result(kb, result, accepted, problems, color)
    if args.trace:
        print_trace(kb, result)
    if args.why_not:
        print_why_not(kb, result)
    return 0


# ------------------------------------------------------------------ interactive mode

def ask(prompt: str) -> str:
    """input() that echoes the answer when stdin is piped, so transcripts read well."""
    answer = input(prompt)
    if not sys.stdin.isatty():
        print(answer)
    return answer.strip()


def ask_yes_no(prompt: str) -> bool:
    """Ask until the user answers y/yes or n/no."""
    while True:
        answer = ask(prompt).lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer y or n.")


def ask_intensity(kb: dict, label: str) -> str:
    """Ask for mild/moderate/severe (levels come from the KB); Enter = moderate."""
    levels = [k for k in kb["meta"]["cf_conventions"]["intensity_cf"] if k != "yes"]
    default = "moderate" if "moderate" in levels else levels[len(levels) // 2]
    options = " ".join(f"[{i}] {name}" for i, name in enumerate(levels, 1))
    while True:
        answer = ask(f"How severe is your {label.lower()}? {options} (Enter = {default}): ").lower()
        if answer == "":
            return default
        if answer.isdigit() and 1 <= int(answer) <= len(levels):
            return levels[int(answer) - 1]
        if answer in levels:
            return answer
        print(f"Please enter a number from 1 to {len(levels)}, or press Enter.")


def print_symptom_list(kb: dict) -> None:
    """Show the numbered symptom list in two columns."""
    items = [f"{i:>2}. {s['label']}" for i, s in enumerate(kb["symptoms"].values(), 1)]
    rows = (len(items) + 1) // 2
    width = max(len(x) for x in items) + 4
    print("Known symptoms:")
    for r in range(rows):
        right = items[r + rows] if r + rows < len(items) else ""
        print("  " + items[r].ljust(width) + right)
    print()


def match_entry(kb: dict, ids: list[str], entry: str) -> Optional[str]:
    """Match one typed entry (list number, name, or close match) to a symptom id."""
    if entry.isdigit():
        number = int(entry)
        return ids[number - 1] if 1 <= number <= len(ids) else None
    sid, suggestion = resolve_symptom(entry, kb)
    if sid is None and suggestion is not None:
        label = kb["symptoms"][suggestion]["label"]
        if ask_yes_no(f"Did you mean '{label}'? (y/n) "):
            return suggestion
    return sid


def collect_symptoms(kb: dict) -> tuple[dict[str, str], list[str]]:
    """Run the interactive question flow; return ({id: value}, notes)."""
    ids = list(kb["symptoms"])
    print_symptom_list(kb)
    raw = ask("Enter your symptoms, separated by commas (names, numbers from the list, "
              "or Roman Urdu e.g. bukhar, khansi): ")
    chosen: list[str] = []
    notes: list[str] = []
    for entry in split_entries(raw, kb):
        sid = match_entry(kb, ids, entry)
        if sid is None:
            note = f"'{entry}' is not in the knowledge base and was ignored."
            print("  " + note)
            notes.append(note)
        elif sid not in chosen:
            chosen.append(sid)

    accepted: dict[str, str] = {}
    for sid in chosen:
        symptom = kb["symptoms"][sid]
        accepted[sid] = (ask_intensity(kb, symptom["label"])
                         if symptom["input"] == "intensity" else "yes")

    # Follow-up questions: symptoms that depend on a parent the user reported.
    for sid, symptom in kb["symptoms"].items():
        parent = symptom.get("ask_only_if")
        if parent and parent in accepted and sid not in accepted:
            if ask_yes_no(f"{symptom['label']}? (y/n) "):
                accepted[sid] = "yes"
    return accepted, notes


def consultation_menu(kb: dict, result: DiagnosisResult) -> bool:
    """Show the after-result menu; return True for a new consultation, False to quit."""
    while True:
        print("\n[1] Show reasoning trace  [2] Why other diseases were ruled out  "
              "[3] New consultation  [4] Quit")
        choice = ask("Choose 1-4: ")
        if choice == "1":
            print_trace(kb, result)
        elif choice == "2":
            print_why_not(kb, result)
        elif choice == "3":
            return True
        elif choice == "4":
            return False
        else:
            print("Please enter a number from 1 to 4.")


def run_interactive(kb: dict, color: bool) -> int:
    """Interactive loop: ask symptoms, diagnose, show result and menu."""
    print(paint("\nSymptom consultation (type Ctrl+C to exit)\n", "1;36", color))
    while True:
        accepted, notes = collect_symptoms(kb)
        if not accepted:
            print("\nNo recognised symptoms were entered, so no diagnosis can be made.")
            print("\n" + textwrap.fill("DISCLAIMER: " + kb["meta"]["disclaimer"], width=LINE_WIDTH))
            if ask_yes_no("\nStart a new consultation? (y/n) "):
                continue
            break
        result = diagnose(kb, accepted)
        print_result(kb, result, accepted, notes, color)
        if not consultation_menu(kb, result):
            break
    print("Goodbye.")
    return 0


# --------------------------------------------------------------------- entry points

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Define and parse the command-line options."""
    parser = argparse.ArgumentParser(description="Intelligent Medical Diagnosis Expert System")
    parser.add_argument("--symptoms", help='non-interactive, e.g. "bukhar:moderate, rash:yes"')
    parser.add_argument("--trace", action="store_true", help="also print the reasoning trace")
    parser.add_argument("--why-not", action="store_true", dest="why_not",
                        help="also explain why other diseases were ruled out")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colours")
    return parser.parse_args(argv)


def run(kb: dict, args: argparse.Namespace) -> int:
    """Run the CLI in the right mode and return the process exit code."""
    color = color_enabled(args)
    if args.symptoms is not None:
        return run_once(kb, args, color)
    try:
        return run_interactive(kb, color)
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye.")
        return 0
