"""
ControlPlane.ai - Phase 1A + 1B + 1C
Prompt -> Gemini API -> Response -> Responsibility Check -> Performance Check
"""

import os
import time

import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
from responsibility_checker import check_responsibility
from performance_checker import check_performance

load_dotenv()

st.set_page_config(
    page_title="ControlPlane.ai - Phase 1C",
    page_icon="🧭",
    layout="centered",
)


def get_api_key():
    try:
        key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        key = None

    if not key:
        key = os.getenv("GEMINI_API_KEY")

    if key:
        return key

    with st.sidebar:
        st.markdown("### API key")
        return st.text_input("GEMINI_API_KEY", type="password")


api_key = get_api_key()

st.title("ControlPlane.ai")
st.caption("Phase 1C: Gemini Response + Responsibility Risk + Performance Risk")

if not api_key:
    st.warning("Enter Gemini API key in Streamlit Secrets or sidebar.")
    st.stop()

genai.configure(api_key=api_key)

MODEL_NAME = "gemini-3.6-flash"

prompt = st.text_area(
    "Prompt",
    placeholder="Example: What is our refund policy?",
    height=120,
)

evidence = st.text_area(
    "Evidence / Source Text",
    placeholder=(
        "Paste source text here. Example: Our refund policy allows returns "
        "within 30 days with a valid receipt."
    ),
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

    response_text = getattr(response, "text", "")

    st.divider()
    st.subheader("AI Response")
    st.write(response_text)

    responsibility_result = check_responsibility(response_text)
    performance_result = check_performance(response_text, evidence)

    risk_score = responsibility_result.get("score", 0)
    risk_flags = responsibility_result.get("flags", [])
    risk_action = responsibility_result.get("action", "Allow")

    st.divider()
    st.subheader("Responsibility Risk Check")
    st.metric("Responsibility Risk Score", f"{risk_score} / 100")
    st.write(f"Recommended Action: **{risk_action}**")

    if risk_flags:
        st.warning("Issues detected:")
        for flag in risk_flags:
            st.write(f"- {flag}")
    else:
        st.success("No major responsibility risks detected.")

    st.divider()
    st.subheader("Performance Risk Check")
    st.metric("Performance Risk Score", f"{performance_result.score} / 100")

    for reason in performance_result.reasons:
        st.write(f"- {reason}")

    if performance_result.unsupported_sentences:
        st.warning("Unsupported sentences detected:")
        for sentence in performance_result.unsupported_sentences:
            st.write(f"- {sentence}")
    elif not performance_result.evidence_used:
        st.info("Paste evidence/source text above for a stronger performance check.")
    else:
        st.success("Response is supported by the provided evidence.")

    usage = getattr(response, "usage_metadata", None)

    input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    total_tokens = getattr(usage, "total_token_count", None) if usage else None

    st.divider()
    st.subheader("Raw Signals")
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Input tokens", input_tokens if input_tokens is not None else "-")
    c2.metric("Output tokens", output_tokens if output_tokens is not None else "-")
    c3.metric("Total tokens", total_tokens if total_tokens is not None else "-")
    c4.metric("Latency", f"{latency_ms} ms")
