const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) } });
  if (!r.ok) throw new Error((await r.text()) || r.status);
  const ct = r.headers.get('content-type') || '';
  return ct.includes('json') ? r.json() : r.text();
}

function toast(msg) {
  let t = document.getElementById('toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; document.body.appendChild(t); }
  t.textContent = msg;
  t.className = 'show';
  clearTimeout(t._h);
  t._h = setTimeout(() => { t.className = ''; }, 3500);
}

let VIEW_TOKEN = 0;

const NAV = [
  ['/', '◈', 'Overview'], ['/sources', '⛁', 'Sorgenti'], ['/loop', '↻', 'Loop'],
  ['/logs', '≡', 'Logs'], ['/config', '⌘', 'Config'], ['/updates', '↑', 'Update'],
];

function shell(active) {
  return `
  <aside class="rail">
    <div class="logo">◈</div>
    ${NAV.map(([p, i, l]) => `<a class="ric ${p === active ? 'on' : ''}" href="#${p}" title="${l}">${i}</a>`).join('')}
    <div class="grow"></div>
    <div class="foot">v26.10<br>solaredge</div>
  </aside>
  <main class="main">
    <div class="top">
      <div class="crumb">Collector <span style="opacity:.4">/</span> <b>${NAV.find(n => n[0] === active)?.[2] || 'Overview'}</b></div>
      <div class="r"><button class="kbd" id="palBtn" title="Command palette">⌘K</button><span class="env">PROD</span><span id="clock">--:--:--</span><span class="dot"></span></div>
    </div>
    <div id="view"></div>
  </main>`;
}

function tick() { const c = $('#clock'); if (c) c.textContent = new Date().toLocaleTimeString('it-IT'); }

function ping() {
  api('/api/ping').then(() => {}).catch(() => {
    const dot = $('.top .dot'), env = $('.top .env');
    if (dot) { dot.style.background = 'var(--coral)'; dot.style.boxShadow = '0 0 8px var(--coral)'; }
    if (env) { env.textContent = 'OFFLINE'; env.style.color = 'var(--coral)'; env.style.borderColor = 'rgba(255,92,122,.35)'; env.style.background = 'rgba(255,92,122,.12)'; }
  });
}

function flowTag(flow) {
  const f = String(flow || 'sistema').toLowerCase();
  return f.includes('realtime') ? 't-rt' : f.includes('api') ? 't-api' : f.includes('web') ? 't-web' : f.includes('gme') ? 't-gme' : f.includes('bolletta') ? 't-gme' : 't-ok';
}

function logLine(l) {
  const flow = l.flow_type || l.flow || l.source || 'sistema';
  const lvl = String(l.level || 'INFO').toUpperCase();
  const cls = lvl.includes('ERR') || lvl.includes('CRIT') ? 't-err' : flowTag(flow);
  const ts = l.timestamp || l.time || '';
  return `<div class="ln"><span class="tm">${esc(String(ts).slice(-8))}</span><span class="tag ${cls}">${esc(String(flow).slice(0,8).toUpperCase())}</span><span class="msg">${esc(l.message || l.msg || '')}</span></div>`;
}

function fmtDur(a, b) {
  const p = (t) => { const [h, m, s] = String(t).split(':').map(Number); return h * 3600 + m * 60 + s; };
  const d = p(b) - p(a);
  return d >= 0 && d < 86400 ? d + 's' : '—';
}

function extractRuns(logs) {
  const runs = [];
  let cur = null;
  for (const l of logs) {
    const msg = String(l.message || l.msg || '');
    const flow = String(l.flow_type || l.flow || 'sistema');
    const ts = l.timestamp || l.time || '';
    if (/Avvio (flusso|raccolta)/i.test(msg)) {
      if (cur) runs.push(cur);
      cur = { flow, start: ts, end: ts, ok: true, lines: [l] };
      continue;
    }
    if (!cur) continue;
    cur.lines.push(l);
    cur.end = ts;
    if (/ERROR|❌|fallit/i.test(msg)) cur.ok = false;
  }
  if (cur) runs.push(cur);
  return runs;
}

function toggleHtml(kind, id, on) {
  return `<span class="sw ${on ? 'on' : ''}" data-toggle="${kind}" data-id="${esc(id)}"><i></i></span>`;
}

function bindToggles(root) {
  root.querySelectorAll('[data-toggle]').forEach(el => el.addEventListener('click', async (e) => {
    e.stopPropagation();
    const kind = el.dataset.toggle, id = el.dataset.id;
    const map = { web: '/api/devices/toggle', api: '/api/endpoints/toggle', modbus: '/api/modbus/devices/toggle', webmetric: '/api/devices/metrics/toggle', modbusmetric: '/api/modbus/devices/metrics/toggle', gme: '/api/gme/toggle' };
    let url = `${map[kind]}?id=${encodeURIComponent(id)}`;
    if (el.dataset.metric) url += '&metric=' + encodeURIComponent(el.dataset.metric);
    try { await api(url, { method: 'POST' }); route(); }
    catch (err) { toast('Toggle fallito: ' + err.message); }
  }));
}

const FLOWS = [
  { key: 'realtime', label: 'Realtime', note: 'Modbus inverter', stats: 'realtime_stats' },
  { key: 'web', label: 'Web scraping', note: 'Portale SolarEdge', stats: 'web_stats', last: 'web_last_at', next: 'web_next_at' },
  { key: 'api', label: 'API SolarEdge', note: 'Monitoring API', stats: 'api_stats', last: 'api_last_at', next: 'api_next_at' },
  { key: 'gme', label: 'GME', note: 'Mercato elettrico', stats: 'gme_stats', last: 'gme_last_at', next: 'gme_next_at' },
  { key: 'bolletta', label: 'Bolletta', note: 'ARERA / GO', stats: 'bolletta_stats', last: 'bolletta_last_at', next: 'bolletta_next_at' },
];

const FRESH_LIMIT = { Solaredge_Realtime: 120, Solaredge: 1800, GME: 108000, Bolletta: 108000 };

function fmtAge(sec) {
  if (sec == null) return '—';
  if (sec < 60) return sec + 's';
  if (sec < 3600) return Math.round(sec / 60) + ' min';
  if (sec < 86400) return Math.round(sec / 3600) + 'h';
  return Math.round(sec / 86400) + 'g';
}

function since(iso) {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? null : Math.round((Date.now() - t) / 1000);
}

function rel(iso) {
  const s = since(iso);
  if (s == null) return '';
  return s >= 0 ? fmtAge(s) + ' fa' : 'tra ' + fmtAge(-s);
}

function every(sec) {
  if (!sec) return '—';
  if (sec < 60) return sec + ' s';
  if (sec < 3600) return Math.round(sec / 60) + ' min';
  return Math.round(sec / 3600) + ' h';
}

function freshDot(name, age) {
  const limit = FRESH_LIMIT[name] || 3600;
  if (age == null) return 'er';
  if (age <= limit) return 'ok';
  return age <= limit * 2 ? 'wr' : 'er';
}

async function viewOverview() {
  const v = $('#view');
  const token = VIEW_TOKEN;
  const keepY = window.scrollY;
  if (!v.querySelector('.kpis')) v.innerHTML = '<div class="empty">caricamento…</div>'

  const res = await Promise.allSettled([
    api('/api/loop/status'), api('/api/sources?type=web'), api('/api/sources?type=api'),
    api('/api/sources?type=modbus'), api('/api/loop/logs?flow=all&limit=600'),
    api('/api/updates/status'), api('/api/freshness'), api('/api/config'),
  ]);
  if (token !== VIEW_TOKEN) return;
  const val = (i, fb) => (res[i].status === 'fulfilled' ? res[i].value : fb);

  const status = val(0, { stats: {} });
  const st = status.stats || {};
  const src = { web: val(1, {}), api: val(2, {}), modbus: val(3, {}) };
  const logs = val(4, { logs: [] }).logs || [];
  const upd = val(5, {});
  const fresh = val(6, { buckets: [], reachable: false });
  const cfg = val(7, {});
  const fe = status.flows_enabled || {};
  const gmeOn = fe.gme !== undefined ? !!fe.gme : !!(cfg.gme && cfg.gme.enabled);
  const bollettaOn = fe.bolletta !== undefined ? !!fe.bolletta : true;

  const count = (o) => {
    const list = Object.values(o || {});
    return {
      total: list.length,
      on: list.filter(d => d.enabled).length,
      mets: list.reduce((a, d) => a + Object.keys(d.measurements || {}).length, 0),
      metsOn: list.reduce((a, d) => a + Object.values(d.measurements || {}).filter(m => m.enabled).length, 0),
    };
  };
  const cw = count(src.web), ca = count(src.api), cm = count(src.modbus);
  const srcTotal = cw.total + ca.total + cm.total, srcOn = cw.on + ca.on + cm.on;
  const metTotal = cw.mets + ca.mets + cm.mets, metOn = cw.metsOn + ca.metsOn + cm.metsOn;

  const flowOf = (k) => st[k] || { executed: 0, success: 0, failed: 0 };
  const totals = ['realtime_stats', 'web_stats', 'api_stats', 'gme_stats', 'bolletta_stats']
    .reduce((a, k) => {
      const f = flowOf(k);
      a.run += f.executed || 0; a.ok += f.success || 0; a.failed += f.failed || 0;
      return a;
    }, { run: 0, ok: 0, failed: 0 });
  const done = totals.ok + totals.failed;
  const rate = done ? (100 * totals.ok / done).toFixed(1) : null;

  const errs = logs.filter(l => /ERROR|WARN|❌|⚠/i.test(String(l.level || '') + ' ' + String(l.message || l.msg || '')));
  const buckets = fresh.buckets || [];
  const retention = status.retention_config || {};

  v.innerHTML = `
    <div class="pagehead">
      <div><h1>Overview</h1><p>Riepilogo del collector · aggiornato alle ${esc(st.last_update_formatted || '—')}</p></div>
      <div style="margin-left:auto"><span class="tag ${status.loop_mode ? 't-ok' : 't-err'}">${status.loop_mode ? 'loop attivo' : 'loop fermo'}</span></div>
    </div>

    <div class="kpis">
      <div class="kpi info"><div class="t">Run eseguiti</div><div class="v">${totals.run}</div><div class="s">dall'avvio del collector</div></div>
      <div class="kpi ok"><div class="t">Completati</div><div class="v">${totals.ok}</div><div class="s">su ${done} conclusi</div></div>
      <div class="kpi ${totals.failed ? 'bad' : ''}"><div class="t">Falliti</div><div class="v">${totals.failed}</div><div class="s">${totals.failed ? 'da controllare nei log' : 'nessun errore di flusso'}</div></div>
      <div class="kpi ${rate === null || Number(rate) === 100 ? 'ok' : 'warn'}"><div class="t">Success rate</div><div class="v">${rate === null ? '—' : rate}<small>%</small></div><div class="s">${totals.ok}/${done} completati</div></div>
      <div class="kpi"><div class="t">Sorgenti attive</div><div class="v">${srcOn}<small>/${srcTotal}</small></div><div class="s">web ${cw.on} · api ${ca.on} · modbus ${cm.on}</div></div>
      <div class="kpi"><div class="t">Metriche attive</div><div class="v">${metOn}<small>/${metTotal}</small></div><div class="s">misure abilitate</div></div>
    </div>

    <div class="dash">
      <div class="c span-8">
        <div class="h"><span class="t">Pipeline</span><span class="m">sorgenti → collector → destinazioni</span></div>
        <div class="flow3">
          <div class="col">
            <div class="col-h">Sorgenti · device attivi</div>
            <div class="chip2"><span class="hd ${cw.on ? 'ok' : 'off'}"></span>Web scraping<b>${cw.on}/${cw.total}</b></div>
            <div class="chip2"><span class="hd ${ca.on ? 'ok' : 'off'}"></span>API SolarEdge<b>${ca.on}/${ca.total}</b></div>
            <div class="chip2"><span class="hd ${cm.on ? 'ok' : 'off'}"></span>Modbus<b>${cm.on}/${cm.total}</b></div>
            <div class="chip2"><span class="hd ${gmeOn ? 'ok' : 'off'}"></span>GME · PUN<b>${gmeOn ? 'attivo' : 'off'}</b></div>
            <div class="chip2"><span class="hd ${bollettaOn ? 'ok' : 'off'}"></span>Bolletta · ARERA<b>${bollettaOn ? 'attivo' : 'off'}</b></div>
          </div>
          <div class="rail-line"><i></i></div>
          <div class="node"><span><b>Collector</b><small>uptime ${esc(st.uptime_formatted || '—')}</small></span></div>
          <div class="rail-line outl"><i></i></div>
          <div class="col">
            <div class="col-h">Destinazioni · ultimo punto</div>
            ${buckets.length ? buckets.map(b => `<div class="chip2"><span class="hd ${freshDot(b.name, b.age_seconds)}"></span>${esc(b.name)}<b>${fmtAge(b.age_seconds)}</b></div>`).join('') : '<div class="chip2"><span class="hd er"></span>InfluxDB<b>n/d</b></div>'}
          </div>
        </div>
        <div class="bars-h"><span>Scritture per destinazione</span><span>punti nella finestra indicata</span></div>
        <div class="bars">
          ${buckets.map(b => {
            const max = Math.max(...buckets.map(x => x.points || 0), 1);
            const w = Math.max(2, Math.round(100 * Math.sqrt((b.points || 0) / max)));
            return `<div class="barrow">
              <span class="hd ${freshDot(b.name, b.age_seconds)}"></span>
              <span class="nm">${esc(b.name)}</span>
              <span class="bar"><i style="width:${w}%"></i></span>
              <span class="num">${b.points == null ? '—' : b.points.toLocaleString('it-IT')}</span>
              <span class="win">in ${esc(b.window)}</span>
              <span class="age">${fmtAge(b.age_seconds)}</span>
            </div>`;
          }).join('') || '<div class="empty">nessuna scrittura leggibile</div>'}
        </div>
      </div>

      <div class="c span-4">
        <div class="h"><span class="t">Salute del sistema</span></div>
        <div class="hrow"><span class="lbl">Loop</span><span class="val">${status.loop_mode ? 'attivo' : 'fermo'}</span></div>
        <div class="hrow"><span class="lbl">Uptime</span><span class="val">${esc(st.uptime_formatted || '—')}</span></div>
        <div class="hrow"><span class="lbl">Ultimo ciclo</span><span class="val">${esc(st.last_update_formatted || '—')}</span></div>
        <div class="hrow"><span class="lbl">InfluxDB</span><span class="val">${fresh.reachable ? 'raggiungibile' : 'non raggiungibile'}</span></div>
        <div class="hrow"><span class="lbl">Errori nel buffer</span><span class="val">${errs.length}</span></div>
        <div class="hrow"><span class="lbl">Aggiornamenti</span><span class="val">${upd.updates_available ? 'disponibili' : 'nessuno'}</span></div>
        <div class="hrow"><span class="lbl">Retention log</span><span class="val">${retention.all_hours ? retention.all_hours + 'h' : '—'}</span></div>
      </div>
    </div>

    <div class="c span-12">
      <div class="h"><span class="t">Flussi</span><span class="m">cadenza · ultimo e prossimo run · esiti della sessione</span></div>
      <div class="tblwrap"><table class="tbl">
        <thead><tr><th>Flusso</th><th>Intervallo</th><th>Ultimo run</th><th>Prossimo</th><th class="num">Eseguiti</th><th class="num">OK</th><th class="num">Falliti</th><th class="num">Esito</th></tr></thead>
        <tbody>${FLOWS.map(f => {
          const s = flowOf(f.stats);
          const d = (s.success || 0) + (s.failed || 0);
          const rate = d ? (100 * (s.success || 0) / d).toFixed(0) + '%' : '—';
          const lastTime = f.key === 'realtime' ? (st.last_update_formatted || '—') : (st[f.key + '_last_run'] || '—');
          const lastRel = f.key !== 'realtime' && st[f.last] ? rel(st[f.last]) : '';
          const nextRel = st[f.next] ? rel(st[f.next]) : '';
          const off = f.key === 'gme' && !gmeOn;
          return `<tr>
            <td><span class="name"><span class="hd ${off ? 'off' : 'ok'}"></span>${esc(f.label)}${off ? ' <span class="tag t-off">off</span>' : ''}</span></td>
            <td class="mono">${every((status.intervals_seconds || {})[f.key])}</td>
            <td>${esc(lastTime)}${lastRel ? ` <span class="sub">${lastRel}</span>` : ''}</td>
            <td>${esc(st[f.key + '_next_run'] || '—')}${nextRel ? ` <span class="sub">${nextRel}</span>` : ''}</td>
            <td class="num">${s.executed || 0}</td>
            <td class="num">${s.success || 0}</td>
            <td class="num">${s.failed || 0}</td>
            <td class="num">${rate}</td>
          </tr>`;
        }).join('')}</tbody>
      </table></div>
    </div>

    <div class="dash">
      <div class="c span-7">
        <div class="h"><span class="t">Errori e avvisi</span><span class="m">${errs.length} nel buffer</span></div>
        <div class="term" style="height:15rem" id="overr">${errs.slice(-40).map(logLine).join('') || '<div class="empty">nessun errore o avviso recente</div>'}</div>
      </div>

      <div class="c span-5">
        <div class="h"><span class="t">Sorgenti per tipo</span><span class="m">device e metriche abilitati</span></div>
        <div class="tblwrap"><table class="tbl">
          <thead><tr><th>Tipo</th><th class="num">Device</th><th class="num">Attivi</th><th class="num">Metriche</th><th>Ultima raccolta</th></tr></thead>
          <tbody>
            <tr><td>Web scraping</td><td class="num">${cw.total}</td><td class="num">${cw.on}</td><td class="num">${cw.metsOn}/${cw.mets}</td><td>${esc(st.web_last_run || '—')}</td></tr>
            <tr><td>API SolarEdge</td><td class="num">${ca.total}</td><td class="num">${ca.on}</td><td class="num">—</td><td>${esc(st.api_last_run || '—')}</td></tr>
            <tr><td>Modbus</td><td class="num">${cm.total}</td><td class="num">${cm.on}</td><td class="num">${cm.metsOn}/${cm.mets}</td><td>${esc(st.last_update_formatted || '—')}</td></tr>
            <tr><td>GME · PUN</td><td class="num">—</td><td class="num">${gmeOn ? 'on' : 'off'}</td><td class="num">—</td><td>${esc(st.gme_last_run || '—')}</td></tr>
            <tr><td>Bolletta · ARERA</td><td class="num">—</td><td class="num">${bollettaOn ? 'on' : 'off'}</td><td class="num">—</td><td>${esc(st.bolletta_last_run || '—')}</td></tr>
          </tbody>
        </table>
        <div class="note">API SolarEdge: ogni endpoint è un dataset fisso, non ha metriche selezionabili. GME e Bolletta non hanno device: sono flussi a dataset fisso.</div>
        </div>
      </div>
    </div>`;

  const term = $('#overr');
  if (term) term.scrollTop = term.scrollHeight;
  window.scrollTo(0, keepY);
}

function pretty(k) {
  return String(k).replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}

async function viewSourceDetail(type, id) {
  const v = $('#view');
  v.innerHTML = '<div class="empty">caricamento…</div>';
  try {
    const all = await api('/api/sources?type=' + type);
    const d = all[id];
    if (!d) { v.innerHTML = `<div class="empty">sorgente “${esc(id)}” non trovata</div>`; return; }
    const label = d.device_name || d.category || id;
    const meta = d.device_type || d.category || d.data_type || '';
    const mets = d.measurements || {};
    const onCount = Object.values(mets).filter(m => m && m.enabled).length;
    const metricKind = type === 'web' ? 'webmetric' : type === 'modbus' ? 'modbusmetric' : null;
    const infoRows = [
      ['ID', id], ['Categoria', d.category], ['Tipo', d.device_type || d.data_type],
      ['Endpoint', d.endpoint ? `${d.method || 'GET'} ${d.endpoint}` : null],
      ['Formato', d.data_format], ['Range', d.date_range],
      ['Serial', d.requires_serial === true ? 'richiesto' : d.requires_serial === false ? 'no' : null],
    ].filter(([, x]) => x);
    v.innerHTML = `
      <div class="pagehead">
        <a class="btn" href="#/sources">← Sorgenti</a>
        <div><h1>${esc(label)}</h1><p>${esc(type)} · ${esc(meta)}</p></div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:.5rem"><span class="m">${d.enabled ? 'attiva' : 'off'}</span>${toggleHtml(type, id, d.enabled)}</div>
      </div>
      <div class="mets">
        <div class="m b"><div class="t">Stato</div><div class="v" style="font-size:1rem">${d.enabled ? 'attiva' : 'off'}</div></div>
        <div class="m a"><div class="t">Metriche</div><div class="v" style="font-size:1rem">${onCount}<small>/${Object.keys(mets).length}</small></div></div>
        <div class="m c"><div class="t">Categoria</div><div class="v" style="font-size:.94rem">${esc(d.category || '—')}</div></div>
        <div class="m d"><div class="t">Tipo</div><div class="v" style="font-size:.94rem">${esc(d.device_type || d.data_type || '—')}</div></div>
      </div>
      ${d.description ? `<div class="c" style="margin-bottom:var(--gap)"><div class="h"><span class="t">Descrizione</span></div><p style="margin:0;font-size:.85rem;color:var(--mut);line-height:1.6">${esc(d.description)}</p></div>` : ''}
      <div class="split">
        <div class="c"><div class="h"><span class="t">Metriche</span><span class="m">${Object.keys(mets).length}</span></div>
          <div class="slist">${Object.entries(mets).map(([k, m]) => `
            <div class="srow" style="cursor:default">
              <span class="hd ${m.enabled ? 'ok' : 'wr'}"></span>
              <span class="nm">${esc(m.description || pretty(k))}<span class="mt" style="margin-left:.5rem">${esc(m.unit || m.field_name || '')}</span></span>
              ${metricKind ? `<span class="sw ${m.enabled ? 'on' : ''}" data-toggle="${metricKind}" data-id="${esc(id)}" data-metric="${esc(k)}"><i></i></span>` : `<span class="mt">${m.enabled ? 'on' : 'off'}</span>`}
            </div>`).join('') || '<div class="empty">nessuna metrica</div>'}</div>
        </div>
        <div class="c"><div class="h"><span class="t">Info</span></div>
          <div class="slist">${infoRows.map(([k, x]) => `<div class="row"><span class="tm">${esc(k)}</span><span class="nm" style="text-align:right;font-size:.8rem">${esc(x)}</span></div>`).join('')}</div>
        </div>
      </div>
      <div class="c" style="margin-top:var(--gap)"><div class="h"><span class="t">Log recenti</span><span class="m">match su id/name</span></div><div class="term" id="srclog" style="height:14rem"><div class="empty">caricamento…</div></div></div>`;
    if (metricKind) bindToggles(v);
    const logs = await api('/api/loop/logs?flow=all&limit=2000');
    const needle = [id, label].map(x => String(x).toLowerCase());
    const hits = (logs.logs || []).filter(l => needle.some(n => String(l.message || l.msg || '').toLowerCase().includes(n))).slice(-40);
    const el = $('#srclog');
    el.innerHTML = hits.map(logLine).join('') || '<div class="empty">nessuna riga recente per questa sorgente</div>';
    el.scrollTop = el.scrollHeight;
  } catch (e) { v.innerHTML = `<div class="empty">errore: ${esc(e.message)}</div>`; }
}

const STATE = { srcTab: 'web' };
const SRC_TABS = [
  ['web', 'Web scraping'], ['api', 'API endpoints'], ['modbus', 'Modbus'],
  ['gme', 'GME'], ['bolletta', 'Bolletta'],
];

const FLOW_INFO = {
  gme: {
    title: 'GME - mercato elettrico',
    badge: 'bucket GME',
    what: "Scarica i prezzi del mercato del giorno prima dal GME e li scrive nel bucket GME.",
    collects: [
      'Prezzi orari e PUN (gme_prices, pun_mwh, in euro/MWh)',
      'Media mensile del PUN (gme_monthly_avg)',
    ],
    source: 'API GME - credenziali GME_USERNAME / GME_PASSWORD',
    destination: 'InfluxDB - GME',
    bucket: 'GME',
    flow: 'gme',
  },
  bolletta: {
    title: 'Bolletta - ARERA e GO',
    badge: 'bucket Bolletta',
    what: "Legge i bonus sociali ARERA, l'indice GO del mese e i parametri di rete, li valida e li scrive nel bucket Bolletta.",
    collects: [
      'Bonus per 1-2, 3-4 e oltre 4 componenti (b12, b34, b4plus)',
      'Indice GO del mese in euro/kWh',
      'Rete: componente variabile, fissa e di potenza',
      'Stato della validazione (ok / errore)',
    ],
    source: 'Pagine ARERA + API GME (segmento GO)',
    destination: 'InfluxDB - Bolletta',
    bucket: 'Bolletta',
    flow: 'bolletta',
  },
};

const DEVICE_INFO = {
  web: {
    title: 'Web scraping - portale SolarEdge',
    badge: 'bucket Solaredge - Type: web',
    what: 'Legge i dati dei device dal portale SolarEdge, senza consumare i crediti della Monitoring API.',
    collects: [
      'Produzione e consumo per inverter, meter e optimizer',
      'Energia, potenza, tensione, corrente e frequenza',
      'Solo le metriche abilitate nei singoli device',
    ],
    destination: 'InfluxDB - Solaredge (Type: web)',
  },
  api: {
    title: 'API SolarEdge - Monitoring API',
    badge: 'bucket Solaredge - Type: api',
    what: "Interroga la Monitoring API ufficiale su un insieme fisso di endpoint; ogni endpoint e' un dataset, non ha metriche.",
    collects: [
      "Dettagli dell'impianto (site_details)",
      'Energia a quarti d\'ora (site_energy_details)',
      'Gli altri endpoint sono definiti ma disabilitati',
    ],
    destination: 'InfluxDB - Solaredge (Type: api)',
  },
  modbus: {
    title: 'Modbus - inverter in rete locale',
    badge: 'bucket Solaredge_Realtime - Type: realtime',
    what: "Legge i registri dell'inverter via Modbus TCP a ogni ciclo del loop.",
    collects: [
      'Produzione e consumo in tempo reale',
      'Batteria, meter, stringhe e optimizer',
      'Un punto per metrica abilitata, a ogni ciclo',
    ],
    destination: 'InfluxDB - Solaredge_Realtime (Type: realtime)',
  },
};

function infoCard(o) {
  return `<div class="c">
    <div class="h"><span class="t">${esc(o.title)}</span><span class="m">${esc(o.badge || '')}</span></div>
    <p class="lead">${esc(o.what)}</p>
    <div class="split">
      <div>
        <div class="hd2">Cosa raccoglie</div>
        <ul class="ticks">${o.collects.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
        <div class="row"><span class="tm">Sorgente</span><span class="nm">${esc(o.source)}</span></div>
        <div class="row"><span class="tm">Destinazione</span><span class="nm">${esc(o.destination)}</span></div>
        <div class="row"><span class="tm">Cadenza</span><span class="nm">${esc(o.cadence || '-')}</span></div>
      </div>
      <div>
        <div class="hd2">Stato</div>
        ${(o.rows || []).map(([k, val]) => `<div class="row"><span class="tm">${esc(k)}</span><span class="nm">${val}</span></div>`).join('')}
        ${o.extra || ''}
      </div>
    </div>
  </div>`;
}

async function viewFlowInfo(kind) {
  const body = $('#srcbody');
  const token = VIEW_TOKEN;
  const info = FLOW_INFO[kind];
  const res = await Promise.allSettled([api('/api/loop/status'), api('/api/loop/logs?flow=' + kind + '&limit=200')]);
  const status = res[0].status === 'fulfilled' ? res[0].value : {};
  const st = status.stats || {};
  const fe = status.flows_enabled || {};
  const iv = status.intervals_seconds || {};
  const on = kind === 'gme' ? !!fe.gme : !!fe.bolletta;
  const stats = st[kind + '_stats'] || {};
  const nextRel = st[kind + '_next_at'] ? rel(st[kind + '_next_at']) : '';
  const rows = res[1].status === 'fulfilled' ? (res[1].value.logs || []) : [];
  if (token !== VIEW_TOKEN || !body.isConnected) return;

  body.innerHTML = infoCard({
    ...info,
    cadence: every(iv[kind]),
    rows: [
      ['Abilitato', on ? 'si' : 'no'],
      ['Ultimo run', esc(st[kind + '_last_run'] || '-')],
      ['Prossimo', esc(st[kind + '_next_run'] || '-') + (nextRel ? ' - ' + nextRel : '')],
      ['Eseguiti / falliti', `${stats.executed || 0} / ${stats.failed || 0}`],
    ],
    extra: kind === 'gme'
      ? `<div class="row"><span class="tm">Attivo</span><span class="nm">${toggleHtml('gme', 'gme', on)}</span></div>`
      : '<div class="note">Si abilita in .env con BOLLETTA_ENABLED.</div>',
  }) + `
    <div class="c">
      <div class="h"><span class="t">Log recenti</span><span class="m">flow ${esc(kind)}</span></div>
      <div class="term" id="flowlog" style="height:14rem">${rows.slice(-60).map(logLine).join('') || '<div class="empty">nessuna riga nel buffer</div>'}</div>
    </div>`;

  if (kind === 'gme') bindToggles(body);
  const el = $('#flowlog');
  if (el) el.scrollTop = el.scrollHeight;
}

async function viewSources() {
  const v = $('#view');
  v.innerHTML = `<div class="pagehead"><div><h1>Sorgenti</h1><p>Device, endpoint e flussi a dataset fisso</p></div></div>
    <div class="tabs">${SRC_TABS.map(([k, l]) => `<div class="tab ${STATE.srcTab === k ? 'on' : ''}" data-tab="${k}">${l}</div>`).join('')}</div>
    <div id="srcbody"><div class="empty">caricamento...</div></div>`;
  v.querySelectorAll('[data-tab]').forEach(el => el.addEventListener('click', () => { STATE.srcTab = el.dataset.tab; viewSources(); }));

  if (STATE.srcTab === 'gme' || STATE.srcTab === 'bolletta') return viewFlowInfo(STATE.srcTab);

  const body = $('#srcbody');
  const token = VIEW_TOKEN;
  const kind = STATE.srcTab;
  try {
    const [srcRes, cfgRes, stRes] = await Promise.allSettled([
      api('/api/sources?type=' + kind), api('/api/config'), api('/api/loop/status'),
    ]);
    if (token !== VIEW_TOKEN || !body.isConnected) return;
    if (srcRes.status !== 'fulfilled') throw new Error(srcRes.reason && srcRes.reason.message || 'lettura sorgenti fallita');

    const data = srcRes.value || {};
    const cfg = cfgRes.status === 'fulfilled' ? cfgRes.value : {};
    const status = stRes.status === 'fulfilled' ? stRes.value : {};
    const st = status.stats || {};
    const iv = status.intervals_seconds || {};

    const list = Object.entries(data);
    const on = list.filter(([, d]) => d.enabled).length;
    const mets = list.reduce((a, [, d]) => a + Object.keys(d.measurements || {}).length, 0);
    const metsOn = list.reduce((a, [, d]) => a + Object.values(d.measurements || {}).filter(m => m.enabled).length, 0);

    const modbus = (cfg.solaredge && cfg.solaredge.modbus) || {};
    const site = (cfg.solaredge && cfg.solaredge.api && cfg.solaredge.api.site_id) || (cfg.global && cfg.global.site_id) || '-';
    const info = DEVICE_INFO[kind];
    const source = kind === 'web'
      ? 'Portale SolarEdge (accesso via Cognito, cookie di sessione)'
      : kind === 'api'
        ? `Monitoring API SolarEdge - sito ${site} (API key)`
        : `Inverter ${modbus.host || '-'}:${modbus.port || '-'} (Modbus TCP)`;
    const last = kind === 'modbus' ? (st.last_update_formatted || '-') : (st[kind + '_last_run'] || '-');
    const next = kind === 'modbus' ? 'continuo' : (st[kind + '_next_run'] || '-');
    const nextRel = st[kind + '_next_at'] ? rel(st[kind + '_next_at']) : '';

    const rows = list.map(([id, d]) => {
      const isApi = kind === 'api';
      const name = isApi ? id : (d.device_name || d.description || d.category || id);
      const meta = isApi ? (d.category || '') : (d.category || d.device_type || d.method || '');
      const desc = isApi ? String(d.description || '') : '';
      return `<div class="srow" data-src="${kind}" data-id="${esc(id)}"${desc ? ` title="${esc(desc)}"` : ''}><span class="hd ${d.enabled ? 'ok' : 'wr'}"></span><span class="nm"><span class="nm-t">${esc(name)}<span class="mt" style="margin-left:.5rem">${esc(meta)}</span></span>${desc ? `<span class="desc">${esc(desc)}</span>` : ''}</span>${isApi ? '' : `<span class="mt">${id}</span>`}${toggleHtml(kind, id, d.enabled)}<span class="mt" style="color:var(--dim)">></span></div>`;
    }).join('');

    body.innerHTML = infoCard({
      ...info,
      source,
      cadence: every(iv[kind === 'modbus' ? 'realtime' : kind]),
      rows: kind === 'api'
        ? [
            ['Endpoint attivi', `${on}/${list.length}`],
            ['Ultimo run', esc(last)],
            ['Prossimo', esc(next) + (nextRel ? ' - ' + nextRel : '')],
          ]
        : [
            ['Device attivi', `${on}/${list.length}`],
            ['Metriche attive', `${metsOn}/${mets}`],
            ['Ultimo run', esc(last)],
            ['Prossimo', esc(next) + (nextRel ? ' - ' + nextRel : '')],
          ],
    }) + `
      <div class="c">
        <div class="h"><span class="t">${kind === 'api' ? 'Endpoint' : kind === 'modbus' ? 'Device Modbus' : 'Device'}</span><span class="m">${on}/${list.length} attivi</span></div>
        <div id="srclist" class="slist">${rows || '<div class="empty">nessuna voce</div>'}</div>
      </div>`;

    bindToggles(v);
    v.querySelectorAll('[data-src]').forEach(el => el.addEventListener('click', () => {
      location.hash = `#/source/${el.dataset.src}/${encodeURIComponent(el.dataset.id)}`;
    }));
  } catch (e) {
    if (body.isConnected) body.innerHTML = `<div class="c"><div class="empty">errore: ${esc(e.message)}</div></div>`;
  }
}

let loopTimer = null;
const LOOP_STATE = { runFlow: 'all' };

function loopFlowCard(f, st, fe, iv) {
  const s = st[f.stats] || {};
  const off = (f.key === 'gme' || f.key === 'bolletta') && fe[f.key] === false;
  const last = f.key === 'realtime' ? (st.last_update_formatted || '-') : (st[f.key + '_last_run'] || '-');
  const next = f.key === 'realtime' ? 'continuo' : (st[f.key + '_next_run'] || '-');
  const nextRel = st[f.next] ? rel(st[f.next]) : '';
  return `<div class="fcard ${off ? 'off' : ''}">
    <div class="fh"><span class="hd ${off ? 'off' : 'ok'}"></span><b>${esc(f.label)}</b><span class="tag ${flowTag(f.key)}">${every(iv[f.key])}</span></div>
    <div class="fsub">${esc(f.note)}</div>
    <div class="fgrid">
      <div><span>Ultimo</span><b>${esc(last)}</b></div>
      <div><span>Prossimo</span><b>${esc(next)}${nextRel ? ` <i>${nextRel}</i>` : ''}</b></div>
      <div><span>Eseguiti</span><b>${s.executed || 0}</b></div>
      <div><span>Falliti</span><b class="${s.failed ? 'bad' : ''}">${s.failed || 0}</b></div>
    </div>
  </div>`;
}

async function viewLoop() {
  const v = $('#view');
  const keepY = window.scrollY;
  const token = VIEW_TOKEN;
  try {
    const [status, logs] = await Promise.all([api('/api/loop/status'), api('/api/loop/logs?flow=all&limit=800')]);
    if (token !== VIEW_TOKEN) return;
    const st = status.stats || {};
    const fe = status.flows_enabled || {};
    const iv = status.intervals_seconds || {};
    const allRuns = extractRuns(logs.logs || []).reverse();
    const runs = LOOP_STATE.runFlow === 'all' ? allRuns : allRuns.filter(r => r.flow === LOOP_STATE.runFlow);
    const totals = ['realtime_stats', 'web_stats', 'api_stats', 'gme_stats', 'bolletta_stats'].reduce((a, k) => {
      const f = st[k] || {};
      a.run += f.executed || 0; a.ok += f.success || 0; a.fail += f.failed || 0;
      return a;
    }, { run: 0, ok: 0, fail: 0 });

    v.innerHTML = `
      <div class="pagehead">
        <div><h1>Loop</h1><p>Un solo processo esegue i flussi a turno, ognuno alla sua cadenza.</p></div>
        <div style="margin-left:auto;display:flex;gap:.5rem">
          <button class="btn ${status.loop_mode ? 'coral' : 'mint'}" id="loopToggle">${status.loop_mode ? 'Stop' : 'Start'}</button>
          <button class="btn" id="clearLogs">Pulisci log</button>
        </div>
      </div>
      <div class="kpis">
        <div class="kpi info"><div class="t">Stato</div><div class="v">${status.loop_mode ? 'on' : 'off'}</div><div class="s">${status.loop_mode ? 'loop in esecuzione' : 'loop fermo'}</div></div>
        <div class="kpi"><div class="t">Uptime</div><div class="v" style="font-size:1.5rem">${esc(st.uptime_formatted || '-')}</div><div class="s">dall'avvio del processo</div></div>
        <div class="kpi"><div class="t">Ultimo ciclo</div><div class="v" style="font-size:1.5rem">${esc(st.last_update_formatted || '-')}</div><div class="s">ultima iterazione</div></div>
        <div class="kpi ok"><div class="t">Run</div><div class="v">${totals.run}</div><div class="s">${totals.ok} ok</div></div>
        <div class="kpi ${totals.fail ? 'bad' : ''}"><div class="t">Falliti</div><div class="v">${totals.fail}</div><div class="s">${totals.fail ? 'da controllare nei log' : 'nessuno'}</div></div>
      </div>

      <div class="c">
        <div class="h"><span class="t">Flussi</span><span class="m">cosa gira, ogni quanto, con che esito</span></div>
        <div class="flowcards">${FLOWS.map(f => loopFlowCard(f, st, fe, iv)).join('')}</div>
        <div class="note">Il loop e' sequenziale: ogni flusso parte quando scade il suo intervallo. Un fallimento non ferma gli altri; Stop ferma tutto fino al prossimo Start.</div>
      </div>

      <div class="split-even">
        <div class="c">
          <div class="h"><span class="t">Ultimi run</span><span class="m">${runs.length} nel buffer</span></div>
          <div class="filters">${['all', 'realtime', 'web', 'api', 'gme', 'bolletta'].map(k => `<button class="chip ${LOOP_STATE.runFlow === k ? 'on' : ''}" data-runflow="${k}">${k}</button>`).join('')}</div>
          <div class="slist">${runs.slice(0, 20).map(r => `<div class="srow" data-run="${esc(r.flow)}" data-start="${esc(r.start)}"><span class="hd ${r.ok ? 'ok' : 'er'}"></span><span class="tag ${flowTag(r.flow)}">${esc(r.flow.slice(0,8).toUpperCase())}</span><span class="nm">${esc(r.start)} - ${esc(r.end)}</span><span class="mt">${fmtDur(r.start, r.end)}</span><span class="mt" style="color:var(--dim)">></span></div>`).join('') || '<div class="empty">nessun run di questo flusso nel buffer</div>'}</div>
        </div>
        <div class="c">
          <div class="h"><span class="t">Log live</span><span class="m">ultimi 200</span></div>
          <div class="term" id="loopterm" style="height:26rem">${(logs.logs || []).slice(-200).map(logLine).join('') || '<div class="empty">nessun log</div>'}</div>
        </div>
      </div>`;

    $('#loopToggle').addEventListener('click', async () => {
      await api(status.loop_mode ? '/api/loop/stop' : '/api/loop/start', { method: 'POST' });
      toast(status.loop_mode ? 'Loop fermato' : 'Loop avviato');
      viewLoop();
    });
    $('#clearLogs').addEventListener('click', async () => {
      await api('/api/loop/logs/clear', { method: 'POST' });
      viewLoop();
    });
    v.querySelectorAll('[data-runflow]').forEach(el => el.addEventListener('click', () => {
      LOOP_STATE.runFlow = el.dataset.runflow;
      viewLoop();
    }));
    v.querySelectorAll('[data-run]').forEach(el => el.addEventListener('click', () => {
      location.hash = `#/loop/run/${encodeURIComponent(el.dataset.run)}/${encodeURIComponent(el.dataset.start)}`;
    }));
    const term = $('#loopterm');
    term.scrollTop = term.scrollHeight;
    window.scrollTo(0, keepY);
  } catch (e) {
    v.innerHTML = `<div class="empty">errore: ${esc(e.message)}</div>`;
  }
}

const LOGS_STATE = { flow: 'all', q: '' };
let LOGCACHE = [];

function renderLogLines() {
  const q = LOGS_STATE.q.toLowerCase();
  const rows = LOGCACHE.filter(l => !q || String(l.message || l.msg || '').toLowerCase().includes(q));
  const el = $('#logterm');
  if (!el) return;
  const cnt = $('#logcount');
  if (cnt) cnt.textContent = rows.length;
  el.innerHTML = rows.map(logLine).join('') || '<div class="empty">nessun log</div>';
  el.scrollTop = el.scrollHeight;
}

async function loadLogs() {
  const d = await api('/api/loop/logs?flow=' + LOGS_STATE.flow + '&limit=2000');
  if (!$('#logterm')) return;
  LOGCACHE = d.logs || [];
  renderLogLines();
}

async function viewLogs() {
  const v = $('#view');
  v.innerHTML = `<div class="pagehead"><div><h1>Logs</h1><p>buffer del collector · <span id="logcount">${LOGCACHE.length}</span> righe</p></div></div>
    <div class="filters" id="logflows">${['all','realtime','web','api','gme','bolletta'].map(f => `<button class="chip ${LOGS_STATE.flow === f ? 'on' : ''}" data-flow="${f}">${f}</button>`).join('')}
      <input id="logq" placeholder="cerca nel messaggio…" value="${esc(LOGS_STATE.q)}" class="search">
    </div>
    <div class="c"><div class="term" id="logterm" style="height:calc(100vh - 300px)"><div class="empty">caricamento…</div></div></div>`;
  v.querySelectorAll('[data-flow]').forEach(el => el.addEventListener('click', async () => {
    LOGS_STATE.flow = el.dataset.flow;
    v.querySelectorAll('[data-flow]').forEach(x => x.classList.toggle('on', x.dataset.flow === LOGS_STATE.flow));
    await loadLogs();
  }));
  let t = null;
  $('#logq').addEventListener('input', (e) => {
    LOGS_STATE.q = e.target.value;
    clearTimeout(t);
    t = setTimeout(renderLogLines, 120);
  });
  try { await loadLogs(); } catch (e) { $('#logterm').innerHTML = `<div class="empty">errore: ${esc(e.message)}</div>`; }
}

const CFG_FILES = [
  ['main', 'main.yaml'],
  ['web_endpoints', 'web_endpoints.yaml'],
  ['api_endpoints', 'api_endpoints.yaml'],
  ['modbus_endpoints', 'modbus_endpoints.yaml'],
  ['env', '.env'],
];
const CFG_STATE = { file: 'main' };

async function loadCfgFile() {
  const msg = $('#cfgMsg');
  const ta = $('#cfg');
  msg.textContent = 'caricamento...';
  try {
    const d = await api('/api/config/yaml?file=' + CFG_STATE.file);
    if (!ta.isConnected) return;
    ta.value = d && d.content != null ? d.content : (d || '');
    $('#cfgpath').textContent = (d && d.path) || CFG_STATE.file;
    msg.textContent = '';
  } catch (e) {
    msg.textContent = 'errore: ' + e.message;
  }
}

async function viewConfig() {
  const v = $('#view');
  v.innerHTML = `
    <div class="pagehead">
      <div><h1>Config</h1><p>File di configurazione del collector</p></div>
      <div style="margin-left:auto;display:flex;gap:.5rem">
        <button class="btn" id="reloadCfg">Ricarica</button>
        <button class="btn mint" id="saveCfg">Salva</button>
      </div>
    </div>
    <div class="tabs">${CFG_FILES.map(([k, l]) => `<div class="tab ${CFG_STATE.file === k ? 'on' : ''}" data-file="${k}">${l}</div>`).join('')}</div>
    <div class="c">
      <div class="h"><span class="t" id="cfgpath">-</span><span class="m" id="cfgMsg"></span></div>
      <textarea class="cfg-editor" id="cfg" spellcheck="false"></textarea>
      <div class="note">Il salvataggio riscrive il file: per i YAML commenti e ordine delle chiavi non sono conservati. .env viene scritto cosi' com'e'.</div>
    </div>`;

  v.querySelectorAll('[data-file]').forEach(el => el.addEventListener('click', () => {
    CFG_STATE.file = el.dataset.file;
    v.querySelectorAll('[data-file]').forEach(x => x.classList.toggle('on', x.dataset.file === CFG_STATE.file));
    loadCfgFile();
  }));
  $('#reloadCfg').addEventListener('click', loadCfgFile);
  $('#saveCfg').addEventListener('click', async () => {
    const msg = $('#cfgMsg');
    msg.textContent = 'salvataggio...';
    try {
      await api('/api/config/yaml', { method: 'POST', body: JSON.stringify({ file: CFG_STATE.file, content: $('#cfg').value }) });
      msg.textContent = 'salvato';
      toast('File salvato');
    } catch (e) {
      msg.textContent = 'errore: ' + e.message;
    }
  });
  await loadCfgFile();
}

async function viewUpdates() {
  const v = $('#view');
  v.innerHTML = `<div class="pagehead"><div><h1>Update</h1><p>git · origin/main</p></div>
    <div style="margin-left:auto;display:flex;gap:.5rem"><button class="btn" id="checkUpd">Controlla</button><button class="btn mint" id="runUpd">Aggiorna</button></div></div>
    <div class="c" id="upd"><div class="empty">caricamento…</div></div>
    <div class="m" id="updMsg" style="display:none"></div>`;
  const say = (t) => { const m = $('#updMsg'); m.style.display = 'block'; m.textContent = t; };
  try {
    const s = await api('/api/updates/status');
    $('#upd').innerHTML = `<div class="mets" style="margin:0">
      <div class="m ${s.updates_available ? 'c' : 'b'}"><div class="t">Stato</div><div class="v" style="font-size:.94rem">${s.updates_available ? 'aggiornamenti disponibili' : 'aggiornato'}</div></div>
      <div class="m a"><div class="t">Ultimo check</div><div class="v" style="font-size:.94rem">${esc(s.last_check_str || 'mai')}</div></div>
    </div>`;
  } catch (e) { $('#upd').innerHTML = `<div class="empty">errore: ${esc(e.message)}</div>`; }
  $('#checkUpd').addEventListener('click', async () => {
    say('controllo in corso…');
    try { const r = await api('/api/updates/check'); say(`${r.message} · locale ${r.local_commits} · remoti ${r.remote_commits}`); }
    catch (e) { say('errore: ' + e.message); }
  });
  $('#runUpd').addEventListener('click', async () => {
    if (!confirm("Avviare l'aggiornamento da git?")) return;
    say('aggiornamento in corso…');
    try { const r = await api('/api/updates/run', { method: 'POST' }); say(r.message || 'fatto'); }
    catch (e) { say('errore: ' + e.message); }
  });
}

const VIEWS = { '/': viewOverview, '/sources': viewSources, '/loop': viewLoop, '/logs': viewLogs, '/config': viewConfig, '/updates': viewUpdates };
function route() {
  const seg = (location.hash.replace(/^#/, '') || '/').split('?')[0].split('/').filter(Boolean);
  const page = seg[0] || '';
  const active = page === 'source' ? '/sources' : '/' + page;
  const root = document.getElementById('app');
  root.innerHTML = shell(active);
  VIEW_TOKEN += 1;
  ping();
  clearInterval(loopTimer);
  if (page === 'source') {
    if (seg[1] && seg[2]) viewSourceDetail(seg[1], decodeURIComponent(seg[2]));
    else viewSources();
    return;
  }
  if (page === 'loop' && seg[1] === 'run' && seg[2] && seg[3]) {
    viewRun(decodeURIComponent(seg[2]), decodeURIComponent(seg[3]));
    return;
  }
  const fn = VIEWS['/' + page] || viewOverview;
  fn();
  if (page === '' || page === 'loop') {
    loopTimer = setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      const y = window.scrollY;
      Promise.resolve(fn()).finally(() => window.scrollTo(0, y));
    }, 10000);
  }
}
const PALETTE_ITEMS = [
  ...NAV.map(([p, , l]) => ({ label: l, hint: 'vai', run: () => { location.hash = '#' + p; } })),
  { label: 'Avvia loop', hint: 'azione', run: async () => { await api('/api/loop/start', { method: 'POST' }); toast('Loop avviato'); route(); } },
  { label: 'Ferma loop', hint: 'azione', run: async () => { await api('/api/loop/stop', { method: 'POST' }); toast('Loop fermato'); route(); } },
  { label: 'Pulisci log', hint: 'azione', run: async () => { await api('/api/loop/logs/clear', { method: 'POST' }); toast('Log puliti'); route(); } },
  { label: 'Controlla aggiornamenti', hint: 'azione', run: async () => { const r = await api('/api/updates/check'); toast(r.message); } },
];

let PAL = null;
function palette(open) {
  if (!open) { if (PAL) PAL.remove(); PAL = null; return; }
  if (PAL) return;
  PAL = document.createElement('div');
  PAL.id = 'pal';
  PAL.innerHTML = `<div class="palbox"><input id="palq" placeholder="Vai a… oppure un'azione…"><div id="palitems"></div></div>`;
  document.body.appendChild(PAL);
  PAL.addEventListener('click', (e) => { if (e.target === PAL) palette(false); });
  const input = $('#palq');
  let sel = 0;
  const draw = () => {
    const q = input.value.toLowerCase();
    const items = PALETTE_ITEMS.filter(i => i.label.toLowerCase().includes(q));
    sel = Math.min(sel, Math.max(items.length - 1, 0));
    input._items = items;
    $('#palitems').innerHTML = items.map((i, n) => `<div class="palitem ${n === sel ? 'on' : ''}" data-n="${n}"><span>${esc(i.label)}</span><span class="m">${i.hint}</span></div>`).join('') || '<div class="empty">niente</div>';
    v_all('.palitem').forEach(el => el.addEventListener('click', () => { const it = items[+el.dataset.n]; palette(false); it.run(); }));
  };
  const v_all = (sel2) => document.querySelectorAll(sel2);
  input.addEventListener('input', () => { sel = 0; draw(); });
  input.addEventListener('keydown', (e) => {
    const items = input._items || [];
    if (e.key === 'Escape') palette(false);
    if (e.key === 'ArrowDown') { sel = Math.min(sel + 1, items.length - 1); draw(); e.preventDefault(); }
    if (e.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); draw(); e.preventDefault(); }
    if (e.key === 'Enter' && items[sel]) { palette(false); items[sel].run(); }
  });
  draw();
  input.focus();
}

window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); palette(!PAL); }
});
document.addEventListener('click', (e) => { if (e.target.id === 'palBtn') palette(true); });

tick(); setInterval(tick, 1000);
window.addEventListener('hashchange', route);
route();
