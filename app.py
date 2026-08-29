"""
ControlPlane.ai - Phase 2D
Human Review Queue added for VERIFY/BLOCK decisions.
"""

import os
import time
from uuid import uuid4

import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv

from responsibility_checker import check_responsibility
from performance_checker import check_performance
from cost_checker import check_cost
from risk_fusion import fuse_risk
from decision_engine import decide
from risk_profiles import RISK_PROFILES, DEFAULT_PROFILE_NAME
from blast_radius import estimate_blast_radius
from decision_passport import build_decision_passport
from human_escalation import create_item, needs_human_review, pending_items, resolve

load_dotenv()

st.set_page_config(
    page_title="ControlPlane.ai",
    page_icon="CP",
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


def queue_item_exists(queue, item_id):
    return any(item.id == item_id for item in queue)


if "review_queue" not in st.session_state:
    st.session_state.review_queue = []


api_key = get_api_key()

st.title("ControlPlane.ai")
st.caption("Phase 2D: Human Review Queue")

selected_profile_name = st.selectbox(
    "AI Risk Budget",
    list(RISK_PROFILES.keys()),
    index=list(RISK_PROFILES.keys()).index(DEFAULT_PROFILE_NAME),
)

risk_profile = RISK_PROFILES[selected_profile_name]

st.info(
    f"**{risk_profile.name}**: {risk_profile.description}\n\n"
    f"Reach: {risk_profile.reach_label}\n\n"
    f"Severity: {risk_profile.severity_baseline}"
)

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

    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", None) if usage else 0
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else 0
    total_tokens = getattr(usage, "total_token_count", None) if usage else 0

    responsibility_result = check_responsibility(response_text)
    performance_result = check_performance(response_text, evidence)
    cost_result = check_cost(input_tokens, output_tokens, latency_ms)

    responsibility_score = responsibility_result.get("score", 0)
    responsibility_flags = responsibility_result.get("flags", [])
    responsibility_action = responsibility_result.get("action", "Allow")

    fusion_result = fuse_risk(
        performance_result.score,
        cost_result.score,
        responsibility_score,
    )

    decision_result = decide(
        fusion_result.overall_score,
        performance_result.score,
        cost_result.score,
        responsibility_score,
        thresholds=risk_profile.decision_thresholds,
        overrides=risk_profile.overrides,
    )

    blast_radius_result = estimate_blast_radius(
        decision_result.action,
        fusion_result.overall_score,
        risk_profile.reach,
        risk_profile.reach_label,
        risk_profile.severity_baseline,
    )

    decision_passport = build_decision_passport(
        prompt=prompt,
        response_text=response_text,
        evidence=evidence,
        risk_profile=risk_profile,
        performance_result=performance_result,
        cost_result=cost_result,
        responsibility_score=responsibility_score,
        responsibility_flags=responsibility_flags,
        fusion_result=fusion_result,
        decision_result=decision_result,
        blast_radius_result=blast_radius_result,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
    )

    if needs_human_review(decision_result.action):
        item_id = str(uuid4())[:8]

        review_item = create_item(
            item_id=item_id,
            prompt=prompt,
            response=response_text,
            decision_action=decision_result.action,
            overall_score=fusion_result.overall_score,
            reasons=decision_result.reasons,
        )

        st.session_state.review_queue.append(review_item)

    st.divider()
    st.subheader("AI Response")
    st.write(response_text)

    st.divider()
    st.subheader("ControlPlane Decision")

    decision_labels = {
        "ALLOW": "ALLOW",
        "MONITOR": "ALLOW + MONITOR",
        "VERIFY": "REWRITE / VERIFY",
        "BLOCK": "BLOCK / HUMAN REVIEW",
    }

    decision_label = decision_labels.get(decision_result.action, decision_result.action)

    st.markdown(f"## Decision: {decision_label}")

    if needs_human_review(decision_result.action):
        st.warning("This response has been added to the Human Review Queue.")

    if decision_result.escalated:
        st.warning(
            f"Escalated from {decision_result.base_decision} to "
            f"{decision_result.action} because of the selected AI Risk Budget."
        )

    for reason in decision_result.reasons:
        st.write(f"- {reason}")

    st.divider()
    st.subheader("Human Review Queue")

    queue = st.session_state.review_queue
    pending = pending_items(queue)

    st.metric("Pending Review Items", len(pending))

    if pending:
        for item in pending:
            with st.expander(
                f"Review {item.id} - {item.decision} - Risk {item.overall_score}/100",
                expanded=True,
            ):
                st.write("Prompt:")
                st.write(item.prompt)

                st.write("AI Response:")
                st.write(item.response)

                st.write("Reasons:")
                for reason in item.reasons:
                    st.write(f"- {reason}")

                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    if st.button("Approve", key=f"approve_{item.id}"):
                        resolve(queue, item.id, "APPROVED")
                        st.rerun()

                with col_b:
                    if st.button("Override Allow", key=f"override_{item.id}"):
                        resolve(queue, item.id, "OVERRIDE_ALLOW")
                        st.rerun()

                with col_c:
                    if st.button("Confirm Block", key=f"block_{item.id}"):
                        resolve(queue, item.id, "CONFIRMED_BLOCK")
                        st.rerun()
    else:
        st.success("No pending human review items.")

    st.divider()
    st.subheader("Blast Radius")

    st.metric("Blast Radius", blast_radius_result.rating)

    if blast_radius_result.contained:
        st.success("Potential harm is contained before reaching users.")
    else:
        st.warning("Response may reach users, so business impact must be monitored.")

    for reason in blast_radius_result.reasons:
        st.write(f"- {reason}")

    st.divider()
    st.subheader("Overall Risk Fusion")

    overall_score = fusion_result.overall_score

    st.metric("Overall Risk Score", f"{overall_score} / 100")
    st.progress(overall_score / 100)

    for reason in fusion_result.reasons:
        st.write(f"- {reason}")

    st.divider()
    st.subheader("Risk Breakdown")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Performance Risk", f"{performance_result.score} / 100")

    with col2:
        st.metric("Cost Risk", f"{cost_result.score} / 100")

    with col3:
        st.metric("Responsibility Risk", f"{responsibility_score} / 100")

    st.divider()
    st.subheader("Performance Risk Check")

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

    st.divider()
    st.subheader("Cost Risk Check")

    st.write(f"Estimated call cost: **${cost_result.estimated_cost_usd:.6f}**")
    st.write(f"Output token ratio: **{cost_result.output_token_ratio}x**")

    for reason in cost_result.reasons:
        st.write(f"- {reason}")

    st.divider()
    st.subheader("Responsibility Risk Check")

    st.write(f"Initial Responsibility Action: **{responsibility_action}**")

    if responsibility_flags:
        st.warning("Issues detected:")
        for flag in responsibility_flags:
            st.write(f"- {flag}")
    else:
        st.success("No major responsibility risks detected.")

    st.divider()
    st.subheader("Decision Passport")

    st.json(decision_passport)

    st.divider()
    st.subheader("Raw Signals")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Input tokens", input_tokens if input_tokens is not None else "-")
    c2.metric("Output tokens", output_tokens if output_tokens is not None else "-")
    c3.metric("Total tokens", total_tokens if total_tokens is not None else "-")
    c4.metric("Latency", f"{latency_ms} ms")
