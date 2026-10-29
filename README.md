# Intelligent Medical Diagnosis Expert System

A rule-based expert system for medical diagnosis. The knowledge base is stored in JSON and is processed by a generic forward-chaining inference engine. Conclusions carry MYCIN-style certainty factors, and a hybrid backward-chaining mode asks the user only for the facts it still needs. The system is used through a command-line interface, with an optional Streamlit GUI.

## Course

Artificial Intelligence & Expert Systems (AIES), Fall 2026, NED University

## Project Structure

```
AIES-CCP/
├── app.py                   # Streamlit GUI (presentation only)
├── main.py                  # Entry point: verifies the KB, then starts the CLI
├── expert_system/
│   ├── __init__.py          # Package marker for the engine code
│   ├── kb_verify.py         # Loads the KB and checks its consistency (8 checks)
│   ├── engine.py            # Generic forward-chaining inference engine (no medical names)
│   ├── backward.py          # Backward chaining: generates questions when two diseases are close
│   └── cli.py               # Command-line interface (interactive and --symptoms modes)
├── data/
│   └── knowledge_base.json  # The knowledge base: symptoms, diseases, rules, red flags
├── run_tests.py             # Test runner: python run_tests.py [--verbose]
├── tests/
│   ├── cases.json           # 14 clinical test cases written from WHO/CDC descriptions
│   └── regression.json      # 7 regression cases with exact expected CFs
├── docs/
│   ├── kb_design.md         # Design document: source of truth for the KB
│   ├── diagrams/.gitkeep    # Architecture and flow diagrams for the report
│   └── screenshots/.gitkeep # Screenshots of the running system for the report
├── .streamlit/config.toml   # GUI theme (no secrets; secrets.toml is git-ignored)
├── .gitignore               # Keeps caches, virtual envs, secrets and temp files out of git
├── .gitattributes           # Line-ending rules (LF for Python files)
├── requirements.txt         # streamlit (GUI only); everything else is standard library
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
- 23 rules: 20 diagnostic rules and 3 red-flag rules
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

This runs the 8 consistency checks (unknown symptoms, bad THEN targets, unused facts, incomplete diseases, invalid CFs/priorities, CF overcounting, unreachable diseases, rule cycles). On success it prints `KB verified: 6 diseases, 20 symptoms, 7 intermediate facts, 23 rules`; otherwise it lists every error and exits with code 1. `main.py` runs the same check at startup.

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

The result also lists `below_threshold`: diseases with some evidence (0 < CF < 0.30) that were not shown. The engine has no built-in demo; run the tests with `python run_tests.py` (see Testing).

## Using the CLI

`expert_system/cli.py` is generic: every symptom name, label, synonym, disease and message comes from the knowledge base.

**Interactive mode** (`python main.py`):

1. A numbered list of the known symptoms is shown.
2. Enter symptoms separated by commas, as names, list numbers, or Roman Urdu synonyms (for example `bukhar, khansi`). An exact match is accepted. A close match asks `Did you mean 'Headache'? (y/n)`. Anything else is reported as not in the knowledge base.
3. For each intensity symptom you pick `[1] mild [2] moderate [3] severe` (Enter = moderate). Yes/no symptoms count as "yes".
4. Follow-up questions come from the KB: if you reported fever, you are asked `Fever lasting more than 3 days? (y/n)`.
5. The result is printed (format below), followed by a menu: `[1]` reasoning trace, `[2]` why other diseases were ruled out, `[3]` new consultation, `[4]` quit. Ctrl+C or end of input exits cleanly.

**Non-interactive mode** (for screenshots and tests):

```
python main.py --symptoms "bukhar:moderate, rash:yes, eye pain, zukam:mild"
python main.py --symptoms "fever, cough, breathlessness, chest pain" --trace
python main.py --symptoms "fever, headche, ulti, body pain" --why-not
```

Symptoms can be separated by commas, "and", "aur", "&" or "+" (for example `bukhar aur sir dard`); this works in both modes. Each entry is `name[:value]` where value is `mild`, `moderate`, `severe`, `yes` or `no`. The default is `moderate` for intensity symptoms and `yes` for yes/no symptoms. Close matches are never auto-accepted; they are reported as `Unknown symptom 'headche' - did you mean 'Headache'?`. Follow-up symptoms are used only if you give them explicitly (for example `prolonged fever:yes`).

| Flag | Meaning |
|---|---|
| `--symptoms "..."` | run once without questions |
| `--trace` | also print the forward-chaining trace |
| `--why-not` | also explain why the other diseases were ruled out |
| `--no-color` | disable ANSI colours (colour is used only on a real terminal) |

**Synonyms:** each symptom in the KB lists English and Roman Urdu synonyms (`bukhar`, `khansi`, `zukam`, `ulti`, `pait dard`, `kamzori`, ...). Adding a synonym to the JSON makes it work in the CLI with no code change.

**Result format** (same in both modes): red-flag alerts first (framed with `!` lines and an `EMERGENCY:` prefix), the recognised symptoms, a ranked table (rank, disease, severity, confidence %, CF), then for each disease its description, the reasoning ("Why this was suggested"), treatment, prevention and sources. Unknown symptoms and warnings follow. If no disease reaches the confidence threshold (30%, from the KB) the CLI says there is not enough evidence, plus a hint when a required symptom was not reported (for example, fever is required by several diseases in this KB). The disclaimer is always last.

## Testing

```
python run_tests.py            # add --verbose to print the full diagnosis of failing cases
```

The runner prints eight sections as tables, a summary, and `TOTAL: x/y passed`. The exit code is 1 if anything fails.

| Section | What it proves |
|---|---|
| [1] KB verification | the knowledge base passes all 8 consistency checks |
| [2] Clinical cases | 13 cases in `tests/cases.json`, written from WHO/CDC symptom descriptions (the source quote is stored with each case), not from our own rules. They check the most likely disease, ranking, red-flag alerts, unknown symptoms and edge cases |
| [3] Regression | 7 cases in `tests/regression.json` with exact expected CFs (tolerance 0.001), so any accidental change to a rule or CF is noticed |
| [4] CLI input parsing | separators ("and", "aur", "&"), Roman Urdu synonyms, no splitting on "or", and "did you mean" suggestions |
| [5] Verifier self-tests | deliberately broken copies of the KB (kept in memory only) are caught by `kb_verify` |
| [6] Order independence | shuffling the order of rules and red flags (50 fixed seeds) never changes any CF |
| [7] Hybrid backward chaining | close calls are detected, questions are generated from the rules in the right order, scripted answers separate the diseases, no symptom is asked twice, and `backward.py` contains no disease or symptom names |
| [8] GUI smoke tests | `app.py` loads without errors, the T01 example gives Dengue, a close case shows the close-call warning and a bleeding-gums question, and the knowledge base tab shows 23 rules (skipped if streamlit is not installed) |

A failing clinical case is a finding about the knowledge base, not a reason to edit the test.

**Example of the iterative development cycle:** test T02 (WHO: "the most common early symptoms of malaria are fever, headache and chills") originally failed because no rule accepted that combination. The cause was found (the old R8 needed chills AND sweating), the rule was split (R8 now needs only chills; new R20 covers sweating), and all 78 tests passed again. The change and the rejected alternative (a rule that would double-count evidence and be refused by `kb_verify`) are recorded in section 13 of `docs/kb_design.md`.

## Hybrid reasoning (forward + backward chaining)

`expert_system/backward.py` adds backward chaining on top of the forward-chaining engine. It contains no disease or symptom names: every question is generated from the rules.

**When it triggers:** after forward chaining, if at least two diseases are shown and the top two (by CF) are close, meaning `gap = (cf_a - cf_b) / (cf_a + cf_b) * 100 <= 15`. At most 3 questions are asked.

**The 5 backward-chaining steps** (labelled in the code):

1. Start with a goal: each of the two close diseases.
2. Search for rules whose THEN part is the goal.
3. Check each IF condition: a symptom already reported (CF at or above the firing threshold) is true.
4. Not known: an intermediate fact becomes a sub-goal (steps 2 to 4 again); an unreported symptom becomes a question.
5. Repeat until every sub-goal has been explored.

**Why proven sub-goals are still explored:** the aim is not to prove one hypothesis but to find additional evidence that separates two hypotheses. A sub-goal that is already proven may still have other rules that a new answer would strengthen.

Symptoms already reported or denied, symptoms whose `ask_only_if` parent was not reported, and symptoms that appear under both goals (they do not discriminate) are never asked. Questions are ordered by: completes a rule first, then higher rule CF, then the higher-CF disease, then KB rule order. After every answer, forward chaining runs again.

**Example (interactive):**

```
HYBRID REASONING: Backward chaining
Dengue 50.0% vs Malaria 50.0% are too close (gap 0.0 <= 15). Asking up to 3 questions to tell them apart.

Why I'm asking: Dengue <- R7 needs Dengue signs <- R6 needs Bleeding gums or nose
Bleeding gums or nose? (y/n) y
  Updated ranking: Dengue 62.5% (CF 0.63), Malaria 37.5% (CF 0.38)

Outcome: The diseases are now clearly separated.
```

The full final result is then printed, so new red-flag alerts (here the bleeding warning) appear. Menu option `[5]` shows the backward-chaining steps again.

**Non-interactive:** without `--answers`, the CLI lists the questions that would be asked, with their rule paths. With `--answers` the session runs using your answers (same parsing and synonyms as `--symptoms`); a question not covered by `--answers` stops the session.

```
python main.py --symptoms "fever, headache, ulti, badan dard"
python main.py --symptoms "fever, headache, ulti, badan dard" --answers "bleeding gums:yes"
```

## Graphical interface

The GUI is optional and needs Python 3.11+ (the engine, CLI and tests run on 3.10+ with no installs).

```
pip install -r requirements.txt
python -m streamlit run app.py
```

`app.py` is presentation only: all reasoning, ranking, symptom matching and text come from the `expert_system` package and the knowledge base.

| Tab | What it shows |
|---|---|
| Diagnosis | Example cases, symptom picker, free-text input (English or Roman Urdu, with "Did you mean?"), intensity controls and follow-up questions. Results: red-flag alerts first, the ranked table with confidence bars and severity badges, the backward-chaining panel (one question at a time when two diseases are close), and an expander per disease with its justification, treatment, prevention and sources |
| Reasoning trace | One row per forward-chaining cycle: conflict set, fired rule, concluded fact, CF before and after, re-fire |
| Why not | Why each disease that was not shown was ruled out |
| Backward chaining | The questions asked, why they were asked, the answers, and the ranking after each |
| Knowledge base | Counts, rules (filterable by disease), diseases, symptoms and red flags |

When no disease is shown, the Diagnosis tab shows the same required-symptom hint as the CLI.

The GUI is covered by headless smoke tests (section [8] of `python run_tests.py`); they are skipped automatically if streamlit is not installed.

## Progress

- [x] Phase 0: Setup
- [x] Phase 1: Knowledge Base
- [x] Phase 2: Inference Engine
- [x] Phase 3: CLI
- [x] Phase 4: Tests
- [x] Phase 5: Hybrid Backward Chaining
- [x] Phase 6: Streamlit GUI
- [ ] Phase 7: Screenshots
- [ ] Phase 8: Report & Title Page
- [ ] Phase 9: Review & Submission

## Disclaimer

This is an educational project only. It is not medical advice and must not be used to diagnose or treat any condition. Consult a qualified healthcare professional for medical concerns.
