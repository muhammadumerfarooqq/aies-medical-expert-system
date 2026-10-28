# Knowledge Base Design — Intelligent Medical Diagnosis Expert System

**Course:** AIES (Artificial Intelligence & Expert Systems), Fall 2026, NED University
**Group:** Muhammad Umer Farooq (CTGA-021), Fizza Aman (CTGA-018)
**Status:** Phase 1 design — source of truth for `data/knowledge_base.json`
**Development cycle stage:** Conceptualization + Formalization (lecture: *Expert Systems — Fundamentals*)

---

## 1. Knowledge acquisition approach

Knowledge was acquired from published WHO and CDC fact sheets (in place of interviewing a physician), following the four steps of the Knowledge Acquisition System from the lecture:

| Step | What we did |
|---|---|
| Knowledge elicitation | Extracted symptoms, warning signs, treatments and prevention from WHO/CDC fact sheets (Section 12) |
| Knowledge structuring | Organised symptom combinations into IF–THEN rules with an intermediate "signs" layer |
| Knowledge representation | Stored everything in `data/knowledge_base.json`; the engine contains no medical knowledge |
| Knowledge refinement | `kb_verify.py` checks consistency at startup; failed test cases feed back into rule/CF changes |

**Knowledge types (lecture split):**
- **Factual knowledge:** disease descriptions, severity levels, symptom definitions, treatments, prevention, red-flag warning signs.
- **Heuristic knowledge:** diagnostic rules and their certainty factors (CFs) — rule-of-thumb judgments, like the lecture's "If fever persists for 3+ days, test for infection."

---

## 2. Diseases (6) — factual

| ID | Disease | Severity | Description | Source |
|---|---|---|---|---|
| `pneumonia` | Pneumonia | **severe** | Acute infection of the lungs (bacterial, viral or fungal). Cough, shortness of breath, fever, chest pain. | WHO |
| `dengue` | Dengue | **severe** | Viral infection spread by *Aedes* mosquitoes. High fever with pain behind the eyes, aches, nausea, rash; lasts 2–7 days. Severe dengue is a medical emergency. | WHO, CDC |
| `malaria` | Malaria | **severe** | Parasitic disease (*Plasmodium*) spread by infected *Anopheles* mosquitoes. Fever, headache, chills. Always requires treatment with medicine. | WHO |
| `typhoid` | Typhoid | **moderate** | Bacterial infection (*Salmonella* Typhi) spread through contaminated food and water. Prolonged high fever, abdominal pain, constipation or diarrhoea. | WHO |
| `influenza` | Influenza | **moderate** | Acute viral respiratory infection. Sudden fever, dry cough, headache, muscle and joint pain, malaise. | WHO |
| `common_cold` | Common Cold | **mild** | Viral infection of the nose and throat. Sneezing, runny nose, sore throat; most people have no fever; resolves on its own. | CDC |

**Severity rule used:** severe = can become life-threatening and needs urgent medical care; moderate = serious but treatable with standard care, complications mainly if untreated; mild = self-limiting.

---

## 3. Symptoms (20) — factual

Input type: **intensity** = user picks mild / moderate / severe; **yes/no** = binary.

| ID | Label | Input | Synonyms (incl. Roman Urdu) |
|---|---|---|---|
| `fever` | Fever | intensity | temperature, high temperature, feverish, bukhar |
| `fever_more_than_3_days` | Fever lasting more than 3 days | yes/no (asked only if fever entered) | prolonged fever, fever for days |
| `chills` | Chills | intensity | shivering, rigors, kapkapi |
| `sweating` | Sweating | intensity | night sweats, paseena |
| `headache` | Headache | intensity | head pain, sir dard |
| `body_aches` | Body / muscle / joint pain | intensity | muscle pain, joint pain, body pain, badan dard |
| `fatigue` | Fatigue | intensity | tiredness, weakness, malaise, kamzori |
| `cough` | Cough | intensity | dry cough, khansi |
| `sore_throat` | Sore throat | intensity | throat pain, gala kharab |
| `runny_nose` | Runny nose | intensity | nasal discharge, blocked nose, zukam |
| `sneezing` | Sneezing | intensity | sneeze, cheenk |
| `rash` | Skin rash | yes/no | red spots, skin spots |
| `pain_behind_eyes` | Pain behind the eyes | intensity | eye pain, retro-orbital pain |
| `bleeding_gums` | Bleeding gums or nose | yes/no | gum bleeding, nose bleed |
| `nausea_vomiting` | Nausea or vomiting | intensity | nausea, vomiting, ulti |
| `abdominal_pain` | Abdominal pain | intensity | stomach pain, belly pain, pait dard |
| `diarrhea_or_constipation` | Diarrhoea or constipation | intensity | loose motions, diarrhea, constipation |
| `shortness_of_breath` | Shortness of breath | intensity | breathlessness, difficulty breathing, saans phoolna |
| `chest_pain` | Chest pain | intensity | chest tightness, seene mein dard |
| `confusion` | Confusion | yes/no | disorientation, drowsiness, altered consciousness |

---

## 4. Certainty factor (CF) conventions — MYCIN model

| Item | Value |
|---|---|
| User symptom intensity → CF | mild **0.4**, moderate **0.7**, severe **1.0**; yes/no "yes" = **1.0** |
| Rule fires only if | min(premise CFs) **≥ 0.2** (MYCIN's firing threshold) |
| CF of a fired rule's conclusion | `rule_CF × min(premise CFs)` |
| Two rules supporting the same fact | `CF_new = CF_old + CF_rule × (1 − CF_old)` |
| Disease shown to user if | CF **≥ 0.30** |
| Relative % (teacher's 70/30 format) | each shown disease's CF ÷ sum of shown CFs × 100 |
| Ranking | severity first (severe > moderate > mild), then CF |

---

## 5. Intermediate facts (enable chaining) — 7

| ID | Meaning |
|---|---|
| `pneumonia_signs` | Evidence pattern consistent with pneumonia |
| `dengue_signs` | Evidence pattern consistent with dengue |
| `malaria_signs` | Evidence pattern consistent with malaria |
| `typhoid_signs` | Evidence pattern consistent with typhoid |
| `prolonged_fever` | Fever persisting more than 3 days |
| `flu_signs` | Evidence pattern consistent with influenza |
| `cold_signs` | Evidence pattern consistent with the common cold |

**Chaining structure (uniform for every disease):**
Layer 1: symptoms → `<disease>_signs` → Layer 2: `fever` ∧ `<disease>_signs` → disease
(Common Cold has no fever gate because most colds are afebrile. Typhoid uses `prolonged_fever` as its gate, which is itself inferred — 3 levels of chaining.)

---

## 6. Diagnostic rules (19) — heuristic

Priority (conflict resolution / salience): red flags **100**, severe-disease chain **30**, moderate **20**, mild **10**. Intermediate rules inherit the priority of the disease they feed.

| Rule | IF | THEN | CF | Priority | Rationale (source) |
|---|---|---|---|---|---|
| R1 | `cough` ∧ `shortness_of_breath` | `pneumonia_signs` | 0.80 | 30 | Lower respiratory pattern (WHO) |
| R2 | `chest_pain` | `pneumonia_signs` | 0.50 | 30 | Chest pain listed for pneumonia (WHO) |
| R3 | `fever` ∧ `pneumonia_signs` | **Pneumonia** | 0.85 | 30 | Fever + lower respiratory signs (WHO) |
| R4 | `rash` ∧ `pain_behind_eyes` | `dengue_signs` | 0.85 | 30 | Most specific dengue pair (WHO, CDC) |
| R5 | `body_aches` ∧ `nausea_vomiting` | `dengue_signs` | 0.60 | 30 | Dengue: aches + nausea/vomiting (WHO, CDC) |
| R6 | `bleeding_gums` | `dengue_signs` | 0.70 | 30 | Dengue warning sign (WHO, CDC) |
| R7 | `fever` ∧ `dengue_signs` | **Dengue** | 0.90 | 30 | WHO: high fever + ≥2 dengue symptoms |
| R8 | `chills` ∧ `sweating` | `malaria_signs` | 0.85 | 30 | Classic malaria paroxysm (WHO) |
| R9 | `headache` ∧ `nausea_vomiting` | `malaria_signs` | 0.60 | 30 | Early malaria symptoms (WHO) |
| R10 | `fever` ∧ `malaria_signs` | **Malaria** | 0.90 | 30 | Fever + malaria signs (WHO) |
| R11 | `fever` ∧ `fever_more_than_3_days` | `prolonged_fever` | 0.90 | 20 | Lecture heuristic: fever 3+ days → test for infection |
| R12 | `abdominal_pain` ∧ `diarrhea_or_constipation` | `typhoid_signs` | 0.75 | 20 | Typhoid GI pattern (WHO) |
| R13 | `prolonged_fever` ∧ `typhoid_signs` | **Typhoid** | 0.85 | 20 | WHO: prolonged high fever + GI symptoms |
| R14 | `cough` ∧ `body_aches` | `flu_signs` | 0.70 | 20 | Dry cough + muscle pain (WHO) |
| R15 | `headache` ∧ `fatigue` | `flu_signs` | 0.50 | 20 | Headache + severe malaise (WHO) |
| R16 | `fever` ∧ `flu_signs` | **Influenza** | 0.85 | 20 | Sudden fever + flu signs (WHO); cf. CDC ILI definition |
| R17 | `runny_nose` ∧ `sneezing` | `cold_signs` | 0.80 | 10 | Typical cold pattern (CDC) |
| R18 | `sore_throat` | `cold_signs` | 0.50 | 10 | Sore throat (CDC) |
| R19 | `cold_signs` | **Common Cold** | 0.80 | 10 | Most colds have no fever (CDC) |

---

## 7. Red-flag rules (3) — factual (WHO/CDC warning signs)

Fired with priority 100, before any diagnosis. Output an alert; they do not add a disease.

| Rule | IF | Alert message | Source |
|---|---|---|---|
| RF1 | `bleeding_gums` | "Bleeding gums or nose can be a warning sign of severe dengue. Seek emergency medical care now." | WHO, CDC |
| RF2 | `chest_pain` ∧ `shortness_of_breath` | "Chest pain with shortness of breath needs urgent assessment. Seek emergency medical care now." | WHO (pneumonia) |
| RF3 | `confusion` | "Confusion or reduced consciousness can signal a severe infection such as severe malaria. Seek emergency medical care now." | WHO (malaria, pneumonia) |

**Totals:** 6 diseases · 20 symptoms · 7 intermediate facts · 22 rules (19 diagnostic + 3 red-flag)

---

## 8. Treatment and prevention — factual

| Disease | Treatment / recommendation | Prevention | Source |
|---|---|---|---|
| Pneumonia | See a doctor promptly. Antibiotics if bacterial (WHO preferred: amoxicillin), prescribed by a doctor; hospital care for severe cases; rest and plenty of fluids. | Vaccination (pneumococcal, Hib, measles, influenza, whooping cough); frequent handwashing; reduce indoor air pollution; stop smoking; healthy diet. | WHO |
| Dengue | No specific medicine. Rest; drink plenty of fluids/electrolytes; paracetamol for fever and pain; **do not take aspirin or ibuprofen** (bleeding risk); see a doctor and watch for warning signs. | Repellents (DEET, IR3535, icaridin); long sleeves and trousers; window screens and mosquito nets; cover water containers, drain standing water, discard tyres/containers. | CDC, WHO |
| Malaria | Confirm with a blood test (microscopy or rapid diagnostic test); artemisinin-based combination therapy (ACT) prescribed by a doctor; always requires medicine; severe symptoms need emergency care. | Insecticide-treated bed nets; repellents after dusk; protective clothing and window screens; preventive medicine for travellers; WHO-recommended vaccines (RTS,S, R21) for young children in high-transmission areas. | WHO |
| Typhoid | Blood test to confirm; antibiotics prescribed by a doctor, taken for the full course (antimicrobial resistance is common); wash hands after toilet; do not prepare food for others until cleared. | Safe (boiled/treated) water; adequate sanitation; eat thoroughly cooked, hot food; hand hygiene; typhoid conjugate vaccine. | WHO |
| Influenza | Rest, drink fluids, treat fever; seek care if symptoms worsen; antivirals as soon as possible for high-risk or severe cases (doctor-prescribed). | Annual vaccination; wash hands regularly; cover coughs and sneezes; stay home when unwell; avoid touching eyes, nose and mouth. | WHO |
| Common Cold | Rest and fluids; saline nasal spray, humidifier, lozenges; honey for cough (age 1+); OTC medicines only relieve symptoms. **Antibiotics do not help.** See a doctor if breathing is difficult, fever lasts more than 4 days, or symptoms last more than 10 days. | Wash hands; avoid touching face; avoid close contact with sick people; keep vaccines up to date. | CDC |

**Disclaimer (shown with every result):** "This system is an educational project, not a medical diagnosis. Always consult a qualified doctor."

---

## 9. Constraints `kb_verify.py` must enforce

1. Every symptom used in a rule or red flag exists in the symptom list.
2. Every rule's THEN is either a disease or an intermediate fact defined in the KB.
3. Every intermediate fact is produced by at least one rule and used by at least one rule.
4. Every disease has a severity (mild/moderate/severe), description, treatment, prevention and source.
5. All rule CFs are in (0, 1]; all priorities are integers.
6. **No CF overcounting (AIMA §14.7):** when two or more rules conclude the same fact, the sets of root symptoms reachable from their IF parts must be disjoint.
7. Every disease is reachable by at least one rule.
8. No rule chain forms a cycle.

On success print: `KB verified: 6 diseases, 20 symptoms, 7 intermediate facts, 22 rules`

---

## 10. Design check — prototype results (moderate intensity = 0.7 unless stated)

These were computed with a scratch prototype of the engine to confirm the CF values give sensible behaviour. They are **not** the Phase 4 test cases (those are written from WHO/CDC case descriptions).

| Scenario | Input | Result | Shows |
|---|---|---|---|
| Severe + mild together | fever, rash, pain behind eyes, runny nose, sneezing, sore throat | **Dengue** 0.535 (48.4%) listed **first**, Common Cold 0.571 (51.6%) | Severity outranks confidence |
| Close case | fever, headache, nausea/vomiting, body aches | Dengue 0.378 (50%), Malaria 0.378 (50%) | Triggers backward chaining |
| Close + BC answer "bleeding gums: yes" | as above + bleeding gums | Dengue 0.63 (62.5%), Malaria 0.378 (37.5%) + **RF1 alert** | BC changes ranking |
| Close + BC answer "chills, sweating" | as above + chills, sweating | Malaria 0.63 (62.5%), Dengue 0.378 (37.5%) | BC changes ranking |
| Fever only (moderate or severe) | fever | No disease ≥ 30% | No false diagnosis |
| No symptoms | — | No disease | Edge case |
| Pneumonia | fever, cough, shortness of breath, chest pain | Pneumonia 0.595 + **RF2 alert** | Red flag |
| Malaria | fever, chills, sweating, headache, nausea/vomiting | Malaria 0.63 | Two rules combined |
| Typhoid | fever, fever >3 days (yes), abdominal pain, diarrhoea/constipation, fatigue | Typhoid 0.446 | 3-level chaining |
| Influenza | fever, cough, body aches, headache, fatigue | Influenza 0.568 | |
| Common Cold | runny nose, sneezing, sore throat | Common Cold 0.571 | Afebrile disease |
| All severe | fever, cough, body aches, shortness of breath | Pneumonia 0.68 first, Influenza 0.595 | Overlap ranked by severity |

Overcounting check (constraint 6): **PASS** for all 22 rules.

---

## 11. Assumptions

1. Certainty factors are heuristic values assigned by the knowledge engineers (the group) based on how specific each symptom combination is in WHO/CDC descriptions; they are not clinically validated probabilities.
2. Relative percentages assume the patient has one of the six diseases in the knowledge base.
3. Severity is fixed per disease, not assessed per patient.
4. Only positive (confirming) evidence is modelled; a symptom cannot lower a disease's CF (e.g., high fever does not reduce the likelihood of a cold).
5. `fever_more_than_3_days` is only asked after the user reports fever.
6. Symptoms not in the knowledge base are reported to the user and ignored.

---

## 12. Sources

- WHO — Malaria fact sheet (4 Dec 2025): https://who.int/news-room/fact-sheets/detail/malaria
- WHO — Typhoid fact sheet (30 Mar 2023): https://who.int/news-room/fact-sheets/detail/typhoid
- WHO — Influenza (seasonal) fact sheet (28 Feb 2025): https://who.int/en/news-room/fact-sheets/detail/influenza-(seasonal)
- WHO — Pneumonia health topic: https://www.who.int/health-topics/pneumonia
- WHO Western Pacific — Dengue and severe dengue: https://www.who.int/westernpacific/health-topics/dengue-and-severe-dengue
- CDC — Dengue symptoms: https://www.cdc.gov/dengue/symptoms
- CDC — Dengue treatment: https://www.cdc.gov/dengue/treatment/index.html
- CDC — Common cold fact sheet (2026): https://cdc.gov/common-cold/media/pdfs/2026/03/BAA_Common-Cold_Final-508.pdf
- CDC — FluView quick reference (ILI definition): https://gis.cdc.gov/grasp/fluview/FluViewPhase1QuickReferenceGuide.pdf
- Russell, S. & Norvig, P., *Artificial Intelligence: A Modern Approach*, 2nd ed. — §7.5 (forward chaining), §14.7 (certainty factors, MYCIN)
- Shortliffe, E. H. & Buchanan, B. G. (1975). A model of inexact reasoning in medicine. *Mathematical Biosciences*, 23, 351–379.
