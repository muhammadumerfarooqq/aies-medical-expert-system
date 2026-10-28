# Intelligent Medical Diagnosis Expert System

A rule-based expert system for medical diagnosis. The knowledge base is stored in JSON and is processed by a generic forward-chaining inference engine. Conclusions carry MYCIN-style certainty factors, and a hybrid backward-chaining mode asks the user only for the facts it still needs. The system is used through a command-line interface, with an optional Streamlit GUI.

## Course

Artificial Intelligence & Expert Systems (AIES), Fall 2026, NED University

## Project Structure

```
AIES-CCP/
├── main.py                  # Entry point (loads and verifies the KB; no diagnosis yet)
├── expert_system/
│   ├── __init__.py          # Package marker for the engine code
│   ├── kb_verify.py         # Loads the KB and checks its consistency (8 checks)
│   └── engine.py            # Generic forward-chaining inference engine + Checkpoint A demo
├── data/
│   └── knowledge_base.json  # The knowledge base: symptoms, diseases, rules, red flags
├── tests/.gitkeep           # Test cases go here (Phase 4)
├── docs/
│   ├── kb_design.md         # Design document: source of truth for the KB
│   ├── diagrams/.gitkeep    # Architecture and flow diagrams for the report
│   └── screenshots/.gitkeep # Screenshots of the running system for the report
├── .gitignore               # Keeps caches, virtual envs, secrets and temp files out of git
├── .gitattributes           # Line-ending rules (LF for Python files)
├── requirements.txt         # Dependencies (none yet; standard library only)
└── README.md                # This file
```

## How to Run

Requires Python 3.10+. No installs needed.

```
python main.py
```

## Knowledge Base

`data/knowledge_base.json` holds all medical knowledge; the engine itself contains none. It contains:

- 6 diseases (pneumonia, dengue, malaria, typhoid, influenza, common cold) with severity, description, treatment, prevention and sources
- 20 symptoms with labels, input type (intensity or yes/no) and synonyms (including Roman Urdu)
- 7 intermediate facts (e.g. `dengue_signs`) that allow rule chaining
- 22 rules: 19 diagnostic rules and 3 red-flag rules
- the sources (WHO, CDC, textbook references) and the disclaimer

**Factual vs heuristic knowledge:** factual knowledge is the disease descriptions, severities, symptom definitions, treatments, prevention and red-flag warnings. Heuristic knowledge is the diagnostic rules and their certainty factors, which are rules of thumb assigned by the knowledge engineers, not clinically validated probabilities. Every item in the JSON is tagged with its `knowledge_type`.

**Certainty factor (CF) conventions (MYCIN model):**

| Item | Value |
|---|---|
| Symptom intensity to CF | mild 0.4, moderate 0.7, severe 1.0; yes/no "yes" = 1.0 |
| Rule fires only if | min(premise CFs) >= 0.2 |
| CF of a fired rule's conclusion | rule CF x min(premise CFs) |
| Two rules supporting the same fact | CF_new = CF_old + CF_rule x (1 - CF_old) |
| Disease shown to the user if | CF >= 0.30 |
| Ranking | severity first (severe > moderate > mild), then CF |

**Verifying the knowledge base:**

```
python -m expert_system.kb_verify
```

This runs the 8 consistency checks (unknown symptoms, bad THEN targets, unused facts, incomplete diseases, invalid CFs/priorities, CF overcounting, unreachable diseases, rule cycles). On success it prints `KB verified: 6 diseases, 20 symptoms, 7 intermediate facts, 22 rules`; otherwise it lists every error and exits with code 1. `main.py` runs the same check at startup.

## Inference Engine

`expert_system/engine.py` is generic: it contains no disease, symptom or rule names, so a 7th disease added to the JSON works with no engine change. `diagnose(kb, symptoms)` takes symptom IDs with an intensity label (`mild`/`moderate`/`severe`/`yes`) or a number in (0, 1], and returns a `DiagnosisResult` (also available as a plain dict via `to_dict()`). Unknown symptoms and invalid values are never dropped silently; they are reported in `unknown_symptoms` / `warnings`. A symptom with `ask_only_if` (e.g. `fever_more_than_3_days`) is ignored with a warning when its parent symptom is absent.

**Forward-chaining loop (one rule fires per cycle):**

1. Start with the initial facts: working memory = {symptom: CF}.
2. Match: the conflict set is every rule and red flag whose premises are all in working memory with min(premise CFs) >= 0.2 and which is eligible under refraction.
3. Conflict resolution: pick one by (a) priority, highest first, (b) rule depth, shallowest first, (c) order in the JSON. Rule depth = 1 + the deepest rule that concludes one of its premises (symptoms have depth 0).
4. Act: a diagnostic rule adds a contribution `rule CF x min(premise CFs)`; a red flag records an alert and adds no fact.
5. Repeat steps 2 to 4 until the conflict set is empty (fixed point). This always terminates because `kb_verify` forbids rule cycles.

**Refraction and re-firing:** a rule fires once per premise state. It becomes eligible again only if one of its premise CFs changed since it last fired. When it re-fires, its old contribution is replaced, never added twice. Red flags fire at most once.

**CF formulas and thresholds:** a fact's CF combines all its rules' latest contributions with `CF = CF_old + c x (1 - CF_old)`. A disease is shown if its CF >= 0.30. Its relative % is its CF divided by the sum of the shown CFs, times 100. Diseases are ranked by severity (severe > moderate > mild), then CF, then name.

**Explanations:** every shown disease carries a justification (the rules supporting it, expanded down to root symptoms, with the CF arithmetic) plus severity, treatment, prevention and sources. Every disease that is not shown carries a "why not": either its CF is below the threshold, or which symptoms each possible rule still needs (present or missing). The result also holds the red-flag alerts, the disclaimer, the full firing trace and the final working memory.

**Run the demo / Checkpoint A** (seven acceptance cases, PASS/FAIL each):

```
python -m expert_system.engine
```

## Progress

- [x] Phase 0: Setup
- [x] Phase 1: Knowledge Base
- [x] Phase 2: Inference Engine
- [ ] Phase 3: CLI
- [ ] Phase 4: Tests
- [ ] Phase 5: Hybrid Backward Chaining
- [ ] Phase 6: Streamlit GUI
- [ ] Phase 7: Screenshots
- [ ] Phase 8: Report & Title Page
- [ ] Phase 9: Review & Submission

## Disclaimer

This is an educational project only. It is not medical advice and must not be used to diagnose or treat any condition. Consult a qualified healthcare professional for medical concerns.
