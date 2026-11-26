// n8n Code node: "Parse AI report + build email"
// Reads the LLM answer, checks it is valid JSON with exactly 2 highlights, 2 risks and 3 actions,
// then builds the HTML email, the Slack text and the rows saved for the dashboard.
const DASHBOARD_URL = 'https://lumora-analytics.streamlit.app';   // change if you deploy your own copy
// Public link to assets/logo.png (e.g. the GitHub "raw" link once the repo is public).
// Gmail blocks embedded images, so the logo must be hosted online. Leave empty to show the "L" badge instead.
const LOGO_URL = 'https://raw.githubusercontent.com/jethaiautomations-sudo/lumora-analytics/main/assets/logo.png';

const ai = $input.first().json;
const k = $('Calculate KPIs').first().json;

const raw = String(ai.choices?.[0]?.message?.content ?? '').trim();
if (!raw) throw new Error('OpenAI returned no message content: ' + JSON.stringify(ai).slice(0, 300));
let report;
try {
  report = JSON.parse(raw.replace(/^```(json)?/i, '').replace(/```$/, '').trim());
} catch (err) {
  throw new Error('LLM did not return valid JSON: ' + raw.slice(0, 300));
}
if (typeof report.summary !== 'string' || !report.summary.trim()) {
  throw new Error('LLM report: "summary" must be a non-empty string');
}
const expected = { highlights: 2, risks: 2, actions: 3 };
for (const [key, n] of Object.entries(expected)) {
  const items = report[key];
  if (!Array.isArray(items)) throw new Error('LLM report: "' + key + '" must be a list of ' + n + ' strings');
  if (items.length !== n) throw new Error('LLM report: "' + key + '" must have exactly ' + n + ' items (got ' + items.length + ')');
  if (!items.every(i => typeof i === 'string' && i.trim())) throw new Error('LLM report: every item in "' + key + '" must be a non-empty string');
}

// ---------- formatting ----------
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const money = n => '$' + Math.round(n).toLocaleString('en-US');
const fmtDate = iso => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
const period = `${fmtDate(k.period.curStart)} – ${fmtDate(k.period.curEnd)} ${k.period.curEnd.slice(0, 4)}`;
const arrow = c => (c > 0 ? '↑' : c < 0 ? '↓' : '–');
const delta = (c, unit) => {
  if (c === null || c === undefined) return '–';
  const a = Math.abs(c);
  const num = unit === '%' ? a.toFixed(1) + '%' : unit === 'pts' ? a.toFixed(a < 1 ? 2 : 1) + ' pts' : a.toFixed(2) + '×';
  return `${arrow(c)} ${num}`;
};

const C = { ink: '#0F172A', body: '#334155', muted: '#64748B', faint: '#94A3B8', line: '#E2E8F0', bg: '#F1F5F9',
            teal: '#0D9488', tealSoft: '#CCFBF1', good: '#047857', goodBg: '#D1FAE5', bad: '#B91C1C', badBg: '#FEE2E2',
            flatBg: '#F1F5F9', dark: '#0B0F14' };

const K = k.kpis;
const kpis = [
  { label: 'Revenue',     value: money(K.revenue_usd.current),               k: K.revenue_usd,         goodUp: true },
  { label: 'Orders',      value: K.orders.current.toLocaleString('en-US'),   k: K.orders,              goodUp: true },
  { label: 'Avg. order',  value: '$' + K.aov_usd.current.toFixed(2),         k: K.aov_usd,             goodUp: true },
  { label: 'Conversion',  value: K.conversion_rate_pct.current.toFixed(2) + '%', k: K.conversion_rate_pct, goodUp: true },
  { label: 'Paid ROAS',   value: K.paid_roas.current.toFixed(2) + '×',       k: K.paid_roas,           goodUp: true },
  { label: 'Return rate', value: K.return_rate_pct.current.toFixed(1) + '%', k: K.return_rate_pct,     goodUp: false },
];

const pill = (c, unit, goodUp) => {
  const good = c === 0 || c === null ? null : (c > 0) === goodUp;
  const [fg, bg] = good === null ? [C.muted, C.flatBg] : good ? [C.good, C.goodBg] : [C.bad, C.badBg];
  return `<span style="display:inline-block;padding:2px 8px;border-radius:999px;background:${bg};color:${fg};font-size:12px;font-weight:600;white-space:nowrap">${delta(c, unit)}</span>`;
};

const tile = t => `
  <td width="33.33%" valign="top" style="padding:6px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid ${C.line};border-radius:10px;background:#FFFFFF">
      <tr><td style="padding:14px 14px 12px">
        <div style="font-size:12px;color:${C.muted};letter-spacing:.02em">${t.label}</div>
        <div style="font-size:22px;line-height:28px;font-weight:700;color:${C.ink};margin:4px 0 8px">${t.value}</div>
        ${pill(t.k.change, t.k.change_unit, t.goodUp)}
      </td></tr>
    </table>
  </td>`;
const kpiRows = [kpis.slice(0, 3), kpis.slice(3)].map(r => `<tr>${r.map(tile).join('')}</tr>`).join('');

const section = (title, color, bg, items, numbered) => `
  <tr><td style="padding:22px 32px 0">
    <div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:${color};margin:0 0 10px">${title}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      ${items.map((text, i) => `
      <tr><td style="padding:0 0 8px">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:${bg};border-radius:8px">
          <tr>
            <td width="4" style="background:${color};border-radius:8px 0 0 8px"></td>
            <td width="30" valign="top" style="padding:12px 0 12px 12px;font-size:13px;font-weight:700;color:${color}">${numbered ? (i + 1) + '.' : '●'}</td>
            <td style="padding:12px 14px 12px 4px;font-size:14px;line-height:21px;color:${C.body}">${esc(text)}</td>
          </tr>
        </table>
      </td></tr>`).join('')}
    </table>
  </td></tr>`;

const revUp = K.revenue_usd.change >= 0;
const headline = `Revenue ${revUp ? 'up' : 'down'} ${Math.abs(K.revenue_usd.change).toFixed(1)}% to ${money(K.revenue_usd.current)}`;

const html = `<!doctype html>
<html><body style="margin:0;padding:0;background:${C.bg}">
<div style="display:none;max-height:0;overflow:hidden">${esc(headline)}. ${esc(report.summary)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:${C.bg};font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<tr><td align="center" style="padding:28px 12px">
  <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#FFFFFF;border-radius:14px;overflow:hidden;border:1px solid ${C.line}">

    <!-- header -->
    <tr><td style="background:${C.dark};padding:20px 32px">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
        <td valign="middle">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            ${LOGO_URL
              ? `<td width="40" valign="middle"><img src="${LOGO_URL}" width="40" height="40" alt="Lumora" style="display:block;width:40px;height:40px;border-radius:50%;border:0"></td>`
              : `<td width="30" height="30" align="center" valign="middle" style="background:#2DD4BF;background-image:linear-gradient(135deg,#2DD4BF,#3B82F6);border-radius:8px;color:#04110E;font-weight:800;font-size:15px">L</td>`}
            <td style="padding-left:12px">
              <div style="color:#F8FAFC;font-size:15px;font-weight:700;line-height:18px">Lumora Analytics</div>
              <div style="color:#94A3B8;font-size:12px;line-height:16px">Weekly sales report</div>
            </td>
          </tr></table>
        </td>
        <td align="right" valign="middle">
          <span style="display:inline-block;padding:5px 12px;border:1px solid #334155;border-radius:999px;color:#CBD5E1;font-size:12px;white-space:nowrap">${period}</span>
        </td>
      </tr></table>
    </td></tr>

    <!-- headline -->
    <tr><td style="padding:28px 32px 6px">
      <div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:${C.teal}">This week at a glance</div>
      <div style="font-size:24px;line-height:31px;font-weight:700;color:${C.ink};margin:6px 0 10px">${esc(headline)}</div>
      <div style="font-size:15px;line-height:23px;color:${C.body}">${esc(report.summary)}</div>
    </td></tr>

    <!-- KPI tiles -->
    <tr><td style="padding:16px 26px 0">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">${kpiRows}</table>
      <div style="font-size:11px;color:${C.faint};padding:6px 6px 0">Compared with the previous 7 days (${fmtDate(k.period.prevStart)} – ${fmtDate(k.period.prevEnd)}). Green = good, red = needs attention.</div>
    </td></tr>

    ${section('Risks to watch', C.bad, '#FEF2F2', report.risks, false)}
    ${section('Highlights', C.good, '#ECFDF5', report.highlights, false)}
    ${section('Recommended actions', C.teal, '#F0FDFA', report.actions, true)}

    <!-- CTA -->
    <tr><td align="center" style="padding:26px 32px 30px">
      <a href="${DASHBOARD_URL}" style="display:inline-block;background:${C.dark};color:#FFFFFF;text-decoration:none;font-size:14px;font-weight:600;padding:12px 22px;border-radius:8px">Open the dashboard →</a>
    </td></tr>

    <!-- footer -->
    <tr><td style="border-top:1px solid ${C.line};padding:16px 32px;background:#F8FAFC">
      <div style="font-size:11px;line-height:17px;color:${C.faint}">
        Generated automatically by n8n + AI. Figures are calculated from the daily sales sheet; the AI only explains them.<br>
        Lumora Home is a fictional company — sample data for a portfolio demo.
      </div>
    </td></tr>

  </table>
</td></tr></table>
</body></html>`;

// ---------- Slack (mrkdwn) ----------
const slack = [
  `*📊 Weekly sales report · ${period}*`,
  `*${headline}* · Orders ${K.orders.current.toLocaleString('en-US')} (${delta(K.orders.change, '%')}) · Paid ROAS ${K.paid_roas.current.toFixed(2)}× (${delta(K.paid_roas.change, 'x')})`,
  '',
  report.summary,
  '',
  '*⚠️ Risks*', ...report.risks.map(r => '• ' + r),
  '',
  '*✅ Highlights*', ...report.highlights.map(h => '• ' + h),
  '',
  '*🎯 Actions*', ...report.actions.map((a, i) => `${i + 1}. ${a}`),
  '',
  `<${DASHBOARD_URL}|Open the dashboard>`,
].join('\n');

// Rows in the same shape the dashboard reads (section, text)
const dashboardRows = [
  { section: 'summary', text: report.summary },
  ...report.highlights.map(text => ({ section: 'highlight', text })),
  ...report.risks.map(text => ({ section: 'risk', text })),
  ...report.actions.map(text => ({ section: 'action', text })),
].map(r => ({ week_start: k.period.curStart, week_end: k.period.curEnd, generated_at: new Date().toISOString(), ...r }));

return [{ json: {
  subject: `📊 ${headline} · Weekly sales report (${period})`,
  html, slack, dashboardRows, report,
} }];
