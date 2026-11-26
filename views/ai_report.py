from __future__ import annotations

import streamlit as st

from core import metrics as m
from core import settings
from core.ai import PROVIDER_LABELS, AIError, generate_report
from core.data import AI_REPORT_FILE, save_ai_report
from core.n8n import N8nError, trigger_workflow
from ui import components as ui

SECTION = "AI report"
TITLE = "AI weekly report"
SUBTITLE = "Written by an LLM from the KPIs. The model explains the numbers; it never calculates them."


def _as_markdown(r: dict) -> str:
    def bullets(items):
        return "\n".join(f"- {t}" for t in items)
    return (f"# Weekly sales report ({r['week_start']} to {r['week_end']})\n\n{r['summary']}\n\n"
            f"## Highlights\n{bullets(r['highlights'])}\n\n## Risks\n{bullets(r['risks'])}\n\n"
            f"## Recommended actions\n{bullets(r['actions'])}\n")


def render(ctx) -> None:
    report = ctx.ai_report
    with st.container(key="sec_ai_report"):
        if report is None:
            ui.empty_state("No AI report yet", "Run the n8n workflow below, or generate one with your API key.")
        else:
            if (report["week_start"], report["week_end"]) != (str(ctx.start), str(ctx.end)):
                st.info(f"This report covers {report['week_start']} to {report['week_end']}. "
                        "Your filters show a different period.", icon=":material/info:")
            ui.ai_report_card(report)
            st.download_button("Download as Markdown", _as_markdown(report).encode(),
                               file_name=f"ai_report_{report['week_end']}.md", mime="text/markdown",
                               icon=":material/description:")

    c1, c2 = st.columns(2)

    # Option 1: run the n8n workflow (emails, Slack and saves to the sheet)
    with c1:
        with st.container(key="card_n8n"):
            ui.section_title("Run the n8n workflow now",
                             "Same as the Monday run: builds the report, emails it, posts to Slack and saves it to the sheet.")
            url = settings.n8n_webhook_url()
            if not url:
                st.caption("Add N8N_WEBHOOK_URL to .streamlit/secrets.toml to enable this.")
            if st.button("Run workflow", type="primary", icon=":material/play_arrow:", disabled=not url, key="run_n8n"):
                try:
                    with st.spinner("Starting the n8n workflow…"):
                        trigger_workflow(url, {"source": "dashboard", "start": ctx.start, "end": ctx.end,
                                               "channels": ctx.channels})
                except N8nError as e:
                    st.error(f"Workflow not started. {e}")
                else:
                    st.success("Workflow started. The new report appears here in about a minute; press Refresh to load it.",
                               icon=":material/check_circle:")

    # Option 2: ask the AI directly for the selected period (OpenAI or Claude, local mode)
    with c2:
        with st.container(key="card_generate"):
            ui.section_title("Quick report for the selected period",
                             f"{ctx.period_label}. Calls the AI directly and saves the result here.")
            ai = settings.ai_provider()
            if not ai:
                st.caption("Add OPENAI_API_KEY (or ANTHROPIC_API_KEY) to .streamlit/secrets.toml to enable this.")
            else:
                st.caption(f"Using {PROVIDER_LABELS[ai[0]]}" + (f" · {ai[2]}" if ai[2] else ""))
            if st.button("Generate with AI", icon=":material/auto_awesome:", disabled=not ai, key="gen_ai"):
                provider, key, model = ai
                payload = m.kpi_payload(ctx.cur, ctx.prev, ctx.channel_table, ctx.start, ctx.end)
                try:
                    with st.spinner(f"{PROVIDER_LABELS[provider]} is analysing the KPIs…"):
                        new = generate_report(payload, key, provider=provider, model=model)
                except AIError as e:
                    st.error(f"Report not generated. {e}")
                else:
                    # Save straight away, but keep the previous report so Undo can restore it.
                    # session_state is cleared on a browser refresh, which ends the Undo window.
                    if settings.gsheet_id():
                        st.session_state.ai_undo = {"mode": "session", "data": st.session_state.get("quick_report")}
                        st.session_state.quick_report = {**new, "week_start": str(ctx.start), "week_end": str(ctx.end), "meta": {}}
                    else:
                        prev = AI_REPORT_FILE.read_bytes() if AI_REPORT_FILE.exists() else None
                        save_ai_report(new, str(ctx.start), str(ctx.end), provider_label=PROVIDER_LABELS[provider])
                        st.session_state.ai_undo = {"mode": "file", "data": prev}
                        st.cache_data.clear()
                    st.toast("New AI report saved.", icon=":material/check_circle:")
                    st.rerun()
            if (ctx.end - ctx.start).days + 1 < 7:
                st.warning("Short periods are noisy — use 7 days or more for a meaningful report.",
                           icon=":material/warning:")

            undo = st.session_state.get("ai_undo")
            if undo:
                st.caption("New report saved. Undo restores the previous one.")
                if st.button("Undo", icon=":material/undo:", key="undo_ai"):
                    if undo["mode"] == "session":
                        st.session_state.quick_report = undo["data"]
                    else:
                        if undo["data"] is None:
                            AI_REPORT_FILE.unlink(missing_ok=True)
                        else:
                            AI_REPORT_FILE.write_bytes(undo["data"])
                        st.cache_data.clear()
                    del st.session_state["ai_undo"]
                    st.toast("Previous AI report restored.", icon=":material/undo:")
                    st.rerun()
            if st.session_state.get("quick_report"):
                ui.ai_report_card(st.session_state.quick_report)
