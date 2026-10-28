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
│   └── kb_verify.py         # Loads the KB and checks its consistency (8 checks)
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

## Progress

- [x] Phase 0: Setup
- [x] Phase 1: Knowledge Base
- [ ] Phase 2: Inference Engine
- [ ] Phase 3: CLI
- [ ] Phase 4: Tests
- [ ] Phase 5: Hybrid Backward Chaining
- [ ] Phase 6: Streamlit GUI
- [ ] Phase 7: Screenshots
- [ ] Phase 8: Report & Title Page
- [ ] Phase 9: Review & Submission

## Disclaimer

This is an educational project only. It is not medical advice and must not be used to diagnose or treat any condition. Consult a qualified healthcare professional for medical concerns.
