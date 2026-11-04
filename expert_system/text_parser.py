"""Free-text symptom parser: turns a sentence into the engine's input.

Pure standard library and fully deterministic (no language model, no network).
All symptom vocabulary comes from the knowledge base (ids, labels, synonyms);
this file only adds GENERIC word lists for negation, intensity and filler.

Pipeline:  normalise -> split into clauses -> find the longest known phrases ->
           apply negation / intensity cues of the clause -> read durations.

Word order does not matter for the result: cues apply to the whole clause, and
clauses are independent of each other.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from expert_system.cli import normalize, resolve_symptom, split_entries

PROLONGED_AFTER_DAYS = 3   # "more than 3 days" counts as prolonged (see docs/LIMITATIONS.md)

NEGATION_WORDS = {"no", "not", "without", "never", "nahi", "nahin", "nhi", "bina",
                  "don", "doesn", "didn", "t"}
# Intensity cue -> rank among the KB's intensity levels (0 = weakest, 2 = strongest).
INTENSITY_WORDS = {"mild": 0, "slight": 0, "slightly": 0, "little": 0, "light": 0,
                   "halka": 0, "halki": 0, "moderate": 1, "medium": 1,
                   "severe": 2, "high": 2, "very": 2, "bohat": 2, "bahut": 2,
                   "shadeed": 2, "tez": 2, "extreme": 2, "intense": 2, "strong": 2}
FILLER_WORDS = {"i", "m", "me", "my", "have", "has", "had", "am", "is", "are", "was", "were",
                "suffering", "from", "feeling", "feel", "feels", "getting", "with", "a", "an",
                "the", "also", "some", "bit", "since", "for", "and", "of", "in", "on", "to",
                "only", "just", "about", "there", "it", "that", "mujhe", "mera", "meri", "mere",
                "hai", "hain", "ho", "hoon", "raha", "rahi", "rahe", "hota", "hoti", "se",
                "ka", "ki", "ke", "ko", "bhi", "main", "mein", "me", "please", "got",
                "day", "days", "din", "week", "weeks", "hafta", "hafte",
                "im", "ive", "having", "been", "bad", "thora", "thori", "kuch", "rha", "rhi",
                "raha", "tha", "thi", "lag", "lagta", "hoon", "hun", "yeh", "ye", "woh", "us",
                "or", "like", "really", "feelings", "since", "last", "ago"}
SPLIT_WORDS = re.compile(r"\b(?:but|lekin|magar)\b", re.IGNORECASE)
DURATION = re.compile(r"(\d+)\s*(days?|din|dino|weeks?|hafta|hafte|haftay)\b", re.IGNORECASE)


@dataclass
class ParsedInput:
    """Result of parsing one sentence."""
    symptoms: dict[str, str] = field(default_factory=dict)   # id -> level label or "yes"
    negated: list[str] = field(default_factory=list)         # ids the user said they do NOT have
    unknown: list[str] = field(default_factory=list)         # phrases not in the KB
    duration_days: Optional[int] = None
    read_from: dict[str, str] = field(default_factory=dict)  # id -> typed word (fuzzy matches only)
    defaulted: list[str] = field(default_factory=list)       # intensity symptoms given no intensity word


def words(text: str) -> list[str]:
    """Lowercase alphanumeric words of a text."""
    return re.findall(r"[a-z0-9]+", normalize(text))


def build_phrases(kb: dict) -> dict[tuple, str]:
    """Map every known phrase (as a tuple of words) to its symptom id."""
    phrases: dict[tuple, str] = {}
    for sid, symptom in kb["symptoms"].items():
        for name in [sid, symptom["label"]] + symptom.get("synonyms", []):
            tokens = tuple(words(name))
            if tokens:
                phrases.setdefault(tokens, sid)
    return phrases


def intensity_levels(kb: dict) -> list[str]:
    """KB intensity level names, weakest first (the 'yes' entry is not a level)."""
    table = kb["meta"]["cf_conventions"]["intensity_cf"]
    return sorted((k for k in table if k != "yes"), key=table.get)


def find_phrases(tokens: list[str], phrases: dict[tuple, str]) -> tuple[list[str], list[bool]]:
    """Greedy longest-phrase matching on word boundaries.

    Returns (matched symptom ids in order of appearance, used-flag per token).
    """
    used = [False] * len(tokens)
    hits: list[tuple[int, str]] = []
    longest = max((len(p) for p in phrases), default=0)
    for size in range(longest, 0, -1):
        for start in range(len(tokens) - size + 1):
            if any(used[start:start + size]):
                continue
            sid = phrases.get(tuple(tokens[start:start + size]))
            if sid is not None:
                hits.append((start, sid))
                for i in range(start, start + size):
                    used[i] = True
    return [sid for _, sid in sorted(hits)], used


def clauses_of(kb: dict, text: str) -> list[str]:
    """Split a sentence into clauses: commas, 'and'/'aur'/'&'/'+', 'but'/'lekin'/'magar'."""
    clauses = []
    for piece in split_entries(text, kb):
        clauses.extend(part.strip() for part in SPLIT_WORDS.split(piece) if part.strip())
    return clauses


def parse_text(kb: dict, text: str) -> ParsedInput:
    """Parse a sentence into symptoms (with intensity), negated symptoms and unknown phrases."""
    result = ParsedInput()
    phrases = build_phrases(kb)
    levels = intensity_levels(kb)
    default_level = levels[len(levels) // 2]
    present: dict[str, str] = {}
    negated: list[str] = []

    for clause in clauses_of(kb, text):
        tokens = words(clause)
        matched, used = find_phrases(tokens, phrases)
        # Durations such as "5 days" / "2 hafte" are read from the words no phrase used.
        rest_text = " ".join(t for t, u in zip(tokens, used) if not u)
        for amount, unit in DURATION.findall(rest_text):
            days = int(amount) * (7 if unit.lower().startswith(("week", "haft")) else 1)
            result.duration_days = max(result.duration_days or 0, days)
        rest = words(DURATION.sub(" ", rest_text))
        is_negated = any(t in NEGATION_WORDS for t in rest)
        ranks = [INTENSITY_WORDS[t] for t in rest if t in INTENSITY_WORDS]
        level = levels[min(ranks[0], len(levels) - 1)] if ranks else default_level
        leftover = [(i, t) for i, t in enumerate(rest)
                    if t not in NEGATION_WORDS and t not in INTENSITY_WORDS
                    and t not in FILLER_WORDS and not t.isdigit()]

        # Typo fallback: try the fuzzy matcher on adjacent word pairs, then single words.
        unknown_run: list[str] = []
        k = 0
        while k < len(leftover):
            guess, typed, size = None, "", 1
            if k + 1 < len(leftover) and leftover[k + 1][0] == leftover[k][0] + 1:
                typed = leftover[k][1] + " " + leftover[k + 1][1]
                guess = "".join(x for x in resolve_symptom(typed, kb) if x)
                size = 2
            if not guess:
                typed, size = leftover[k][1], 1
                guess = "".join(x for x in resolve_symptom(typed, kb) if x)
            if guess:
                matched.append(guess)
                result.read_from.setdefault(guess, typed)
                if unknown_run:
                    result.unknown.append(" ".join(unknown_run))
                    unknown_run = []
            else:
                unknown_run.append(leftover[k][1])
            k += size
        if unknown_run:
            result.unknown.append(" ".join(unknown_run))

        for sid in matched:
            if is_negated:
                if sid not in negated:
                    negated.append(sid)
            else:
                if sid not in present and kb["symptoms"][sid]["input"] == "intensity" and not ranks:
                    result.defaulted.append(sid)
                present.setdefault(sid, "yes" if kb["symptoms"][sid]["input"] == "yes_no" else level)

    # A follow-up symptom (ask_only_if) implies its parent symptom.
    for sid in list(present):
        parent = kb["symptoms"][sid].get("ask_only_if")
        if parent and parent not in present and parent not in negated:
            present[parent] = default_level
            result.defaulted.append(parent)
    # A duration beyond the limit sets the KB's follow-up symptom, if its parent is present.
    follow_up = next((sid for sid, s in kb["symptoms"].items() if s.get("ask_only_if")), None)
    if follow_up and (result.duration_days or 0) > PROLONGED_AFTER_DAYS:
        if kb["symptoms"][follow_up]["ask_only_if"] in present:
            present[follow_up] = "yes"

    result.symptoms = present
    result.read_from = {sid: word for sid, word in result.read_from.items() if sid in present}
    result.defaulted = [sid for sid in result.defaulted if sid in present]
    result.negated = [sid for sid in negated if sid not in present]
    return result
