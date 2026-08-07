"""Generate a self-contained scrollable HTML replay viewer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def render_replay(log_path: str | Path, output_path: str | Path) -> None:
    records = _read_records(Path(log_path))
    data = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=True).replace("</", "<\\/")
    title = "Bench-bench replay"
    document = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: dark; --bg:#0e1218; --panel:#171e28; --line:#2d3a4c; --ink:#edf2f7; --muted:#9aa9bb; --accent:#75d5b3; --warn:#f6c56f; --bad:#f28b82; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:linear-gradient(140deg,#0e1218,#111b24 55%,#152329); color:var(--ink); font:15px/1.5 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
header {{ position:sticky; top:0; z-index:2; backdrop-filter:blur(14px); background:rgba(14,18,24,.92); border-bottom:1px solid var(--line); padding:18px clamp(18px,4vw,56px); }}
h1 {{ margin:0 0 4px; font-size:clamp(24px,4vw,38px); letter-spacing:-.03em; }}
.sub {{ color:var(--muted); }}
.stats {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }}
.stat {{ border:1px solid var(--line); background:var(--panel); padding:8px 12px; border-radius:999px; }}
.stat strong {{ color:var(--accent); }}
main {{ max-width:1100px; margin:0 auto; padding:28px clamp(18px,4vw,56px) 72px; }}
.controls {{ display:flex; gap:10px; align-items:center; margin-bottom:22px; }}
button {{ border:1px solid var(--line); color:var(--ink); background:var(--panel); border-radius:8px; padding:8px 12px; cursor:pointer; }}
button:hover {{ border-color:var(--accent); }}
#timeline {{ display:grid; gap:14px; }}
.week {{ border:1px solid var(--line); border-radius:14px; background:rgba(23,30,40,.9); overflow:hidden; }}
.week summary {{ list-style:none; cursor:pointer; padding:16px 18px; display:flex; flex-wrap:wrap; gap:10px 18px; align-items:baseline; }}
.week summary::-webkit-details-marker {{ display:none; }}
.week summary:hover {{ background:rgba(117,213,179,.06); }}
.week h2 {{ margin:0; font-size:18px; min-width:100px; }}
.chip {{ border:1px solid var(--line); border-radius:999px; padding:2px 8px; color:var(--muted); font-size:13px; }}
.chip.good {{ color:var(--accent); }} .chip.warn {{ color:var(--warn); }} .chip.bad {{ color:var(--bad); }}
.body {{ border-top:1px solid var(--line); padding:16px 18px 18px; display:grid; gap:14px; }}
.columns {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:12px; }}
.card {{ border:1px solid var(--line); border-radius:10px; padding:12px; background:rgba(14,18,24,.55); }}
.card h3 {{ margin:0 0 8px; font-size:13px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }}
pre {{ white-space:pre-wrap; overflow-wrap:anywhere; margin:0; color:#d5dfeb; font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace; }}
.interrupt {{ border-left:3px solid var(--warn); padding:8px 10px; background:rgba(246,197,111,.08); }}
.empty {{ color:var(--muted); }}
@media (max-width:600px) {{ .week summary {{ display:block; }} .chip {{ display:inline-block; margin:5px 4px 0 0; }} }}
</style>
</head>
<body>
<header><h1>Bench-bench replay</h1><div class="sub">A public episode log, week by week.</div><div class="stats" id="stats"></div></header>
<main><div class="controls"><button id="openAll">Open all</button><button id="closeAll">Close all</button><span class="sub">Scroll through the year to see plans, interruptions, and consequences.</span></div><section id="timeline" aria-live="polite"></section></main>
<script id="episode-data" type="application/json">{data}</script>
<script>
const records = JSON.parse(document.getElementById('episode-data').textContent);
const start = records.find(r => r.type === 'episode_start' || r.type === 'run_start') || {{}};
const weeks = records.filter(r => r.type === 'week' || r.type === 'turn').map(r => ({{
  week: r.week, action: r.action || {{}}, outcome: r.outcome || {{}},
  interrupts: r.interrupts || r.reactive_turns || [], days: r.days || []
}}));
const end = records.find(r => r.type === 'final_result' || r.type === 'run_end') || {{result:{{}}}};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const money = cents => '$' + (Number(cents || 0) / 100).toFixed(2);
const stat = (label, value) => `<span class="stat">${{esc(label)}} <strong>${{esc(value)}}</strong></span>`;
const result = end.result || {{}};
document.getElementById('stats').innerHTML = [
  stat('Seed', start.seed), stat('Weeks', weeks.length), stat('Final 1RM', `${{result.final_1rm_kg ?? '—'}} kg`),
  stat('Sessions', `${{result.completed_sessions ?? '—'}}/${{result.planned_sessions ?? '—'}}`), stat('Pain days', result.pain_days ?? '—'), stat('Spend', money(result.total_spend_cents))
].join('');
const summary = (week, outcome) => `<h2>Week ${{week.week}}</h2><span class="chip ${{outcome.completed_sessions >= 2 ? 'good' : outcome.completed_sessions ? 'warn' : 'bad'}}">planned ${{outcome.planned_sessions}} · transformed ${{outcome.transformed_sessions ?? 0}} · attempted ${{outcome.attempted_sessions ?? 0}} · completed ${{outcome.completed_sessions}} · missed ${{outcome.missed_sessions ?? 0}}</span><span class="chip">sleep ${{outcome.average_sleep_hours}}h</span><span class="chip">estimate ${{outcome.estimated_1rm_kg}} kg</span><span class="chip">pain ${{esc(outcome.pain_band)}}</span>`;
const timeline = document.getElementById('timeline');
timeline.innerHTML = weeks.map((record, index) => {{
  const outcome = record.outcome || {{}};
  const action = record.action || {{}};
  const interrupts = (record.interrupts || []).map(item => `<div class="interrupt"><strong>${{esc(item.title)}}</strong><br><span class="sub">${{esc(item.kind)}} — reactive choice: ${{esc(item.reactive_action?.response ?? item.action?.response)}}</span></div>`).join('') || '<span class="empty">No interrupt fired.</span>';
  const sessions = (action.sessions || []).map(session => `${{session.day}}: ${{esc(session.focus)}} ${{session.sets}}×${{session.reps}} @ ${{session.load_kg}} kg (${{session.location}})`).join('\\n') || 'No planned barbell sessions.';
  const transformations = (outcome.transformation_reasons || []).join('\\n') || 'None';
  return `<details class="week" ${{index === weeks.length - 1 ? '' : ''}}><summary>${{summary(record, outcome)}}</summary><div class="body"><p>${{esc(outcome.headline)}}</p><div class="columns"><div class="card"><h3>Plan</h3><pre>${{esc(sessions)}}</pre></div><div class="card"><h3>Life allocation</h3><pre>${{esc(JSON.stringify(action.life || {{}}, null, 2))}}</pre></div></div><div class="card"><h3>Interrupts</h3>${{interrupts}}</div><div class="card"><h3>Simulator transformations</h3><pre>${{esc(transformations)}}</pre></div><div class="card"><h3>Executed days</h3><pre>${{esc((record.days || []).map(day => `D${{day.day}}  ${{day.sleep_hours}}h  ${{day.note}}`).join('\\n'))}}</pre></div></div></details>`;
}}).join('');
document.getElementById('openAll').onclick = () => document.querySelectorAll('details').forEach(node => node.open = true);
document.getElementById('closeAll').onclick = () => document.querySelectorAll('details').forEach(node => node.open = false);
</script>
</body></html>'''
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
