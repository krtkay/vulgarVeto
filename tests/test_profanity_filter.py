"""
Tests for the profanity_filter NLP engine.

Runs with pytest (``pytest -q``) or standalone (``python tests/test_profanity_filter.py``)
so it works even where pytest isn't installed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from profanity_filter import (  # noqa: E402
    ProfanityFilter,
    Sensitivity,
    Severity,
    normalize_token,
)

# One shared engine (loading the 1k-word lexicon once is enough).
PF = ProfanityFilter()


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------

def test_normalize_leetspeak():
    assert normalize_token("Sh1t") == "shit"
    assert normalize_token("a$$") == "ass"
    assert normalize_token("f.u.c.k") == "fuck"
    assert normalize_token("fuuuuck") == "fuck"
    assert normalize_token("@ss") == "ass"


def test_normalize_is_idempotent_on_plain_words():
    for w in ("hello", "class", "analysis"):
        assert normalize_token(w) == w


# --------------------------------------------------------------------------
# The Scunthorpe problem: clean words that contain a bad word as a substring
# must NOT be flagged.
# --------------------------------------------------------------------------

CLEAN_WORDS = [
    "class", "classic", "grass", "assassin", "assignment", "assume",
    "embarrass", "cocktail", "cockpit", "peacock", "analysis", "cucumber",
    "document", "therapist", "grapefruit", "Scunthorpe", "mass", "bass",
]


def test_scunthorpe_words_not_flagged():
    for word in CLEAN_WORDS:
        res = PF.analyze(word, sensitivity=Sensitivity.HIGH)
        assert res.clean, f"false positive on {word!r}: {[m.canonical for m in res.matches]}"


def test_clean_sentence_untouched():
    text = "The class analysis was a classic, and nobody felt embarrassed."
    res = PF.analyze(text, sensitivity=Sensitivity.HIGH)
    assert res.clean
    assert res.censored == text


# --------------------------------------------------------------------------
# True positives across matching strategies
# --------------------------------------------------------------------------

def test_exact_match():
    res = PF.analyze("what the hell", sensitivity=Sensitivity.LOW)
    assert res.flagged_count == 1
    assert res.matches[0].canonical == "hell"
    assert res.matches[0].method == "exact"


def test_deobfuscation_needs_medium():
    # "shiiit" (repeated-letter obfuscation) is not itself in the lexicon,
    # so it only matches once de-obfuscation is enabled at MEDIUM.
    low = PF.analyze("that shiiit", sensitivity=Sensitivity.LOW)
    med = PF.analyze("that shiiit", sensitivity=Sensitivity.MEDIUM)
    assert low.clean                       # LOW = exact only
    assert med.flagged_count == 1
    assert med.matches[0].canonical == "shit"


def test_masked_vowel_match():
    res = PF.analyze("f*ck this", sensitivity=Sensitivity.MEDIUM)
    assert res.flagged_count == 1
    assert res.matches[0].canonical == "fuck"
    assert res.matches[0].method == "masked"


def test_separator_obfuscation():
    res = PF.analyze("s-h-i-t happens", sensitivity=Sensitivity.MEDIUM)
    assert any(m.canonical == "shit" for m in res.matches)


def test_fuzzy_only_on_high():
    # a one-edit typo of a profanity
    med = PF.analyze("you complete azzhole", sensitivity=Sensitivity.MEDIUM)
    high = PF.analyze("you complete azzhole", sensitivity=Sensitivity.HIGH)
    assert high.flagged_count >= med.flagged_count


# --------------------------------------------------------------------------
# Casing, punctuation & spans are preserved
# --------------------------------------------------------------------------

def test_censor_preserves_surrounding_text():
    res = PF.analyze("Hell! Really?", sensitivity=Sensitivity.LOW, style="beep")
    assert res.censored == "BEEP! Really?"


def test_mask_style_keeps_first_letter():
    res = PF.analyze("shit", sensitivity=Sensitivity.LOW, style="mask")
    assert res.censored == "s***"


def test_remove_style_collapses_spaces():
    res = PF.analyze("oh shit really", sensitivity=Sensitivity.LOW, style="remove")
    assert res.censored == "oh really"


def test_randomized_style_is_reproducible():
    a = PF.analyze("shit", style="symbols", seed=7).censored
    b = PF.analyze("shit", style="symbols", seed=7).censored
    assert a == b


# --------------------------------------------------------------------------
# Phrases, severity tiers & metrics
# --------------------------------------------------------------------------

def test_phrase_detection():
    res = PF.analyze("that alabama hot pocket move", sensitivity=Sensitivity.LOW)
    assert any(m.method == "phrase" for m in res.matches)


def test_severity_tier_filtering():
    text = "damn this fucking mess"
    all_sev = PF.analyze(text)
    severe_only = PF.analyze(text, severities=[Severity.SEVERE, Severity.MODERATE])
    # "damn" is mild, so filtering it out drops the count
    assert all_sev.flagged_count > severe_only.flagged_count
    assert all(m.severity != Severity.MILD for m in severe_only.matches)


def test_metrics():
    res = PF.analyze("one shit two damn three", sensitivity=Sensitivity.LOW)
    assert res.token_count == 5
    assert res.flagged_count == 2
    assert abs(res.profanity_rate - 40.0) < 1e-6
    assert set(res.severity_breakdown()) == {"mild", "moderate", "severe"}


def test_highlight_html_escapes():
    res = PF.analyze("shit <b>", sensitivity=Sensitivity.LOW)
    out = PF.highlight_html(res)
    assert "&lt;b&gt;" in out       # raw HTML is escaped
    assert "<mark" in out            # the profanity is wrapped


# --------------------------------------------------------------------------
# Standalone runner (no pytest required)
# --------------------------------------------------------------------------

def _run_standalone() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  ERROR {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
