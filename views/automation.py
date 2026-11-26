from __future__ import annotations

from pathlib import Path

import streamlit as st

from core import settings
from core.metrics import ALERT_RULES
from ui import components as ui

SECTION = "Automation"
TITLE = "Reporting automation"
SUBTITLE = "The n8n workflow that builds and sends this report every Monday, with no manual work."

WORKFLOW_FILE = Path(__file__).resolve().parent.parent / "assets" / "n8n" / "ai-weekly-sales-report.n8n.json"

STEPS = [
    ("Trigger", "Every Monday at 7:00 AM, or on demand from this dashboard through a webhook."),
    ("Pull data", "Reads daily orders, sessions and ad spend from Google Sheets (or Shopify, a database or an ads API)."),
    ("Calculate KPIs", "A Code node computes revenue, AOV, conversion, ROAS and returns by channel."),
    ("AI analysis", "An LLM (Claude or OpenAI) turns the KPIs into a summary, highlights, risks and actions as strict JSON."),
    ("Validate", "The output is checked; the run stops if the JSON is invalid or a section is missing."),
    ("Deliver", "Emails an HTML report, posts to Slack and saves the report for this dashboard."),
]


def render(ctx) -> None:
    with st.container(key="card_flow"):
        with ui.section_head("Workflow", "Same KPI definitions in n8n and in this dashboard, so the numbers always match.",
                             "flow_dl"):
            if WORKFLOW_FILE.exists():
                st.download_button("Download n8n workflow", WORKFLOW_FILE.read_bytes(),
                                   file_name=WORKFLOW_FILE.name, mime="application/json",
                                   icon=":material/download:", key="dl_workflow")
        ui.workflow_steps(STEPS)

    c1, c2 = st.columns(2)
    with c1:
        with st.container(key="card_rules"):
            ui.section_title("Alert rules", "Checked on every refresh, before any AI step.")
            st.markdown(
                f"- Paid ROAS drops **{ALERT_RULES['roas_drop_pct']}%** or more vs the previous period\n"
                f"- Return rate reaches **{ALERT_RULES['return_rate_max']}%** or more\n"
                f"- Channel revenue falls **{ALERT_RULES['revenue_drop_pct']}%** or more\n"
                f"- Channel revenue grows **{ALERT_RULES['revenue_jump_pct']}%** or more"
            )
    with c2:
        with st.container(key="card_conn"):
            ui.section_title("Connections", "Set in .streamlit/secrets.toml.")
            sheet, hook = settings.gsheet_id(), settings.n8n_webhook_url()
            st.markdown(
                f"- **Data source:** {'Google Sheets (shared with n8n)' if sheet else 'Local files in /data'}\n"
                f"- **n8n webhook:** {'Connected' if hook else 'Not set'}\n"
                f"- **AI for quick reports:** {('Connected (' + {'openai': 'OpenAI', 'anthropic': 'Claude'}[settings.ai_provider()[0]] + ')') if settings.ai_provider() else 'Not set'}"
            )
