# Lumora Analytics: notes for Claude Code

Streamlit + Plotly sales BI dashboard for a fictional home-goods company (Lumora Home). Portfolio project; all data is sample data.

## Run
```
python -m pip install -r requirements.txt
python -m streamlit run app.py
```
Rebuild sample data: `python data/generate_sample_data.py`

## Structure
- `app.py`: page config, cached loaders, filter bar (period, date range, Filters popover, Export, Refresh), builds a `Context` passed to every page, routing via `st.session_state.page`
- `core/bi.py`: all sales BI calculations (orders data). Metric definitions are in its docstring; keep them the single source of truth
- `core/metrics.py`, `core/data.py`: marketing channel data and AI report (local files or Google Sheets via `GSHEET_ID`)
- `core/ai.py`, `core/n8n.py`, `core/settings.py`: Claude API, n8n webhook, secrets
- `ui/theme.py` (colours, formats, Plotly template), `ui/components.py` (HTML components), `ui/charts.py` + `ui/bi_charts.py` (Plotly)
- `views/*.py`: one module per page, each with `SECTION`, `TITLE`, `SUBTITLE` and `render(ctx)`
- `assets/style.css`: all styling. Cards are `st.container(key="card_...")`

## Design rules (keep these)
- Dark theme, teal `#2DD4BF` + blue `#3B82F6` accents, Inter font. Don't restyle without being asked.
- Overview is the 10-second view only: 6 KPIs, one revenue trend, max 3 highlights, compact category/region breakdowns. Detail belongs on its own page.
- Don't show the same table or chart on two pages. Use `st.expander` for secondary detail (progressive disclosure).
- Never hardcode metric values; everything is calculated from `data/`.
- HTML passed to `st.markdown` must not start lines with 4+ spaces (Markdown turns them into code blocks). Escape data with `html.escape`.
- Streamlit >= 1.45 (uses `segmented_control`, `container(key=)`, `icon=` on inputs).
