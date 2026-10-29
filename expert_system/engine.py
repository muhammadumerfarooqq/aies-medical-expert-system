"""Generic forward-chaining inference engine with MYCIN-style certainty factors.

The engine contains NO medical knowledge: every symptom, disease, rule, CF and
threshold is read from the knowledge base (data/knowledge_base.json).

Termination: each cycle fires one rule, and a rule can fire again only when one
of its premise CFs changed. kb_verify forbids cycles in the rule graph, so CFs
settle after finitely many firings and the loop always reaches a fixed point.

The tests live in run_tests.py (python run_tests.py).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from dataclasses import asdict, dataclass, field
from typing import Optional

EPSILON = 1e-9  # tolerance for comparing floating-point CFs


# ---------------------------------------------------------------- data classes

@dataclass
class Firing:
    """One trace record: a single rule or red flag fired in one cycle."""
    cycle: int
    rule_id: str
    kind: str                         # "diagnostic" or "red_flag"
    conflict_set: list[str]           # rule ids, in conflict-resolution order
    premises: dict[str, float]        # premise id -> its CF at firing time
    min_premise_cf: float
    rule_cf: Optional[float]          # None for red flags
    contribution: Optional[float]     # rule_cf * min_premise_cf; None for red flags
    concluded_fact: Optional[str]     # None for red flags
    cf_before: Optional[float]        # fact CF before this firing
    cf_after: Optional[float]         # fact CF after this firing
    refire: bool                      # True if this rule had fired before


@dataclass
class DiseaseResult:
    """A disease that passed the display threshold, with its explanation."""
    disease_id: str
    name: str
    cf: float
    percent: float                    # relative % among the shown diseases
    severity: str
    description: str
    justification: list[str]          # indented lines: rules down to root symptoms
    treatment: list[str]
    prevention: list[str]
    sources: list[str]


@dataclass
class DiagnosisResult:
    """Everything the engine produces for one consultation."""
    diseases: list[DiseaseResult] = field(default_factory=list)   # ranked
    alerts: list[dict] = field(default_factory=list)              # red flags
    unknown_symptoms: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    why_not: dict[str, list[str]] = field(default_factory=dict)   # not-shown diseases
    disclaimer: str = ""
    trace: list[Firing] = field(default_factory=list)
    working_memory: dict[str, float] = field(default_factory=dict)
    # Diseases with 0 < CF < display threshold: {"disease_id", "name", "cf"}, best first.
    below_threshold: list[dict] = field(default_factory=list)
    # Unreported symptoms that block 2+ diseases: {"symptom_id", "label", "diseases": [names]}.
    missing_required: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return the whole result as plain dicts/lists (for tests and the GUI)."""
        return asdict(self)


# ------------------------------------------------------------------- CF helpers

def fmt(x: float, dp: int) -> str:
    """Format x with dp decimals, rounding halves UP (for display only).

    Python's f"{x:.2f}" works on the binary float, so 0.595 (stored as
    0.59499999...) prints as 0.59 instead of 0.60. Rounding to 9 decimals
    first removes that noise, then Decimal rounds half up as people expect.
    The raw CF values are never changed, only their text.
    """
    exact = Decimal(str(round(x, 9)))
    return str(exact.quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP))


def required_symptoms(kb: dict) -> dict[str, set[str]]:
    """For each disease, the root symptoms that EVERY derivation path needs.

    required(symptom) = {symptom}
    required(rule)    = union of required(premise) over the rule's IF premises
    required(fact or disease) = INTERSECTION of required(rule) over all rules
                                concluding it (any one rule may be used, so only
                                what all of them share is truly required).

    Example: A <- r1 [x, y], A <- r2 [x, z]  gives required(A) = {x}.
    """
    by_conclusion: dict[str, list[dict]] = {}
    for rule in kb["rules"]:
        by_conclusion.setdefault(rule["then"], []).append(rule)
    memo: dict[str, set[str]] = {}

    def required_for(item: str) -> set[str]:
        """Required root symptoms of one symptom, fact or disease (memoised)."""
        if item in kb["symptoms"]:
            return {item}
        if item not in memo:
            per_rule = []
            for rule in by_conclusion.get(item, []):
                needed: set[str] = set()
                for premise in rule["if"]:
                    needed |= required_for(premise)
                per_rule.append(needed)
            memo[item] = set.intersection(*per_rule) if per_rule else set()
        return memo[item]

    return {disease: required_for(disease) for disease in kb["diseases"]}


def combine_cfs(contributions: list[float]) -> float:
    """Combine rule contributions for one fact: CF = CF_old + c * (1 - CF_old)."""
    cf = 0.0
    for c in contributions:
        cf = cf + c * (1.0 - cf)
    return cf


def value_to_cf(value, intensity_cf: dict[str, float]) -> Optional[float]:
    """Convert a user value to a CF; 0.0 means absent ("no"), None means invalid."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if 0 < value <= 1 else None
    if isinstance(value, str):
        label = value.strip().lower()
        if label == "no":
            return 0.0
        return intensity_cf.get(label)
    return None


def parse_input(kb: dict, symptoms: dict) -> tuple[dict[str, float], list[str], list[str]]:
    """Validate user input; return (initial facts, unknown ids, warnings)."""
    table = kb["meta"]["cf_conventions"]["intensity_cf"]
    known = kb["symptoms"]
    facts: dict[str, float] = {}
    unknown: list[str] = []
    warnings: list[str] = []
    for sid, value in symptoms.items():
        if sid not in known:
            unknown.append(sid)
            warnings.append(f"Unknown symptom '{sid}' was ignored.")
            continue
        cf = value_to_cf(value, table)
        if cf is None:
            warnings.append(f"Invalid value {value!r} for '{sid}' was ignored.")
        elif cf > 0:
            facts[sid] = cf
    # A follow-up symptom only makes sense if its parent symptom is present.
    for sid in list(facts):
        parent = known[sid].get("ask_only_if")
        if parent and parent not in facts:
            del facts[sid]
            warnings.append(f"'{sid}' ignored because '{parent}' was not reported.")
    return facts, unknown, warnings


def compute_depths(kb: dict) -> dict[str, int]:
    """Rule depth = 1 + deepest rule concluding any of its premises (symptoms: 0)."""
    by_conclusion: dict[str, list[dict]] = {}
    for rule in kb["rules"]:
        by_conclusion.setdefault(rule["then"], []).append(rule)
    depths: dict[str, int] = {}

    def depth_of(rule: dict) -> int:
        """Memoised depth of one rule (recursion ends: the rule graph is acyclic)."""
        if rule["id"] not in depths:
            deepest = 0
            for premise in rule["if"]:
                for producer in by_conclusion.get(premise, []):
                    deepest = max(deepest, depth_of(producer))
            depths[rule["id"]] = 1 + deepest
        return depths[rule["id"]]

    for rule in kb["rules"] + kb["red_flags"]:
        depth_of(rule)
    return depths


def is_eligible(previous: Optional[tuple], current: tuple) -> bool:
    """Refraction: eligible if never fired, or a premise CF changed since."""
    if previous is None:
        return True
    return any(abs(a - b) > EPSILON for a, b in zip(previous, current))


# --------------------------------------------------------------- forward chaining

def run_forward_chaining(kb: dict, initial: dict[str, float]):
    """Run the recognize-act loop; return (memory, last_firing, contributions, trace, alerts)."""
    threshold = kb["meta"]["cf_conventions"]["rule_fire_threshold"]
    depths = compute_depths(kb)
    items = [("diagnostic", r) for r in kb["rules"]] + [("red_flag", r) for r in kb["red_flags"]]
    json_order = {rule["id"]: i for i, (_, rule) in enumerate(items)}

    # STEP 1: start with the initial facts (working memory = {id: cf}).
    memory: dict[str, float] = dict(initial)
    contributions: dict[str, dict[str, float]] = {}   # fact -> {rule_id: contribution}
    last_fired: dict[str, tuple] = {}                 # rule_id -> premise CFs when it fired
    last_firing: dict[str, Firing] = {}               # rule_id -> its latest trace record
    trace: list[Firing] = []
    alerts: list[dict] = []

    def resolution_key(entry):
        """Sort key: priority high first, then shallow rules, then JSON order."""
        rule = entry[1]
        return (-rule["priority"], depths[rule["id"]], json_order[rule["id"]])

    cycle = 0
    while True:
        # STEP 2: match - collect every rule/red flag that can fire now.
        conflict = []
        for kind, rule in items:
            if any(p not in memory for p in rule["if"]):
                continue
            cfs = tuple(memory[p] for p in rule["if"])
            if min(cfs) < threshold - EPSILON:
                continue
            if is_eligible(last_fired.get(rule["id"]), cfs):
                conflict.append((kind, rule, cfs))

        # STEP 5: stop at the fixed point (nothing left to fire).
        if not conflict:
            break

        # STEP 3: conflict resolution - choose ONE rule.
        conflict.sort(key=resolution_key)
        kind, rule, cfs = conflict[0]
        cycle += 1
        premises = dict(zip(rule["if"], cfs))
        min_cf = min(cfs)

        # STEP 4: act - fire the chosen rule.
        if kind == "diagnostic":
            fact = rule["then"]
            contribution = rule["cf"] * min_cf
            before = memory.get(fact, 0.0)
            # Replace this rule's old contribution (never count it twice).
            contributions.setdefault(fact, {})[rule["id"]] = contribution
            after = combine_cfs(list(contributions[fact].values()))
            memory[fact] = after
            firing = Firing(cycle, rule["id"], kind, [c[1]["id"] for c in conflict],
                            premises, min_cf, rule["cf"], contribution, fact,
                            before, after, rule["id"] in last_fired)
        else:
            # Red flag: record an alert only; no fact is added.
            alerts.append({"id": rule["id"], "message": rule["message"],
                           "source": rule.get("source", ""), "symptoms": premises})
            firing = Firing(cycle, rule["id"], kind, [c[1]["id"] for c in conflict],
                            premises, min_cf, None, None, None, None, None, False)
        last_fired[rule["id"]] = cfs
        last_firing[rule["id"]] = firing
        trace.append(firing)
    return memory, last_firing, contributions, trace, alerts


# ------------------------------------------------------------------ explanations

def display_name(kb: dict, item_id: str) -> str:
    """Human-readable name: symptom label, disease name, or prettified fact id."""
    if item_id in kb["symptoms"]:
        return kb["symptoms"][item_id]["label"]
    if item_id in kb["diseases"]:
        return kb["diseases"][item_id]["name"]
    return item_id.replace("_", " ").capitalize()   # "some_fact_id" -> "Some fact id"


def explain_fact(kb: dict, fact: str, memory: dict, contributions: dict,
                 last_firing: dict, indent: int = 0) -> list[str]:
    """Justify a fact: its supporting rules, expanded down to root symptoms."""
    pad = "  " * indent
    rule_ids = list(contributions.get(fact, {}))
    header = f"{pad}{display_name(kb, fact)}: CF {fmt(memory[fact], 3)}"
    if len(rule_ids) > 1:
        parts = ", ".join(f"{r} {fmt(contributions[fact][r], 3)}" for r in rule_ids)
        header += f" (combined from {len(rule_ids)} rules: {parts})"
    lines = [header]
    for rid in rule_ids:
        f = last_firing[rid]
        prem = ", ".join(f"{display_name(kb, p)} {fmt(cf, 3)}" for p, cf in f.premises.items())
        lines.append(f"{pad}  {rid} [{prem}] -> min {fmt(f.min_premise_cf, 3)} x "
                     f"rule CF {fmt(f.rule_cf, 2)} = {fmt(f.contribution, 3)}")
        for premise in f.premises:
            if premise in contributions:
                lines.extend(explain_fact(kb, premise, memory, contributions,
                                          last_firing, indent + 2))
    return lines


def why_not_fact(kb: dict, fact: str, memory: dict, indent: int = 0) -> list[str]:
    """Explain a missing fact: for each rule that could conclude it, what is present/missing."""
    pad = "  " * indent
    threshold = kb["meta"]["cf_conventions"]["rule_fire_threshold"]
    lines: list[str] = []
    for rule in kb["rules"]:
        if rule["then"] != fact:
            continue
        needs = ", ".join(display_name(kb, p) for p in rule["if"])
        lines.append(f"{pad}{rule['id']} needs {needs}")
        for premise in rule["if"]:
            name = display_name(kb, premise)
            if premise in memory and memory[premise] < threshold - EPSILON:
                lines.append(f"{pad}  {name}: present but too weak to fire a rule "
                             f"(CF {fmt(memory[premise], 2)} < {threshold})")
            elif premise in memory:
                lines.append(f"{pad}  {name}: present (CF {fmt(memory[premise], 3)})")
            elif premise in kb["symptoms"]:
                lines.append(f"{pad}  {name}: missing")
            else:
                lines.append(f"{pad}  {name}: not derived")
                lines.extend(why_not_fact(kb, premise, memory, indent + 2))
    return lines


# ----------------------------------------------------------------------- diagnose

def diagnose(kb: dict, symptoms: dict) -> DiagnosisResult:
    """Run a full consultation: validate input, forward-chain, rank and explain."""
    conv = kb["meta"]["cf_conventions"]
    initial, unknown, warnings = parse_input(kb, symptoms)
    memory, last_firing, contributions, trace, alerts = run_forward_chaining(kb, initial)

    # Diseases reaching the display threshold, ranked severity first, then CF.
    shown = [d for d in kb["diseases"]
             if memory.get(d, 0.0) >= conv["display_threshold"] - EPSILON]
    rank = kb["meta"]["severity_rank"]
    shown.sort(key=lambda d: (-rank[kb["diseases"][d]["severity"]],
                              -round(memory[d], 9), kb["diseases"][d]["name"]))
    total = sum(memory[d] for d in shown)

    result = DiagnosisResult(alerts=alerts, unknown_symptoms=unknown, warnings=warnings,
                             disclaimer=kb["meta"]["disclaimer"], trace=trace,
                             working_memory=dict(memory))
    for did in shown:
        info = kb["diseases"][did]
        result.diseases.append(DiseaseResult(
            did, info["name"], memory[did], memory[did] / total * 100, info["severity"],
            info["description"], explain_fact(kb, did, memory, contributions, last_firing),
            info["treatment"], info["prevention"], info["sources"]))

    # "Why not" for every disease that was not shown.
    for did in kb["diseases"]:
        if did in shown:
            continue
        if memory.get(did, 0.0) > 0:
            result.below_threshold.append(
                {"disease_id": did, "name": kb["diseases"][did]["name"], "cf": memory[did]})
            result.why_not[did] = [f"CF {fmt(memory[did], 3)} is below the display "
                                   f"threshold {conv['display_threshold']}"]
        else:
            result.why_not[did] = why_not_fact(kb, did, memory)
    result.below_threshold.sort(key=lambda item: -item["cf"])

    # Required symptoms that were not reported and block 2+ diseases (explanation only).
    # Only when the user reported something: with no input there is nothing to hint about.
    needs = required_symptoms(kb)
    blocked: dict[str, list[str]] = {}
    for did in kb["diseases"]:
        if initial and did not in shown:
            for sid in needs[did]:
                if sid not in initial:
                    blocked.setdefault(sid, []).append(did)
    for sid, dids in blocked.items():
        if len(dids) >= 2:
            result.missing_required.append({
                "symptom_id": sid, "label": kb["symptoms"][sid]["label"],
                "diseases": [kb["diseases"][d]["name"] for d in dids]})
    return result


if __name__ == "__main__":
    print("Run: python run_tests.py")
