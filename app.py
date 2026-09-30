"""
VulgarVeto - an NLP profanity detector & censor.

A Streamlit front-end over :mod:`profanity_filter`. The primary mode is **text**
(pure-Python NLP, works anywhere), with an optional **audio** mode that
transcribes a WAV, censors the transcript, and can re-synthesize clean speech.

Run locally:  ``streamlit run app.py``
"""

from __future__ import annotations

import random

import streamlit as st

import audio_utils
from profanity_filter import ProfanityFilter, Sensitivity, Severity

# ---------------------------------------------------------------------------
# Page + theme
# ---------------------------------------------------------------------------

st.set_page_config(page_title="VulgarVeto", page_icon="🚫", layout="wide")

st.markdown(
    """
    <style>
      .vv-title { font-size: 3rem; font-weight: 800; text-align:center;
                  background: linear-gradient(90deg,#f2711c,#db2828);
                  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                  margin-bottom:0; }
      .vv-tag   { text-align:center; color:#888; margin-top:0; font-size:1.05rem; }
      .vv-box   { background:rgba(127,127,127,.08); border:1px solid rgba(127,127,127,.2);
                  border-radius:12px; padding:1rem 1.2rem; }
      mark { line-height:1.9; }
      .vv-meter-track { width:100%; height:26px; background:rgba(127,127,127,.18);
                        border-radius:13px; overflow:hidden; }
      .vv-meter-fill  { height:100%; color:#fff; font-weight:700; text-align:center;
                        line-height:26px; border-radius:13px; transition:width .4s; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def get_filter() -> ProfanityFilter:
    """Load the lexicon once per server process."""
    return ProfanityFilter()


PF = get_filter()

SENSITIVITY_HELP = {
    "Low - exact words only": Sensitivity.LOW,
    "Medium - + leetspeak & masking": Sensitivity.MEDIUM,
    "High - + fuzzy / typos": Sensitivity.HIGH,
}
SEVERITY_COLORS = {"mild": "#f4b942", "moderate": "#f2711c", "severe": "#db2828"}
CENSOR_STYLES = ["Beep", "Mask", "Symbols", "Dolphin", "Random", "Remove"]

SAMPLE_TEXT = (
    "Honestly, this class analysis was a classic. But then some dumb@ss "
    "started yelling 'what the hell is this sh1t' and f*cking lost it. "
    "Cassandra from Scunthorpe stayed cool though."
)

FUN_FACTS = [
    "Whole-word matching fixes the 'Scunthorpe problem' - clean words that merely contain a rude substring.",
    "Studies suggest swearing can measurably increase pain tolerance.",
    "Leetspeak ('sh1t', 'a$$') is normalized back to letters before matching.",
    "The censorship 'beep' dates to 1950s radio and TV broadcasting.",
    "This app is fully offline for text - no ML model, no GPU, no API key.",
]


# ---------------------------------------------------------------------------
# Sidebar controls (shared by text & audio)
# ---------------------------------------------------------------------------

def sidebar_config():
    st.sidebar.header("⚙️ Controls")

    style = st.sidebar.selectbox("Censor style", CENSOR_STYLES, index=0)

    sens_label = st.sidebar.radio(
        "Detection sensitivity",
        list(SENSITIVITY_HELP.keys()),
        index=1,
        help="Higher = catches more obfuscation, but slightly more false positives.",
    )
    sensitivity = SENSITIVITY_HELP[sens_label]

    st.sidebar.markdown("**Censor which severities?**")
    sev = []
    if st.sidebar.checkbox("Mild", value=True):
        sev.append(Severity.MILD)
    if st.sidebar.checkbox("Moderate", value=True):
        sev.append(Severity.MODERATE)
    if st.sidebar.checkbox("Severe", value=True):
        sev.append(Severity.SEVERE)

    st.sidebar.divider()
    st.sidebar.markdown("### 🎓 Did you know?")
    st.sidebar.info(random.choice(FUN_FACTS))

    return {"style": style, "sensitivity": sensitivity, "severities": sev}


# ---------------------------------------------------------------------------
# Shared result renderer
# ---------------------------------------------------------------------------

def render_analysis(result, style: str):
    if result.token_count == 0:
        st.info("Nothing to analyze yet.")
        return

    # -- metrics ---------------------------------------------------------
    breakdown = result.severity_breakdown()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tokens", result.token_count)
    c2.metric("Flagged", result.flagged_count)
    c3.metric("Profanity rate", f"{result.profanity_rate:.1f}%")
    c4.metric("Unique words", len(result.unique_words))

    # -- profanity meter -------------------------------------------------
    rate = result.profanity_rate
    fill = "#21ba45" if rate < 10 else "#f2711c" if rate < 30 else "#db2828"
    st.markdown(
        f"""
        <div class="vv-meter-track">
          <div class="vv-meter-fill" style="width:{max(min(rate,100),8):.0f}%;background:{fill};">
            {rate:.1f}%
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if result.clean:
        st.success("Clean! No profanity detected. 👏")
        return
    if rate > 30:
        st.warning("Whoa there, sailor - that's some colorful language! 🚢")
    elif rate > 10:
        st.info("A little soap for that mouth wouldn't hurt. 🧼")

    st.write("")

    # -- original (highlighted) vs censored ------------------------------
    left, right = st.columns(2)
    with left:
        st.markdown("#### Original (flagged)")
        st.markdown(
            f'<div class="vv-box">{PF.highlight_html(result)}</div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("#### Censored")
        st.markdown(f'<div class="vv-box">{result.censored}</div>', unsafe_allow_html=True)
        st.download_button(
            "⬇️ Download censored text",
            result.censored,
            file_name="censored.txt",
            mime="text/plain",
            use_container_width=True,
        )

    # -- severity chips --------------------------------------------------
    chips = "".join(
        f'<span style="background:{SEVERE_COLOR(sev)};color:#fff;border-radius:12px;'
        f'padding:2px 10px;margin:2px;display:inline-block;">{sev}: {n}</span>'
        for sev, n in breakdown.items() if n
    )
    st.markdown(f"**Severity mix:** {chips or '—'}", unsafe_allow_html=True)

    # -- explainable detection table ------------------------------------
    with st.expander(f"🔎 Why these {result.flagged_count} were flagged", expanded=True):
        rows = [
            {
                "As written": m.original,
                "Matched entry": m.canonical,
                "Severity": m.severity.label,
                "How": m.method,
            }
            for m in result.matches
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(
            "How: exact = literal word · normalized = leetspeak/spacing undone · "
            "masked = blanked vowel (f*ck) · fuzzy = close typo · phrase = multi-word."
        )


def SEVERE_COLOR(sev: str) -> str:
    return SEVERITY_COLORS.get(sev, "#888")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

def text_tab(cfg):
    st.markdown("#### Paste or type some text")
    text = st.text_area("Input text", value=SAMPLE_TEXT, height=160, label_visibility="collapsed")
    if st.button("🚫 Analyze & Censor", type="primary"):
        if not text.strip():
            st.info("Type something first.")
            return
        result = PF.analyze(
            text,
            sensitivity=cfg["sensitivity"],
            severities=cfg["severities"] or None,
            style=cfg["style"].lower(),
        )
        render_analysis(result, cfg["style"])


def audio_tab(cfg):
    if not audio_utils.speech_to_text_available():
        st.warning("Audio transcription needs `SpeechRecognition` (see requirements.txt).")
        return

    st.markdown("#### Upload a WAV recording")
    st.caption("Uncompressed PCM WAV (mono/stereo). Transcription uses an online service.")
    uploaded = st.file_uploader("WAV file", type=["wav"], label_visibility="collapsed")
    if not uploaded:
        return

    st.audio(uploaded, format="audio/wav")
    make_speech = st.checkbox("Also generate clean speech (text-to-speech)", value=False)
    chunk = st.slider("Transcription chunk size (seconds)", 5, 30, 15, 5)

    if not st.button("🎤 Transcribe & Clean", type="primary"):
        return

    audio_bytes = uploaded.getvalue()
    bar = st.progress(0.0, text="Transcribing…")
    try:
        transcript = audio_utils.transcribe_wav(
            audio_bytes, chunk_seconds=chunk, progress=lambda p: bar.progress(p, text="Transcribing…")
        )
    except RuntimeError as exc:
        bar.empty()
        st.error(str(exc))
        return
    bar.empty()

    if not transcript:
        st.info("No speech was recognized in that file.")
        return

    result = PF.analyze(
        transcript,
        sensitivity=cfg["sensitivity"],
        severities=cfg["severities"] or None,
        style=cfg["style"].lower(),
    )
    render_analysis(result, cfg["style"])

    if make_speech and audio_utils.tts_available():
        with st.spinner("Synthesizing clean audio…"):
            try:
                clean_audio = audio_utils.text_to_speech(result.censored)
                st.markdown("#### 🔊 Clean audio")
                st.caption("Note: this is re-synthesized speech, not the original voice.")
                st.audio(clean_audio, format="audio/mp3")
            except RuntimeError as exc:
                st.error(str(exc))


def about_tab():
    st.markdown(
        """
### What VulgarVeto is
A compact **NLP profanity filter**: it detects offensive words in text (or an
audio transcript) and rewrites them in your chosen censor style.

### The NLP under the hood
- **Span-aware tokenization** - censor in place, keep original casing & punctuation.
- **Whole-word & phrase matching** - fixes the *Scunthorpe problem*: `class`,
  `analysis`, `cocktail`, `assassin` are **not** flagged.
- **De-obfuscation** - leetspeak and symbol masking are normalized before matching
  (`sh1t`→shit, `a$$`→ass, `f.u.c.k`→fuck, `fuuuck`→fuck, `f*ck`→fuck).
- **Multi-strategy matching** - exact → normalized → masked-vowel → fuzzy, chosen
  by the **sensitivity** setting (recall vs. precision).
- **Severity tiers** - mild / moderate / severe, so you choose what to censor.
- **Explainability** - every hit reports *how* it matched.

### Honest limitations
- Audio mode **re-synthesizes** the cleaned transcript with TTS; it does not bleep
  the original recording, so the speaker's voice and timing are not preserved.
- Transcription and TTS call online services and need internet.
- The lexicon (`en.txt`, ~1k entries) drives coverage; severity labels are heuristic.
""",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.markdown('<div class="vv-title">🔊 VulgarVeto 🚫</div>', unsafe_allow_html=True)
    st.markdown('<p class="vv-tag">Keep it clean, keep it mean — bleep that obscene!</p>',
                unsafe_allow_html=True)
    st.write("")

    cfg = sidebar_config()
    t_text, t_audio, t_about = st.tabs(["✍️ Text", "🎤 Audio", "ℹ️ About"])
    with t_text:
        text_tab(cfg)
    with t_audio:
        audio_tab(cfg)
    with t_about:
        about_tab()


if __name__ == "__main__":
    main()
