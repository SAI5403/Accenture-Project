"""
ControlPlane.ai
Product dashboard UI + Analytics + Audit Log + Download Decision Passport.
"""

import json
import os
import time
from uuid import uuid4

import google.generativeai as genai
import streamlit as st
from dotenv import load_dotenv

from adaptive_verification import adaptive_verify
from blast_radius import estimate_blast_radius
from cost_checker import check_cost, estimate_cost_usd
from decision_engine import decide
from decision_passport import build_decision_passport
from demo_scenarios import DEMO_SCENARIOS
from human_escalation import create_item, needs_human_review, pending_items, resolve
from performance_checker import check_performance
from responsibility_checker import check_responsibility
from risk_fusion import fuse_risk
from risk_profiles import DEFAULT_PROFILE_NAME, RISK_PROFILES

load_dotenv()

st.set_page_config(
    page_title="ControlPlane.ai",
    page_icon="CP",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main-title {
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 0;
    }
    .subtitle {
        font-size: 18px;
        color: #555;
        margin-top: 0;
        margin-bottom: 24px;
    }
    .decision-box {
        padding: 22px;
        border-radius: 10px;
        border: 1px solid #ddd;
        background: #f7f7fb;
        margin-bottom: 16px;
    }
    .small-muted {
        color: #666;
        font-size: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
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


def get_main_issue(performance_score, responsibility_score, cost_score):
    if responsibility_score >= 60:
        return "Responsibility risk"
    if performance_score >= 70:
        return "Evidence mismatch / hallucination"
    if cost_score >= 60:
        return "High cost"
    return "None"


if "review_queue" not in st.session_state:
    st.session_state.review_queue = []

if "audit_log" not in st.session_state:
    st.session_state.audit_log = []


api_key = get_api_key()

st.markdown('<div class="main-title">CONTROLPLANE.AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Real-Time Control Layer for Enterprise AI</div>',
    unsafe_allow_html=True,
)

top_left, top_right = st.columns([1, 1])

with top_left:
    scenario_name = st.selectbox(
        "Demo Scenario",
        list(DEMO_SCENARIOS.keys()),
    )
    st.caption(
        "Choose a demo scenario, or select Custom to test your own prompt and evidence."
    )

scenario = DEMO_SCENARIOS[scenario_name]

with top_right:
    profile_names = list(RISK_PROFILES.keys())
    default_profile = scenario.get("profile", DEFAULT_PROFILE_NAME)

    selected_profile_name = st.selectbox(
        "Business Context / AI Risk Budget",
        profile_names,
        index=profile_names.index(default_profile),
    )

risk_profile = RISK_PROFILES[selected_profile_name]

st.info(
    f"Business Context: **{risk_profile.name}** | "
    f"Reach: **{risk_profile.reach}** | "
    f"Adaptive Verification Threshold: **{risk_profile.adaptive_threshold}/100**\n\n"
    f"{risk_profile.description}"
)

if not api_key:
    st.warning("Enter Gemini API key in Streamlit Secrets or sidebar.")
    st.stop()

genai.configure(api_key=api_key)

MODEL_NAME = "gemini-3.6-flash"

with st.container(border=True):
    st.subheader("Analyze AI Response")

    prompt = st.text_area(
        "Prompt",
        value=scenario["prompt"],
        height=120,
    )

    evidence = st.text_area(
        "Evidence / Source Text",
        value=scenario["evidence"],
        height=120,
    )

    generate = st.button(
        "Analyze with AI",
        type="primary",
        use_container_width=True,
    )

if generate:
    if not prompt.strip():
        st.error("Enter a prompt first.")
        st.stop()

    model = genai.GenerativeModel(MODEL_NAME)

    with st.spinner("Calling Gemini and running ControlPlane checks..."):
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

    initial_fusion_result = fuse_risk(
        performance_result.score,
        cost_result.score,
        responsibility_score,
    )

    verification_result = adaptive_verify(
        model=model,
        prompt=prompt,
        response_text=response_text,
        evidence=evidence,
        fast_overall_score=initial_fusion_result.overall_score,
        threshold=risk_profile.adaptive_threshold,
        current_performance_score=performance_result.score,
        estimate_cost_fn=estimate_cost_usd,
    )

    if verification_result.escalated_performance_score is not None:
        performance_result.score = verification_result.escalated_performance_score

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
        review_item = create_item(
            item_id=str(uuid4())[:8],
            prompt=prompt,
            response=response_text,
            decision_action=decision_result.action,
            overall_score=fusion_result.overall_score,
            reasons=decision_result.reasons,
        )
        st.session_state.review_queue.append(review_item)

    total_estimated_cost = round(
        cost_result.estimated_cost_usd + verification_result.verifier_cost_usd,
        6,
    )

    st.session_state.audit_log.append(
        {
            "time": time.strftime("%H:%M:%S"),
            "scenario": scenario_name,
            "context": risk_profile.name,
            "overall": fusion_result.overall_score,
            "performance": performance_result.score,
            "cost": cost_result.score,
            "responsibility": responsibility_score,
            "decision": decision_result.action,
            "main_issue": get_main_issue(
                performance_result.score,
                responsibility_score,
                cost_result.score,
            ),
            "verification_path": verification_result.path,
            "estimated_cost": total_estimated_cost,
        }
    )

    decision_labels = {
        "ALLOW": "ALLOW",
        "MONITOR": "ALLOW + MONITOR",
        "VERIFY": "REWRITE / VERIFY",
        "BLOCK": "BLOCK / HUMAN REVIEW",
    }

    decision_label = decision_labels.get(decision_result.action, decision_result.action)

    st.divider()

    with st.container(border=True):
        st.subheader("ControlPlane Decision")
        st.markdown(f"## {decision_label}")

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Overall Risk", f"{fusion_result.overall_score} / 100")
        d2.metric("Verification", verification_result.path)
        d3.metric("Blast Radius", blast_radius_result.rating)
        d4.metric("Business Context", risk_profile.reach)

        st.progress(fusion_result.overall_score / 100)

        if decision_result.escalated:
            st.warning(
                f"Escalated from {decision_result.base_decision} to "
                f"{decision_result.action} because of the selected AI Risk Budget."
            )

        if needs_human_review(decision_result.action):
            st.warning("This response has been added to the Human Review Queue.")

    st.subheader("AI Response")
    st.write(response_text)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Risk Analysis",
            "Adaptive Verification",
            "Human Review",
            "Decision Passport",
            "Analytics",
            "Audit Log",
        ]
    )

    with tab1:
        st.subheader("Risk Breakdown")

        r1, r2, r3 = st.columns(3)
        r1.metric("Performance Risk", f"{performance_result.score} / 100")
        r2.metric("Cost Risk", f"{cost_result.score} / 100")
        r3.metric("Responsibility Risk", f"{responsibility_score} / 100")

        st.markdown("### Overall Risk Fusion")
        for reason in fusion_result.reasons:
            st.write(f"- {reason}")

        st.markdown("### Decision Reasons")
        for reason in decision_result.reasons:
            st.write(f"- {reason}")

        st.markdown("### Performance Check")
        for reason in performance_result.reasons:
            st.write(f"- {reason}")

        if performance_result.unsupported_sentences:
            st.warning("Unsupported sentences detected:")
            for sentence in performance_result.unsupported_sentences:
                st.write(f"- {sentence}")
        elif not performance_result.evidence_used:
            st.info("Paste evidence/source text for a stronger performance check.")
        else:
            st.success("Response is supported by the provided evidence.")

        st.markdown("### Cost Check")
        st.write(f"Estimated response call cost: **${cost_result.estimated_cost_usd:.6f}**")
        st.write(f"Verifier call cost: **${verification_result.verifier_cost_usd:.6f}**")
        st.write(f"Total estimated cost: **${total_estimated_cost:.6f}**")
        st.write(f"Output token ratio: **{cost_result.output_token_ratio}x**")
        for reason in cost_result.reasons:
            st.write(f"- {reason}")

        st.markdown("### Responsibility Check")
        st.write(f"Initial Responsibility Action: **{responsibility_action}**")
        if responsibility_flags:
            st.warning("Issues detected:")
            for flag in responsibility_flags:
                st.write(f"- {flag}")
        else:
            st.success("No major responsibility risks detected.")

        st.markdown("### Blast Radius")
        st.metric("Blast Radius", blast_radius_result.rating)
        for reason in blast_radius_result.reasons:
            st.write(f"- {reason}")

    with tab2:
        st.subheader("Adaptive Verification")
        st.metric("Verification Path", verification_result.path)

        if verification_result.triggered:
            st.warning("Deep verification was triggered.")
            st.write(f"Verifier verdict: **{verification_result.verdict}**")
            st.write(f"Verifier latency: **{verification_result.verifier_latency_ms} ms**")
            st.write(f"Verifier cost: **${verification_result.verifier_cost_usd:.6f}**")

            if verification_result.verifier_notes:
                st.write("Verifier notes:")
                st.write(verification_result.verifier_notes)
        else:
            st.success("Fast path used. Extra verifier call skipped.")

        for reason in verification_result.reasons:
            st.write(f"- {reason}")

    with tab3:
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

    with tab4:
        st.subheader("AI Decision Passport")
        st.json(decision_passport)

        st.download_button(
            label="Download Decision Passport JSON",
            data=json.dumps(decision_passport, indent=2),
            file_name="decision_passport.json",
            mime="application/json",
        )

    with tab5:
        st.subheader("Session Analytics")

        audit_log = st.session_state.audit_log
        total_requests = len(audit_log)

        allowed = sum(1 for item in audit_log if item["decision"] == "ALLOW")
        monitored = sum(1 for item in audit_log if item["decision"] == "MONITOR")
        verified = sum(1 for item in audit_log if item["decision"] == "VERIFY")
        blocked = sum(1 for item in audit_log if item["decision"] == "BLOCK")

        average_risk = (
            round(sum(item["overall"] for item in audit_log) / total_requests, 1)
            if total_requests
            else 0
        )

        total_cost = round(sum(item["estimated_cost"] for item in audit_log), 6)

        verification_rate = (
            round(
                sum(1 for item in audit_log if item["verification_path"] == "DEEP")
                / total_requests
                * 100,
                1,
            )
            if total_requests
            else 0
        )

        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Total Requests", total_requests)
        a2.metric("Allowed", allowed)
        a3.metric("Verified", verified)
        a4.metric("Blocked", blocked)

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Monitored", monitored)
        b2.metric("Average Risk", average_risk)
        b3.metric("Estimated Cost", f"${total_cost:.6f}")
        b4.metric("Deep Verify Rate", f"{verification_rate}%")

        st.caption("Analytics are based on this Streamlit session only.")

    with tab6:
        st.subheader("Audit Log")

        if st.session_state.audit_log:
            st.dataframe(st.session_state.audit_log, use_container_width=True)
        else:
            st.info("No audit records yet.")

    st.divider()
    st.subheader("Raw Signals")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Input tokens", input_tokens if input_tokens is not None else "-")
    c2.metric("Output tokens", output_tokens if output_tokens is not None else "-")
    c3.metric("Total tokens", total_tokens if total_tokens is not None else "-")
    c4.metric("Latency", f"{latency_ms} ms")
