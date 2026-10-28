# Intelligent Medical Diagnosis Expert System

A rule-based expert system for medical diagnosis. The knowledge base is stored in JSON and is processed by a generic forward-chaining inference engine. Conclusions carry MYCIN-style certainty factors, and a hybrid backward-chaining mode asks the user only for the facts it still needs. The system is used through a command-line interface, with an optional Streamlit GUI.

## Course

Artificial Intelligence & Expert Systems (AIES), Fall 2026, NED University

## Project Structure

```
AIES-CCP/
├── main.py                  # Program entry point (placeholder in Phase 0)
├── expert_system/
│   └── __init__.py          # Package marker for the engine code
├── data/.gitkeep            # Knowledge base JSON goes here (Phase 1)
├── tests/.gitkeep           # Test cases go here (Phase 4)
├── docs/
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

## Progress

- [x] Phase 0: Setup
- [ ] Phase 1: Knowledge Base
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
