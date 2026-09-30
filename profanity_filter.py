"""
profanity_filter.py
====================
A dependency-light NLP profanity **detection & censoring** engine.

Why this module exists
----------------------
The original app flagged any word that merely *contained* a bad word as a
substring (the classic "Scunthorpe problem"): it censored ``class``, ``grass``,
``assassin``, ``cocktail`` and ``analysis``.  This engine replaces that with a
small but genuine NLP pipeline:

1. **Normalization** - Unicode folding, accent stripping, case folding.
2. **Tokenization** - span-aware, so we can censor in place while keeping the
   original punctuation, spacing and casing.
3. **De-obfuscation** - leetspeak / symbol masking is undone before matching
   (``sh1t`` -> ``shit``, ``a$$`` -> ``ass``, ``f.u.c.k`` -> ``fuck``,
   ``fuuuck`` -> ``fuck``, ``f*ck`` -> ``fuck``).
4. **Multi-strategy matching** - exact whole-word, normalized whole-word,
   masked-vowel regex, and (optional) conservative fuzzy matching. The active
   strategies are controlled by a ``Sensitivity`` level, so callers trade recall
   for precision explicitly.
5. **Phrase (n-gram) detection** - multi-word entries such as
   ``alabama hot pocket`` are matched as phrases.
6. **Severity tiers** - each hit is labelled mild / moderate / severe so callers
   can choose which tiers to censor.

The engine is pure Python (standard library only) and fully offline, which keeps
Streamlit Community Cloud deployment lightweight.
"""

from __future__ import annotations

import html
import math
import random
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import get_close_matches
from enum import IntEnum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# ---------------------------------------------------------------------------
# Configuration data
# ---------------------------------------------------------------------------

DEFAULT_WORDLIST = Path(__file__).with_name("en.txt")


class Sensitivity(IntEnum):
    """How hard the engine tries to find matches (recall vs. precision)."""

    LOW = 1      # exact whole-word only  (highest precision)
    MEDIUM = 2   # + leetspeak / symbol / masked-vowel de-obfuscation
    HIGH = 3     # + conservative fuzzy matching (highest recall)


class Severity(IntEnum):
    MILD = 1
    MODERATE = 2
    SEVERE = 3

    @property
    def label(self) -> str:
        return {1: "mild", 2: "moderate", 3: "severe"}[int(self)]


# Leetspeak / symbol -> letter substitutions used during normalization.
# Kept conservative on purpose: only unambiguous single-letter stand-ins.
_LEET_MAP = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "8": "b",
        "9": "g",
        "@": "a",
        "$": "s",
        "!": "i",
        "|": "i",
        "+": "t",
        "(": "c",
        "€": "e",
        "£": "l",
    }
)

# Characters people use to blank out (usually a vowel): "f*ck", "sh#t", "b%tch".
_MASK_CHARS = set("*#%")
# Characters that are just decorative separators inside an obfuscated word.
_SEP_RE = re.compile(r"[\s._\-~]+")

# Token = a run of word-ish characters, possibly carrying obfuscation symbols.
# `! | +` double as sentence punctuation, so they're allowed only *inside* a
# token (interior class), never at the edges -- otherwise "Hell!" would swallow
# the "!" and normalize to "helli". Internal apostrophes/hyphens/dots keep
# "y'all", "ass-hat" and "f.u.c.k" whole.
_TOK_EDGE = r"[A-Za-z0-9@$#%*]"
_TOK_MID = r"[A-Za-z0-9@$#%*!|+'\-.]"
_TOKEN_RE = re.compile(rf"{_TOK_EDGE}(?:{_TOK_MID}*{_TOK_EDGE})?")

# Curated severity hints. Anything not listed defaults to MODERATE. Severity is
# inherently subjective; these are pragmatic defaults, easy to tune.
_MILD_WORDS = {
    "damn", "damned", "damnit", "dammit", "darn", "heck", "hell", "crap",
    "crappy", "bloody", "bugger", "sod", "git", "pissed", "piss", "arse",
    "bollocks", "blimey", "bugger", "wanker", "prat", "twit", "tosser",
}
_SEVERE_WORDS = {
    "cunt", "motherfucker", "motherfucking", "nigger", "nigga", "faggot",
    "fag", "rape", "rapist", "raping", "paedophile", "pedophile", "coon",
    "chink", "spic", "kike", "retard", "retarded", "beastiality", "bestiality",
}

# When an obfuscated token (masked vowel or fuzzy) is ambiguous between several
# dictionary words, prefer the more common one. "f*ck" -> "fuck", not "feck".
_COMMON_PRIORITY = [
    "fuck", "shit", "ass", "asshole", "bitch", "cunt", "dick", "cock", "piss",
    "damn", "crap", "bastard", "slut", "whore", "bollocks", "prick", "wanker",
]
_PRIORITY_RANK = {w: i for i, w in enumerate(_COMMON_PRIORITY)}

# Common English words that share a stem with a slur/profanity and must never be
# flagged. Whole-word matching already prevents most substring false positives;
# this set is a second safety net, mainly for the fuzzy strategy.
_SAFE_WORDS = {
    "class", "classic", "classes", "classical", "pass", "passed", "passes",
    "password", "grass", "brass", "glass", "bass", "compass", "assess",
    "assassin", "assign", "assignment", "assist", "assistant", "assume",
    "assumption", "associate", "association", "embarrass", "mass", "massive",
    "massachusetts", "ambassador", "assemble", "assembly", "assert", "asset",
    "assorted", "cassette", "assessment", "assure", "assured", "hello",
    "shell", "shellfish", "cocktail", "cockpit", "peacock", "cockroach",
    "cockburn", "scunthorpe", "penistone", "document", "documentary",
    "circumstance", "circumstances", "accumulate", "cucumber", "analysis",
    "analyse", "analyze", "analog", "analogy", "analytical", "canal", "banal",
    "sextet", "sextant", "sussex", "essex", "middlesex", "dickens",
    "dickinson", "therapist", "therapeutic", "grape", "grapes", "grapefruit",
    "scrape", "drape", "matsushita", "shiitake", "titan", "titanic", "title",
    "button", "cockney", "cumulative", "circumference",
}


# ---------------------------------------------------------------------------
# Core text utilities
# ---------------------------------------------------------------------------

def _fold(text: str) -> str:
    """Lowercase + Unicode-normalize + strip accents (naive -> naive)."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.lower()


def normalize_token(token: str) -> str:
    """
    Reduce an obfuscated token to a plain ``[a-z]`` skeleton for matching.

    Examples
    --------
    >>> normalize_token("Sh1t")
    'shit'
    >>> normalize_token("a$$")
    'ass'
    >>> normalize_token("f.u.c.k")
    'fuck'
    >>> normalize_token("fuuuuck")
    'fuck'
    """
    folded = _fold(token)
    folded = _SEP_RE.sub("", folded)          # drop . _ - spaces between letters
    folded = folded.translate(_LEET_MAP)      # leet digits/symbols -> letters
    folded = re.sub(r"[^a-z]", "", folded)     # drop anything still non-alpha
    folded = re.sub(r"(.)\1{2,}", r"\1", folded)  # collapse 3+ repeats: cooool->col
    return folded


def _mask_pattern(token: str) -> Optional[str]:
    """
    Build an anchored regex for a token that blanks a letter with * # % ?.

    ``f*ck`` -> ``^f[a-z]ck$``  (matches "fuck").  Returns ``None`` when the
    token has no mask characters, so callers can skip the (costlier) scan.
    """
    folded = _fold(token)
    folded = _SEP_RE.sub("", folded)
    if not any(ch in _MASK_CHARS for ch in folded):
        return None
    pieces: List[str] = []
    for ch in folded:
        if ch in _MASK_CHARS:
            pieces.append("[a-z]")
        elif ch in _LEET_MAP:  # translate a leet char in-place
            pieces.append(re.escape(chr(_LEET_MAP[ord(ch)])))
        elif ch.isalpha():
            pieces.append(re.escape(ch))
        else:
            return None  # something we don't understand -> don't guess
    if not pieces:
        return None
    return "^" + "".join(pieces) + "$"


def _more_canonical(candidate: str, current: str) -> bool:
    """True if ``candidate`` is a nicer spelling to show than ``current``."""
    cand_alpha, cur_alpha = candidate.isalpha(), current.isalpha()
    if cand_alpha != cur_alpha:
        return cand_alpha  # prefer plain letters over leetspeak
    if len(candidate) != len(current):
        return len(candidate) < len(current)  # then prefer shorter
    return candidate < current  # stable tie-break


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class Match:
    """A single detected profanity span within the analysed text."""

    start: int
    end: int
    original: str            # exact substring as it appeared in the input
    canonical: str           # the dictionary entry it matched
    method: str              # exact | normalized | masked | fuzzy | phrase
    severity: Severity
    replacement: str = ""    # filled in when censoring

    @property
    def normalized(self) -> str:
        return normalize_token(self.original)


@dataclass
class AnalysisResult:
    """Everything the UI needs to render an analysis."""

    text: str
    matches: List[Match] = field(default_factory=list)
    censored: str = ""
    token_count: int = 0
    style: str = "beep"

    # -- convenience metrics -------------------------------------------------
    @property
    def flagged_count(self) -> int:
        return len(self.matches)

    @property
    def clean(self) -> bool:
        return not self.matches

    @property
    def profanity_rate(self) -> float:
        """Percentage of tokens that were flagged (0-100)."""
        if self.token_count == 0:
            return 0.0
        return 100.0 * self.flagged_count / self.token_count

    @property
    def unique_words(self) -> List[str]:
        seen: List[str] = []
        for m in self.matches:
            if m.canonical not in seen:
                seen.append(m.canonical)
        return seen

    def severity_breakdown(self) -> Dict[str, int]:
        counts = {"mild": 0, "moderate": 0, "severe": 0}
        for m in self.matches:
            counts[m.severity.label] += 1
        return counts


# ---------------------------------------------------------------------------
# Censor styles
# ---------------------------------------------------------------------------

_GRAWLIX = "@#$%&!*"
_RANDOM_POOL = ["BEEP", "*bleep*", "$#@%!", "****", "[censored]", "[redacted]", "!@#$"]


def _censor_word(word: str, style: str, rng: random.Random) -> str:
    """Return the replacement string for a single flagged ``word``."""
    style = style.lower()
    n = len(word)
    if style in ("beep", "classic", "classic beep"):
        return "BEEP"
    if style == "mask":
        # keep the first letter, star out the rest: "shit" -> "s***"
        return word[0] + "*" * (n - 1) if n > 1 else "*"
    if style in ("symbols", "grawlix"):
        return "".join(rng.choice(_GRAWLIX) for _ in range(max(n, 3)))
    if style == "dolphin":
        return "\U0001F42C" * (n // 2 + 1)
    if style == "random":
        return rng.choice(_RANDOM_POOL)
    if style == "remove":
        return ""
    return "BEEP"


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

class ProfanityFilter:
    """
    Load a lexicon once, then analyse / censor many texts.

    Parameters
    ----------
    words:
        Iterable of lexicon entries. If ``None``, ``en.txt`` next to this
        module is loaded.
    """

    def __init__(self, words: Optional[Iterable[str]] = None) -> None:
        if words is None:
            words = load_wordlist()
        single: Set[str] = set()
        phrases: List[str] = []
        for raw in words:
            entry = raw.strip().lower()
            if not entry:
                continue
            if " " in entry:
                phrases.append(entry)
            else:
                single.add(entry)

        self.words: Set[str] = single
        # normalized skeleton -> canonical entry. When several dictionary spellings
        # share a skeleton (e.g. "shit", "sh1t", "5h1t" all -> "shit"), prefer the
        # cleanest one to display: all-alphabetic first, then shortest.
        self.norm_index: Dict[str, str] = {}
        self.by_length: Dict[int, List[str]] = {}
        for w in single:
            norm = normalize_token(w)
            if norm:
                current = self.norm_index.get(norm)
                if current is None or _more_canonical(w, current):
                    self.norm_index[norm] = w
            self.by_length.setdefault(len(w), []).append(w)

        # Pre-compile phrase patterns (\bfoo\W+bar\b), case-insensitive.
        self.phrase_patterns: List[Tuple[str, re.Pattern]] = []
        for phrase in phrases:
            parts = [re.escape(p) for p in phrase.split()]
            pattern = re.compile(r"\b" + r"[\s\-_]+".join(parts) + r"\b", re.IGNORECASE)
            self.phrase_patterns.append((phrase, pattern))

        self._safe_norm = {normalize_token(w) for w in _SAFE_WORDS}

    # -- severity ------------------------------------------------------------
    @staticmethod
    def severity_of(word: str) -> Severity:
        w = word.lower()
        if w in _SEVERE_WORDS:
            return Severity.SEVERE
        if w in _MILD_WORDS:
            return Severity.MILD
        return Severity.MODERATE

    # -- single-token matching ----------------------------------------------
    def match_token(self, token: str, sensitivity: Sensitivity) -> Optional[str]:
        """Return the canonical dictionary word a token matches, else ``None``."""
        low = token.lower()

        # 1. exact whole-word (always on) -----------------------------------
        if low in self.words:
            return low

        if sensitivity < Sensitivity.MEDIUM:
            return None

        norm = normalize_token(token)
        if not norm or norm in self._safe_norm or low in _SAFE_WORDS:
            return None

        # 2. normalized whole-word (leetspeak / separators / repeats) --------
        if norm in self.norm_index:
            return self.norm_index[norm]

        # 3. masked vowel: "f*ck" -> ^f[a-z]ck$ ------------------------------
        pat = _mask_pattern(token)
        if pat:
            compiled = re.compile(pat)
            # the skeleton has exactly one char per source char, so its length
            # equals the count of pattern atoms (letters + "[a-z]" groups).
            skeleton_len = pat.count("[a-z]") + len(re.sub(r"\[a-z\]", "", pat[1:-1]))
            hits = [c for c in self.by_length.get(skeleton_len, []) if compiled.match(c)]
            if hits:
                return self._best_candidate(hits)

        # 4. conservative fuzzy (HIGH only) ----------------------------------
        if sensitivity >= Sensitivity.HIGH and len(norm) >= 5:
            candidates = [
                n for n in self.norm_index
                if abs(len(n) - len(norm)) <= 1 and n not in self._safe_norm
            ]
            close = get_close_matches(norm, candidates, n=1, cutoff=0.86)
            if close:
                return self.norm_index[close[0]]

        return None

    # -- full-text analysis --------------------------------------------------
    def analyze(
        self,
        text: str,
        *,
        sensitivity: Sensitivity = Sensitivity.MEDIUM,
        severities: Optional[Sequence[Severity]] = None,
        style: str = "beep",
        seed: Optional[int] = 1234,
    ) -> AnalysisResult:
        """
        Analyse ``text`` and produce matches + a censored version.

        ``severities`` restricts which tiers get censored (defaults to all).
        ``seed`` makes randomized censor styles reproducible.
        """
        if severities is None:
            active = {Severity.MILD, Severity.MODERATE, Severity.SEVERE}
        else:
            active = set(severities)

        matches: List[Match] = []
        claimed: List[Tuple[int, int]] = []  # spans already covered by a phrase

        # -- phrase pass first (longest, most specific) ----------------------
        for canonical, pattern in self.phrase_patterns:
            for m in pattern.finditer(text):
                sev = self.severity_of(canonical.split()[-1])
                matches.append(
                    Match(m.start(), m.end(), m.group(0), canonical, "phrase", sev)
                )
                claimed.append((m.start(), m.end()))

        # -- token pass ------------------------------------------------------
        token_count = 0
        for tok in _TOKEN_RE.finditer(text):
            token_count += 1
            start, end = tok.start(), tok.end()
            if any(s <= start < e for s, e in claimed):
                continue  # already inside a matched phrase
            canonical = self.match_token(tok.group(0), sensitivity)
            if canonical is None:
                continue
            method = self._classify_method(tok.group(0), canonical)
            sev = self.severity_of(canonical)
            matches.append(Match(start, end, tok.group(0), canonical, method, sev))

        # keep only active severities, order by position
        matches = [m for m in matches if m.severity in active]
        matches.sort(key=lambda m: m.start)

        result = AnalysisResult(
            text=text, matches=matches, token_count=token_count, style=style
        )
        result.censored = self._apply_censor(text, matches, style, seed)
        return result

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _best_candidate(cands: Sequence[str]) -> str:
        """Deterministically pick the most likely intended word from candidates."""
        def key(w: str) -> Tuple[int, int, int, str]:
            return (
                _PRIORITY_RANK.get(w, len(_COMMON_PRIORITY)),  # common words first
                -int(ProfanityFilter.severity_of(w)),           # then more severe
                len(w),                                          # then shorter
                w,                                               # stable tie-break
            )
        return min(cands, key=key)

    def _classify_method(self, token: str, canonical: str) -> str:
        if token.lower() == canonical:
            return "exact"
        if normalize_token(token) == normalize_token(canonical):
            return "normalized"
        if _mask_pattern(token):
            return "masked"
        return "fuzzy"

    def _apply_censor(
        self, text: str, matches: List[Match], style: str, seed: Optional[int]
    ) -> str:
        rng = random.Random(seed)
        out = text
        # replace right-to-left so earlier indices stay valid
        for m in sorted(matches, key=lambda x: x.start, reverse=True):
            replacement = _censor_word(m.original, style, rng)
            m.replacement = replacement
            piece = out[m.start : m.end]
            # preserve a trailing space if we removed the word entirely
            out = out[: m.start] + replacement + out[m.end :]
        # tidy up doubled spaces left by "remove"
        if style.lower() == "remove":
            out = re.sub(r"\s{2,}", " ", out).strip()
        return out

    # -- HTML highlight (for Streamlit) -------------------------------------
    def highlight_html(self, result: AnalysisResult) -> str:
        """Return the original text with flagged spans wrapped in <mark>."""
        colors = {
            Severity.MILD: "#f4b942",
            Severity.MODERATE: "#f2711c",
            Severity.SEVERE: "#db2828",
        }
        pieces: List[str] = []
        cursor = 0
        for m in sorted(result.matches, key=lambda x: x.start):
            if m.start < cursor:
                continue  # skip overlaps
            pieces.append(html.escape(result.text[cursor : m.start]))
            color = colors[m.severity]
            pieces.append(
                f'<mark title="{m.canonical} · {m.severity.label} · {m.method}" '
                f'style="background:{color};color:#fff;border-radius:4px;'
                f'padding:0 4px;">{html.escape(m.original)}</mark>'
            )
            cursor = m.end
        pieces.append(html.escape(result.text[cursor:]))
        return "".join(pieces).replace("\n", "<br>")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_wordlist(path: Path | str = DEFAULT_WORDLIST) -> List[str]:
    """Read a newline-delimited lexicon, ignoring blanks/whitespace."""
    p = Path(path)
    if not p.exists():
        # Minimal fallback so the app still runs if the file is missing.
        return [
            "damn", "hell", "shit", "fuck", "ass", "bastard", "crap",
            "bitch", "dick", "piss",
        ]
    with p.open("r", encoding="utf-8", errors="ignore") as fh:
        return [line.strip() for line in fh if line.strip()]


if __name__ == "__main__":  # tiny manual smoke test
    pf = ProfanityFilter()
    demo = "This is a classy analysis, but that sh1t was f*cking damn awful, you assassin."
    res = pf.analyze(demo, sensitivity=Sensitivity.MEDIUM, style="mask")
    print("Original :", demo)
    print("Censored :", res.censored)
    print("Flagged  :", [(m.original, m.canonical, m.method, m.severity.label) for m in res.matches])
    print(f"Tokens={res.token_count} rate={res.profanity_rate:.1f}%")
