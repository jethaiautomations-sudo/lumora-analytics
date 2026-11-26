"""Optional: generate the AI report from the dashboard with OpenAI or Claude.

Uses only the standard library. Set ONE of these in .streamlit/secrets.toml
(or as environment variables):
- OPENAI_API_KEY      (optional OPENAI_MODEL, default gpt-4o-mini)
- ANTHROPIC_API_KEY   (Claude)
If both are set, OpenAI is used. Same prompt as the n8n workflow.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5-5"

SYSTEM_PROMPT = """\
You are a senior e-commerce analyst at an online home-goods store, writing the performance report for busy executives. They read it in under a minute and act on it.

DATA RULES
- The KPI JSON compares the current period with the previous period of the same length: overall KPIs, then one entry per channel with current and previous revenue, ad spend, ROAS and return rate.
- Use ONLY numbers that appear in the JSON. Never invent, estimate or recalculate a figure (no new totals, differences or percentages). If a change you want to mention is not given, quote the two values instead ("from $7.5K to $13.0K").
- Do not invent causes the data does not show.

WHAT TO REPORT
- The JSON includes an "alerts" list: rule-based checks computed by code, already ordered most severe first (critical, then warning, then positive). Treat it as the source of truth for what is a risk.
- risks: take them from the "critical" and "warning" alerts, in the order given (most severe first). Use each alert's channel and figures; you may add the matching numbers from that channel's data (e.g. ad spend or revenue) and why it matters. If there are fewer than two critical/warning alerts, fill the remaining slot with the largest revenue decline in the channel data, described with its values only.
- Never decide on your own whether a value is above or below a threshold, and never mention a threshold or limit that is not stated in the alerts.
- highlights: take them from the "positive" alerts first, then from the channels with the largest revenue gains.
- Rank by business impact (money at stake), not by the size of a % change. Ignore small moves under about 5% unless the money involved is large.

STYLE
- Round for readability: money as $176.9K or $13.0K ($1.2M for millions); percentages as whole numbers (69%), or one decimal under 10% (6.4%); ROAS to one decimal with × (1.3×); return rates to whole numbers or one decimal under 10%.
- Plain, direct English. No filler, no hedging, no jargon beyond ROAS.

OUTPUT
- summary: 2-3 sentences: the headline result (revenue and its change), the main driver (which channel), and the biggest risk.
- highlights (2): each names the channel, the number, and why it matters.
- risks (2): the two most severe critical/warning alerts; each names the channel, the number, and why it matters.
- actions (3): each must address one of the risks or highlights you wrote (name the same channel), and be specific and practical: what to change, where, and by when. No generic advice such as "enhance the strategy", "optimise campaigns", "monitor closely" or "improve targeting".

ACTION RULES
- Every number in an action must appear in the KPI JSON. Never invent targets, thresholds or goals (no "aim for $11.3K", "get returns below 17%", "raise ROAS to 3×").
- Check the direction before recommending a change. Only say "cut spend back to last period's level" if that channel's ad spend went UP; if it went down or stayed flat, do not recommend returning to the previous value. The same applies to revenue, ROAS and return rate: the action must move the metric in the direction the data says is needed.
- Prefer actions the data clearly supports, such as "investigate why ... ", "shift budget from X to Y" (X weaker, Y stronger in the data), "pause the worst-performing ads / listing", "audit the most-returned products".
- If the data does not support a specific number, give the action without a number.

EXAMPLES (style only: a different business with made-up channels and figures; never reuse these names or numbers)
- Highlight: "Affiliates revenue rose 42% to $48.2K with no ad spend, making it the cheapest source of growth this period."
- Risk: "TikTok Ads spend rose 58% to $21.4K while ROAS fell from 3.1× to 1.6×, so the extra budget is buying far less revenue; it is now the least efficient paid channel."
- Action: "Cut TikTok Ads spend back to last period's ~$13.5K this week, pause the weakest ad sets, and raise it again only once ROAS recovers."

Return ONLY valid JSON, with no markdown and no other text, with EXACTLY 2 highlights, 2 risks and 3 actions, in this shape:
{"summary": "string", "highlights": ["string", "string"], "risks": ["string", "string"], "actions": ["string", "string", "string"]}"""

PROVIDER_LABELS = {"openai": "OpenAI", "anthropic": "Claude"}


class AIError(Exception):
    pass


def _post(url: str, body: dict, headers: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")[:200]
        if e.code == 401:
            raise AIError("The API key was rejected. Check the key in .streamlit/secrets.toml.") from e
        if e.code == 429:
            raise AIError("Rate limit or no credit left on the API account. " + detail) from e
        raise AIError(f"API returned {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise AIError(f"Could not reach the API: {e.reason}") from e


EXPECTED_COUNTS = {"highlights": 2, "risks": 2, "actions": 3}


def _parse(text: str) -> dict:
    """Parse the reply and check its shape strictly. Raises AIError saying what is wrong."""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        report = json.loads(text)
    except json.JSONDecodeError as e:
        raise AIError("The reply was not valid JSON.") from e
    if not isinstance(report, dict):
        raise AIError("The reply must be a JSON object.")
    problems = []
    if not isinstance(report.get("summary"), str) or not report["summary"].strip():
        problems.append('"summary" must be a non-empty string')
    for key, n in EXPECTED_COUNTS.items():
        items = report.get(key)
        if not isinstance(items, list):
            problems.append(f'"{key}" must be a list of {n} strings')
        elif len(items) != n:
            problems.append(f'"{key}" must have exactly {n} items (got {len(items)})')
        elif not all(isinstance(i, str) and i.strip() for i in items):
            problems.append(f'every item in "{key}" must be a non-empty string')
    if problems:
        raise AIError("; ".join(problems) + ".")
    return report


def _call(provider: str, messages: list[dict], api_key: str, model: str | None, timeout: int) -> str:
    if provider == "openai":
        data = _post(OPENAI_URL, {
            "model": model or OPENAI_DEFAULT_MODEL,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        }, {"Authorization": f"Bearer {api_key}"}, timeout)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise AIError("Unexpected response from OpenAI.") from e
    data = _post(ANTHROPIC_URL, {
        "model": model or ANTHROPIC_MODEL, "max_tokens": 1200, "system": SYSTEM_PROMPT,
        "messages": messages,
    }, {"x-api-key": api_key, "anthropic-version": "2023-06-01"}, timeout)
    return "".join(c.get("text", "") for c in data.get("content", []) if c.get("type") == "text")


def generate_report(kpi_payload: dict, api_key: str, provider: str = "openai",
                    model: str | None = None, timeout: int = 90) -> dict:
    user_msg = "KPIs (selected period vs previous period):\n" + json.dumps(kpi_payload, indent=2, default=str)
    messages = [{"role": "user", "content": user_msg}]
    text = _call(provider, messages, api_key, model, timeout)
    try:
        return _parse(text)
    except AIError as first:
        # One retry: tell the model exactly what was wrong.
        messages += [
            {"role": "assistant", "content": text or "(empty reply)"},
            {"role": "user", "content": f"Your reply did not match the required format: {first} "
                                        "Return the full report again as ONLY valid JSON with exactly "
                                        "2 highlights, 2 risks and 3 actions, each a non-empty string."},
        ]
        text = _call(provider, messages, api_key, model, timeout)
        try:
            return _parse(text)
        except AIError as second:
            raise AIError(f"The AI reply was in the wrong format twice. Last problem: {second}") from second
