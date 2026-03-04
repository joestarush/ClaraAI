"""
app.py — Clara Answers Pipeline UI
Run: streamlit run app.py
"""

import json
import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

st.set_page_config(
    page_title="Clara Answers Pipeline",
    page_icon="📞",
    layout="centered",
)

BASE       = Path(__file__).parent
OUTPUTS    = BASE / "outputs" / "accounts"
DEMO_DIR   = BASE / "dataset" / "demo_calls"
ONB_DIR    = BASE / "dataset" / "onboarding_calls"
RUN_LOG    = BASE / "outputs" / "run_log.json"

ACCOUNTS = {
    "ACC-001": "AquaGuard Fire Protection",
    "ACC-002": "ShieldAlarm Systems",
    "ACC-003": "VoltEdge Electrical Services",
    "ACC-004": "CoolFlow HVAC Services",
    "ACC-005": "FireSafe Sprinkler Contractors",
}


def load_env():
    p = BASE / ".env"
    if p.exists():
        from dotenv import load_dotenv
        load_dotenv(p)

def load_json(path):
    if Path(path).exists():
        with open(path) as f:
            return json.load(f)
    return None

def get_path(account_id, version, filename):
    return OUTPUTS / account_id / f"v{version}" / filename

def v1_exists(aid): return get_path(aid, "1", "memo.json").exists()
def v2_exists(aid): return get_path(aid, "2", "memo.json").exists()

def find_transcript(folder, account_id):
    num = account_id.split("-")[1]
    matches = list(Path(folder).glob(f"*{num}*.txt"))
    return matches[0] if matches else None

def api_ok():
    return bool(os.environ.get("GROQ_API_KEY"))

load_env()


st.title("📞 Clara Answers Pipeline")
st.caption("Onboarding transcript → Account memo → Voice agent config")

if not api_ok():
    st.error("❌ GROQ_API_KEY not found — add it to your .env file")

st.divider()


tab1, tab2, tab3, tab4 = st.tabs([
    "▶️ Run Pipeline",
    "📄 View Outputs",
    "🔄 Changelog",
    "📋 Run Log",
])


with tab1:

    account = st.selectbox(
        "Select account",
        options=list(ACCOUNTS.keys()),
        format_func=lambda x: f"{x} — {ACCOUNTS[x]}",
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Stage 1 — Demo")
        st.caption("Generates memo v1 + agent spec v1")

        demo_t = find_transcript(DEMO_DIR, account)
        if demo_t:
            with st.expander("View transcript"):
                st.text(Path(demo_t).read_text())
        else:
            st.warning("Transcript not found")

        if v1_exists(account):
            st.info("v1 already exists — will overwrite")

        if st.button("▶️ Run Demo Pipeline",
                     disabled=not api_ok() or not demo_t,
                     type="primary", key="btn_demo"):
            with st.spinner("Running..."):
                try:
                    from extract_demo import run_demo_pipeline
                    run_demo_pipeline(account_id=account, transcript_path=str(demo_t))
                    st.success("✅ Done!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    with col2:
        st.subheader("Stage 2 — Onboarding")
        st.caption("Generates memo v2 + agent spec v2 + changelog")

        onb_t = find_transcript(ONB_DIR, account)
        if onb_t:
            with st.expander("View transcript"):
                st.text(Path(onb_t).read_text())
        else:
            st.warning("Transcript not found")

        if not v1_exists(account):
            st.warning("Run Stage 1 first")

        if st.button("▶️ Run Onboarding Pipeline",
                     disabled=not api_ok() or not v1_exists(account) or not onb_t,
                     type="primary", key="btn_onb"):
            with st.spinner("Running..."):
                try:
                    from extract_onboarding import run_onboarding_pipeline
                    run_onboarding_pipeline(account_id=account, transcript_path=str(onb_t))
                    st.success("✅ Done!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.divider()

    # Batch run
    st.subheader("🚀 Batch — Run All 5 Accounts")

    if st.button("▶️ Run All Accounts (Demo + Onboarding)",
                 disabled=not api_ok(), type="secondary", key="btn_batch"):
        progress = st.progress(0)
        status   = st.empty()
        total    = len(ACCOUNTS) * 2
        step     = 0

        from extract_demo import run_demo_pipeline
        from extract_onboarding import run_onboarding_pipeline

        for aid, name in ACCOUNTS.items():
            dt = find_transcript(DEMO_DIR, aid)
            ot = find_transcript(ONB_DIR, aid)

            status.info(f"Running demo for {aid} — {name}...")
            try:
                run_demo_pipeline(account_id=aid, transcript_path=str(dt))
            except Exception as e:
                st.error(f"Demo failed for {aid}: {e}")
            step += 1
            progress.progress(step / total)

            status.info(f"Running onboarding for {aid} — {name}...")
            try:
                run_onboarding_pipeline(account_id=aid, transcript_path=str(ot))
            except Exception as e:
                st.error(f"Onboarding failed for {aid}: {e}")
            step += 1
            progress.progress(step / total)

        status.success("✅ All accounts complete!")
        st.rerun()


    st.divider()
    st.subheader("Account Status")
    for aid, name in ACCOUNTS.items():
        c1, c2, c3 = st.columns([2, 1, 1])
        c1.markdown(f"**{aid}** — {name}")
        c2.markdown("✅ v1" if v1_exists(aid) else "⏳ v1")
        c3.markdown("✅ v2" if v2_exists(aid) else "⏳ v2")

with tab2:

    account2 = st.selectbox(
        "Select account",
        options=list(ACCOUNTS.keys()),
        format_func=lambda x: f"{x} — {ACCOUNTS[x]}",
        key="view_account",
    )
    version = st.radio("Version", ["v1", "v2"], horizontal=True)
    vnum    = version[1]

    memo  = load_json(get_path(account2, vnum, "memo.json"))
    agent = load_json(get_path(account2, vnum, "agent_spec.json"))

    if not memo:
        st.warning(f"No {version} outputs found. Run the pipeline first.")
    else:
        st.divider()

        c1, c2, c3 = st.columns(3)
        c1.metric("Company",  memo.get("company_name", "—"))
        c2.metric("Version",  memo.get("version", "—"))
        bh = memo.get("business_hours") or {}
        c3.metric("Timezone", bh.get("timezone") or "—")

        st.markdown(f"**Address:** {memo.get('office_address') or '—'}")
        st.markdown(f"**Services:** {', '.join(memo.get('services_supported', []))}")

        st.divider()

        st.subheader("🚨 Emergency Definition")
        st.info(memo.get("emergency_definition") or "Not defined")

        with st.expander("🕐 Business Hours"):
            for day in ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]:
                val = bh.get(day)
                st.markdown(f"**{day.capitalize()}:** {val or '—'}")

        with st.expander("📞 Emergency Routing Rules"):
            rules = memo.get("emergency_routing_rules", [])
            if rules:
                for r in rules:
                    st.markdown(f"- **{r.get('condition','')}**")
                    st.markdown(f"  → Action: `{r.get('action','')}`")
                    if r.get("phone_number"):
                        st.markdown(f"  → Phone: `{r['phone_number']}`")
                    if r.get("transfer_timeout_rings"):
                        st.markdown(f"  → Timeout: `{r['transfer_timeout_rings']} rings`")
                    if r.get("fallback_action"):
                        st.markdown(f"  → Fallback: `{r['fallback_action']}`")
                    if r.get("fallback_phone_number"):
                        st.markdown(f"  → Fallback number: `{r['fallback_phone_number']}`")
            else:
                st.write("None defined")

        with st.expander("📋 Non-Emergency Routing Rules"):
            rules = memo.get("non_emergency_routing_rules", [])
            if rules:
                for r in rules:
                    st.markdown(f"- **{r.get('condition','')}** → {r.get('action','')} `{r.get('phone_number') or ''}`")
            else:
                st.write("None defined")

        with st.expander("🔀 Call Transfer Rules"):
            rules = memo.get("call_transfer_rules", [])
            if rules:
                for r in rules:
                    st.markdown(f"- **{r.get('scenario','')}**")
                    st.markdown(f"  → Transfer to: `{r.get('primary_transfer_to','')}`  `{r.get('primary_phone_number') or ''}`")
                    if r.get("timeout_rings"):
                        st.markdown(f"  → Timeout: `{r['timeout_rings']} rings`")
                    if r.get("fallback"):
                        st.markdown(f"  → Fallback: `{r['fallback']}`")
            else:
                st.write("None defined")

        with st.expander("⚙️ Integration Constraints"):
            constraints = memo.get("integration_constraints", [])
            if constraints:
                for c in constraints:
                    connected = "✅ Connected" if c.get("connected") else "❌ Not connected"
                    st.markdown(f"- **{c.get('platform') or 'Unknown platform'}** — {connected}")
                    if c.get("notes"):
                        st.markdown(f"  → {c['notes']}")
            else:
                st.write("No integrations")

        with st.expander("🏢 Office Hours Flow Summary"):
            st.write(memo.get("office_hours_flow_summary") or "—")

        with st.expander("🌙 After Hours Flow Summary"):
            st.write(memo.get("after_hours_flow_summary") or "—")

        with st.expander("📝 Notes"):
            notes = memo.get("notes", [])
            if notes:
                for n in notes:
                    st.markdown(f"- {n}")
            else:
                st.write("None")

        unknowns = memo.get("questions_or_unknowns", [])
        if unknowns:
            with st.expander(f"❓ Open Questions / Unknowns ({len(unknowns)})"):
                for q in unknowns:
                    st.warning(q)
        else:
            st.success("✅ No open questions")

        st.divider()

        if agent:
            st.subheader("🎙️ Agent Spec")

            tp = agent.get("transfer_protocol") or {}
            fp = agent.get("fallback_protocol") or {}

            c1, c2 = st.columns(2)
            c1.markdown(f"**Primary number:** {tp.get('primary_number') or '—'}")
            c1.markdown(f"**Timeout:** {tp.get('timeout_rings') or '—'} rings  ({tp.get('timeout_seconds') or '—'} sec)")
            c2.markdown(f"**Fallback number:** {tp.get('fallback_number') or '—'}")
            c2.markdown(f"**Fallback action:** {tp.get('fallback_action') or '—'}")

            st.markdown(f"**Fallback message:** _{fp.get('message_to_caller') or '—'}_")

            with st.expander("🔧 Tool Invocations"):
                tools = agent.get("tool_invocations", [])
                if tools:
                    for t in tools:
                        st.markdown(f"- **{t.get('tool_name','')}** — triggers when: _{t.get('trigger_condition','')}_")
                        st.caption(t.get("note",""))
                else:
                    st.write("None defined")

            with st.expander("📜 System Prompt"):
                st.code(agent.get("system_prompt", ""), language="markdown")

with tab3:

    account3 = st.selectbox(
        "Select account",
        options=list(ACCOUNTS.keys()),
        format_func=lambda x: f"{x} — {ACCOUNTS[x]}",
        key="changelog_account",
    )

    changelog = load_json(get_path(account3, "2", "changelog.json"))

    if not changelog:
        st.warning("No changelog found. Run the onboarding pipeline first.")
    else:
        st.divider()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Changes", changelog.get("total_changes", 0))
        c2.metric("v1 Date", (changelog.get("v1_extracted_at") or "—")[:10])
        c3.metric("v2 Date", (changelog.get("v2_extracted_at") or "—")[:10])

        st.info(changelog.get("summary", ""))
        st.divider()

        changes = changelog.get("changes", [])
        if not changes:
            st.success("No changes detected between v1 and v2.")
        else:
            icons = {
                "updated":          "🟡",
                "added":            "🟢",
                "removed":          "🔴",
                "list_item_added":  "🟢",
                "list_item_removed":"🔴",
                "type_changed":     "🟠",
            }
            for c in changes:
                ctype = c.get("type", "")
                icon  = icons.get(ctype, "⚪")
                with st.container(border=True):
                    st.markdown(f"{icon} **`{c.get('field','')}`** — `{ctype}`")
                    if "old_value" in c:
                        st.markdown(f"**Before:** `{c['old_value']}`")
                    if "new_value" in c:
                        st.markdown(f"**After:** `{c['new_value']}`")


with tab4:

    st.subheader("📋 Pipeline Run Log")
    st.caption("Every pipeline run is logged here as a task tracker entry.")

    log = load_json(RUN_LOG)

    if not log:
        st.warning("No runs logged yet. Run the pipeline first.")
    else:
        # Summary counts
        total   = len(log)
        success = sum(1 for e in log if e.get("status") == "success")
        failed  = total - success

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Runs", total)
        c2.metric("Successful", success)
        c3.metric("Failed", failed)

        st.divider()

        for entry in reversed(log):
            status_icon = "✅" if entry.get("status") == "success" else "❌"
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"{status_icon} **{entry.get('account_id')}** — {entry.get('company_name')}")
                c2.markdown(f"`Stage {entry.get('version')} — {entry.get('stage')}`")
                st.caption(f"🕐 {entry.get('timestamp','')[:19].replace('T',' ')}  |  {entry.get('notes','')}")
                if entry.get("outputs"):
                    with st.expander("Output files"):
                        for o in entry["outputs"]:
                            st.code(o)
