"""Knowledge-base loader and consistency checker.

Run with:  python -m expert_system.kb_verify

The checks follow section 9 of docs/kb_design.md. They run before the
inference engine ever sees the knowledge base, so a bad rule is caught at
startup instead of producing a wrong diagnosis.
"""

import json
import sys
from pathlib import Path

# <project root>/data/knowledge_base.json, located from this file's own path
# so it works no matter which directory the program is started from.
DEFAULT_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_base.json"

VALID_SEVERITIES = ("mild", "moderate", "severe")


def load_kb(path=None):
    """Read the knowledge base JSON file and return it as a dict.

    path: optional file path; defaults to <project root>/data/knowledge_base.json.
    """
    kb_path = Path(path) if path is not None else DEFAULT_KB_PATH
    with open(kb_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_number(value):
    """True for int/float values; bool is excluded (True would pass as 1)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _root_symptoms(premises, rules_by_conclusion, symptoms, visiting=frozenset()):
    """Return the set of ROOT symptoms reachable from a list of premises.

    A premise that is a symptom is itself a root. A premise that is an
    intermediate fact is expanded recursively through every rule that
    concludes it. 'visiting' holds the facts being expanded right now, so a
    cyclic KB cannot cause infinite recursion (cycles are reported by check 8).
    """
    roots = set()
    for premise in premises:
        if premise in symptoms:
            roots.add(premise)
        elif premise in rules_by_conclusion and premise not in visiting:
            for rule in rules_by_conclusion[premise]:
                roots |= _root_symptoms(
                    rule.get("if", []),
                    rules_by_conclusion,
                    symptoms,
                    visiting | {premise},
                )
    return roots


def _find_cycle(edges):
    """Return one cycle as a list of fact ids (first == last), or None.

    edges maps each fact to the facts it feeds (premise -> conclusion).
    Uses depth-first search with three colours: unvisited, on the current
    path (grey), finished (black). Meeting a grey node means a cycle.
    """
    grey, black = 1, 2
    colour = {}

    def visit(node, path):
        colour[node] = grey
        path.append(node)
        for nxt in edges.get(node, ()):
            if colour.get(nxt) == grey:
                return path[path.index(nxt):] + [nxt]
            if nxt not in colour:
                found = visit(nxt, path)
                if found:
                    return found
        path.pop()
        colour[node] = black
        return None

    for start in list(edges):
        if start not in colour:
            found = visit(start, [])
            if found:
                return found
    return None


def verify_kb(kb):
    """Run all consistency checks on a loaded knowledge base.

    Returns (ok, errors, stats):
      ok     - True when no errors were found
      errors - list of human-readable messages, each naming the item involved
      stats  - counts used for the success line
    """
    errors = []
    symptoms = kb.get("symptoms", {})
    diseases = kb.get("diseases", {})
    facts = kb.get("intermediate_facts", {})
    rules = kb.get("rules", [])
    red_flags = kb.get("red_flags", [])

    # Structural sanity: ids must not repeat, and a name can only be one kind
    # of thing (otherwise "THEN x" would be ambiguous).
    seen_ids = set()
    for item in rules + red_flags:
        item_id = item.get("id", "<no id>")
        if item_id in seen_ids:
            errors.append(f"Duplicate rule id {item_id}")
        seen_ids.add(item_id)
    for name in set(symptoms) & set(diseases) | set(symptoms) & set(facts) | set(diseases) & set(facts):
        errors.append(f"Id '{name}' is used for more than one kind of item (symptom/disease/fact)")
    for sid, sym in symptoms.items():
        parent = sym.get("ask_only_if")
        if parent is not None and parent not in symptoms:
            errors.append(f"Symptom {sid}: ask_only_if refers to unknown symptom '{parent}'")

    # Check 1: every premise of a rule or red flag is a known symptom
    # (rules may also use intermediate facts; red flags only symptoms).
    for rule in rules:
        for premise in rule.get("if", []):
            if premise not in symptoms and premise not in facts:
                errors.append(
                    f"Rule {rule.get('id')}: IF uses unknown symptom/fact '{premise}'"
                )
    for flag in red_flags:
        for premise in flag.get("if", []):
            if premise not in symptoms:
                errors.append(f"Red flag {flag.get('id')}: IF uses unknown symptom '{premise}'")

    # Check 2: every rule concludes a disease or an intermediate fact.
    for rule in rules:
        then = rule.get("then")
        if then not in diseases and then not in facts:
            errors.append(f"Rule {rule.get('id')}: THEN '{then}' is neither a disease nor an intermediate fact")

    # Index rules by what they conclude (used by checks 3, 6, 7).
    rules_by_conclusion = {}
    for rule in rules:
        rules_by_conclusion.setdefault(rule.get("then"), []).append(rule)

    # Check 3: each intermediate fact is produced by a rule and used by a rule.
    used_premises = {p for rule in rules for p in rule.get("if", [])}
    for fid in facts:
        if fid not in rules_by_conclusion:
            errors.append(f"Intermediate fact {fid} is never produced by any rule")
        if fid not in used_premises:
            errors.append(f"Intermediate fact {fid} is never used by any rule")

    # Check 4: every disease has severity, description, treatment, prevention, source.
    for did, disease in diseases.items():
        if disease.get("severity") not in VALID_SEVERITIES:
            errors.append(f"Disease {did}: severity must be one of {', '.join(VALID_SEVERITIES)}")
        if not disease.get("description"):
            errors.append(f"Disease {did}: missing description")
        if not disease.get("treatment"):
            errors.append(f"Disease {did}: missing treatment")
        if not disease.get("prevention"):
            errors.append(f"Disease {did}: missing prevention")
        if not disease.get("sources"):
            errors.append(f"Disease {did}: missing sources")

    # Check 5: CFs are numbers in (0, 1]; priorities are integers.
    for rule in rules:
        cf = rule.get("cf")
        if not _is_number(cf) or not 0 < cf <= 1:
            errors.append(f"Rule {rule.get('id')}: CF {cf!r} must be a number in (0, 1]")
    for item in rules + red_flags:
        priority = item.get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool):
            errors.append(f"Rule {item.get('id')}: priority {priority!r} must be an integer")

    # Check 6: no CF overcounting. When several rules conclude the same
    # fact, CFs are combined as if the evidence were independent, so the
    # rules must not share any root symptom.
    for fact, concluding in rules_by_conclusion.items():
        if len(concluding) < 2:
            continue
        roots = [
            _root_symptoms(r.get("if", []), rules_by_conclusion, symptoms)
            for r in concluding
        ]
        for i in range(len(concluding)):
            for j in range(i + 1, len(concluding)):
                shared = roots[i] & roots[j]
                if shared:
                    errors.append(
                        f"CF overcounting: rules {concluding[i].get('id')} and "
                        f"{concluding[j].get('id')} both conclude '{fact}' and share "
                        f"root symptom(s) {', '.join(sorted(shared))}"
                    )

    # Check 7: every disease is concluded by at least one rule.
    for did in diseases:
        if did not in rules_by_conclusion:
            errors.append(f"Disease {did} is not reachable: no rule concludes it")

    # Check 8: the fact-to-fact graph (premise -> conclusion) has no cycle.
    edges = {}
    for rule in rules:
        for premise in rule.get("if", []):
            if premise in facts:
                edges.setdefault(premise, set()).add(rule.get("then"))
    cycle = _find_cycle(edges)
    if cycle:
        errors.append("Rule cycle detected: " + " -> ".join(cycle))

    stats = {
        "diseases": len(diseases),
        "symptoms": len(symptoms),
        "intermediate_facts": len(facts),
        "rules": len(rules) + len(red_flags),
    }
    return (not errors), errors, stats


def format_success(stats):
    """Build the one-line success message from the stats dict."""
    return (
        f"KB verified: {stats['diseases']} diseases, {stats['symptoms']} symptoms, "
        f"{stats['intermediate_facts']} intermediate facts, {stats['rules']} rules"
    )


def main():
    """Load and verify the default KB; print the result and exit 1 on errors."""
    ok, errors, stats = verify_kb(load_kb())
    if ok:
        print(format_success(stats))
        return 0
    for error in errors:
        print(f"ERROR: {error}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
