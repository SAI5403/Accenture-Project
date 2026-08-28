# ControlPlane.ai — Phase 1A

Milestone: **Prompt → Gemini API → Response**, plus raw token/latency capture
(no risk scoring yet — that's Phase 1B–1F).

## 1. Get a Gemini API key
Go to [Google AI Studio](https://aistudio.google.com/app/apikey) and create a
free API key. Keep it private — don't paste it into chat, commit it, or share
a screenshot with it visible.

## 2. Set up the project
```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Add your key
Copy `.env.example` to `.env` and fill in your real key:
```bash
cp .env.example .env
# then edit .env and set GEMINI_API_KEY=<your real key>
```
`.env` is where the app reads the key from automatically. If you skip this,
the app will ask for a key in the sidebar instead (session-only, not saved).

**Add `.env` to your `.gitignore` before you ever `git init` / push this repo.**

## 4. Run it
```bash
streamlit run app.py
```
This opens a browser tab at `http://localhost:8501`.

## 5. Try it
Enter a prompt (e.g. "What is our refund policy?") and click **Generate
Response**. You should see:
- The AI response text
- Input/output/total token counts and latency — this is the raw data Phase
  1D (Cost Risk) will turn into a score

## What's next (Phase 1B–1F)
This app intentionally does *nothing* with risk yet. Once this is working
end-to-end, the next milestones are, in order:
1. **1B — Responsibility checker**: PII / unsafe-content detection on the response
2. **1C — Performance checker**: does the response hold up against retrieved evidence
3. **1D — Cost checker**: turn the token/latency numbers already being captured into a Cost Risk score
4. **1E — Risk Fusion**: combine the three scores into one overall risk (0–100)
5. **1F — Decision Engine**: map the overall score to Allow / Monitor / Verify / Block

Each of those should be its own file (`performance_checker.py`,
`responsibility_checker.py`, `cost_checker.py`, `risk_fusion.py`,
`decision_engine.py`) sitting next to `app.py`, called in sequence after the
Gemini response comes back — nothing here needs to change for that, this file
already returns everything they'll need (response text + token counts).
