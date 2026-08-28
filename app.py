"""
ControlPlane.ai — Phase 1A
Prompt -> Gemini API -> Response

This is deliberately minimal. No risk detectors yet — that's Phase 1B/1C/1D.
Goal for this milestone: prove the end-to-end pipeline works and start
capturing the raw signals (tokens, latency) that later feed the Cost Risk
detector.
"""

import os
import time

import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
from responsibility_checker import check_responsibility

load_dotenv()  # reads GEMINI_API_KEY from a local .env file, if present

st.set_page_config(page_title="ControlPlane.ai — Phase 1A", page_icon="🧭", layout="centered")


# ---------------------------------------------------------------------------
# API key handling
# ---------------------------------------------------------------------------
def get_api_key() -> str | None:
    """Prefer an env var; fall back to a session-only sidebar input.

    Never hardcode a key in this file and never commit a .env file.
    """
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    with st.sidebar:
        st.markdown("### API key")
        st.caption("Not found in environment. Paste one for this session only "
                    "(it is not saved anywhere).")
        return st.text_input("GEMINI_API_KEY", type="password")


api_key = get_api_key()

st.title("ControlPlane.ai")
st.caption("Real-Time Control Layer for AI — Phase 1A: basic pipeline")

if not api_key:
    st.warning("Enter a Gemini API key in the sidebar (or set GEMINI_API_KEY) to continue.")
    st.stop()

genai.configure(api_key=api_key)

MODEL_NAME = "gemini-3.6-flash"  # fast + cheap, good for iterating during dev

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
prompt = st.text_area(
    "Prompt",
    placeholder="e.g. What is our refund policy?",
    height=120,
)

generate = st.button("Generate Response", type="primary", use_container_width=True)

if generate:
    if not prompt.strip():
        st.error("Enter a prompt first.")
        st.stop()

    model = genai.GenerativeModel(MODEL_NAME)

    with st.spinner("Calling Gemini..."):
        start = time.time()
        try:
            response = model.generate_content(prompt)
        except Exception as e:
            st.error(f"API call failed: {e}")
            st.stop()
        latency_ms = round((time.time() - start) * 1000)

    st.divider()
    st.subheader("AI Response")
    st.write(response.text)

    responsibility_result = check_responsibility(response.text)

st.divider()
st.subheader("Responsibility Risk Check")

st.metric("Responsibility Risk Score", f"{responsibility_result['score']} / 100")

if responsibility_result["flags"]:
    st.warning("Issues detected:")
    for flag in responsibility_result["flags"]:
        st.write(f"- {flag}")
else:
    st.success("No major responsibility risks detected.")

    # --- Raw signals captured now, used by Phase 1D (Cost Risk) later -----
    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    total_tokens = getattr(usage, "total_token_count", None) if usage else None

    st.divider()
    st.subheader("Raw signals (for later Cost Risk detector)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Input tokens", input_tokens if input_tokens is not None else "—")
    c2.metric("Output tokens", output_tokens if output_tokens is not None else "—")
    c3.metric("Total tokens", total_tokens if total_tokens is not None else "—")
    c4.metric("Latency", f"{latency_ms} ms")

    st.caption(
        "No risk scoring yet — this milestone only proves Prompt → Gemini → Response "
        "and starts logging the token/latency data Phase 1D will turn into a Cost Risk score."
    )
