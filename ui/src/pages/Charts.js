import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceArea, BarChart
} from 'recharts';

// ── Helpers ───────────────────────────────────────────────────

const MODE_COLORS = {
  MANUAL:   'rgba(168,85,247,0.45)',
  SCHEDULE: 'rgba(14,165,233,0.45)',
  PV:       'rgba(34,197,94,0.45)',
  IDLE:     'rgba(100,116,139,0.30)',
  ERROR:    'rgba(239,68,68,0.50)',
  NO_COMM:  'rgba(239,68,68,0.50)',
};

const MODE_BORDER = {
  MANUAL:   '#a855f7',
  SCHEDULE: '#0ea5e9',
  PV:       '#22c55e',
  IDLE:     '#64748b',
  ERROR:    '#ef4444',
  NO_COMM:  '#ef4444',
};

const MODE_LABELS = {
  MANUAL:   'Ręczny',
  SCHEDULE: 'Harmonogram',
  PV:       'PV',
  IDLE:     'Czuwanie',
  ERROR:    'Błąd',
  NO_COMM:  'Brak komun.',
};

const LINE_COLORS = {
  temp_current: '#38bdf8',
  temp_target:  '#f97316',
  power_w:      '#ef4444',
  pv_power_w:   '#22c55e',
};

const RANGES = [
  { id: '3h',  label: '3h',    hours: 3 },
  { id: '6h',  label: '6h',    hours: 6 },
  { id: '24h', label: '24h',   hours: 24 },
  { id: '3d',  label: '3 dni', hours: 72 },
  { id: '7d',  label: '7 dni', hours: 168 },
];

const LAYERS = [
  { id: 'temp_current', label: 'Temp. aktualna',  color: LINE_COLORS.temp_current, unit: '°C', yAxis: 'left' },
  { id: 'temp_target',  label: 'Temp. docelowa',  color: LINE_COLORS.temp_target,  unit: '°C', yAxis: 'left', dashed: true },
  { id: 'power_w',      label: 'Moc grzania (zadana)', color: LINE_COLORS.power_w, unit: 'W',  yAxis: 'right' },
  { id: 'tuya_power_w', label: 'Moc rzeczywista (Tuya)', color: '#22d3ee',        unit: 'W',  yAxis: 'right' },
  { id: 'pv_power_w',   label: 'Produkcja PV',    color: LINE_COLORS.pv_power_w,   unit: 'W',  yAxis: 'right' },
  { id: 'draw_events',  label: 'Sesje poboru wody (eksperymentalne)', color: '#eab308', unit: '', yAxis: 'left' },
  { id: 'pump_events',  label: 'Praca pompy cyrkulacyjnej', color: '#a855f7', unit: '', yAxis: 'left' },
];

const DRAW_EVENT_COLORS = {
  session:      'rgba(234,179,8,0.35)',
  subthreshold: 'rgba(148,163,184,0.25)',
};

const DRAW_EVENT_BORDER = {
  session:      '#eab308',
  subthreshold: '#94a3b8',
};

const ENERGY_RANGES = [
  { id: '7d',  label: '7 dni',  days: 7 },
  { id: '14d', label: '14 dni', days: 14 },
  { id: '30d', label: '30 dni', days: 30 },
];

function fmt(ts, hours) {
  if (!ts) return '';
  const d = new Date(ts);
  if (hours <= 24) return d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString('pl-PL', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function fmtFull(ts) {
  if (!ts) return '';
  return new Date(ts).toLocaleString('pl-PL', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

function fmtDay(day) {
  if (!day) return '';
  const d = new Date(day + 'T00:00:00');
  return d.toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit' });
}

function buildModeSegments(data) {
  if (!data.length) return [];
  const segments = [];
  let cur = { mode: data[0].mode, start: data[0].ts };
  for (let i = 1; i < data.length; i++) {
    if (data[i].mode !== cur.mode) {
      segments.push({ ...cur, end: data[i].ts });
      cur = { mode: data[i].mode, start: data[i].ts };
    }
  }
  segments.push({ ...cur, end: data[data.length - 1].ts });
  return segments;
}

// Dopina do każdej próbki boiler_history najbliższy w czasie odczyt Tuya
// (dwa niezależne, niesynchronizowane szeregi czasowe) — tolerancja 5 min,
// dalej nie łączy (traktuje jako brak danych w tym momencie).
function attachTuyaPower(rows, tuyaRows) {
  if (!tuyaRows.length) return rows;
  const TOLERANCE_MS = 5 * 60 * 1000;
  let ti = 0;
  return rows.map(r => {
    const rt = new Date(r.ts).getTime();
    while (
      ti < tuyaRows.length - 1 &&
      Math.abs(new Date(tuyaRows[ti + 1].ts).getTime() - rt) <=
      Math.abs(new Date(tuyaRows[ti].ts).getTime() - rt)
    ) {
      ti++;
    }
    const closest = tuyaRows[ti];
    const diffMs = Math.abs(new Date(closest.ts).getTime() - rt);
    return { ...r, tuya_power_w: diffMs <= TOLERANCE_MS ? closest.power_w : null };
  });
}

// Oś X wykresu jest kategoryczna (pozycjonuje punkty po dokładnym dopasowaniu
// wartości ts z `chartData`). ReferenceArea dla zdarzeń z INNYCH tabel
// (draw_events, pump_history) ma własne znaczniki czasu, które nigdy nie
// trafiają dokładnie w próbki boiler_history — bez tego dopasowania
// Recharts po cichu nie renderuje takiego obszaru wcale. Zwraca najbliższy
// istniejący w chartData znacznik czasu (gwarantuje trafienie w kategorię).
function snapToNearestTs(targetIso, sortedData) {
  if (!targetIso || !sortedData.length) return targetIso;
  const target = new Date(targetIso).getTime();
  let lo = 0, hi = sortedData.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (new Date(sortedData[mid].ts).getTime() < target) lo = mid + 1;
    else hi = mid;
  }
  let best = lo;
  if (lo > 0) {
    const diffLo = Math.abs(new Date(sortedData[lo].ts).getTime() - target);
    const diffPrev = Math.abs(new Date(sortedData[lo - 1].ts).getTime() - target);
    if (diffPrev < diffLo) best = lo - 1;
  }
  return sortedData[best].ts;
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '10px 14px', fontSize: 12,
      boxShadow: '0 8px 24px rgba(0,0,0,0.4)', minWidth: 180,
    }}>
      <div style={{ color: 'var(--text3)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>
        {fmtFull(label)}
      </div>
      {payload.map(p => (
        <div key={p.dataKey} style={{
          display: 'flex', justifyContent: 'space-between', gap: 16,
          color: p.color, marginBottom: 3,
        }}>
          <span>{p.name}</span>
          <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
            {p.value != null ? p.value.toFixed(1) : '—'}{p.unit}
          </span>
        </div>
      ))}
      {d?.mode && (
        <div style={{
          marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--border)',
          color: MODE_BORDER[d.mode] || 'var(--text3)', fontSize: 11,
        }}>
          {MODE_LABELS[d.mode] || d.mode}
        </div>
      )}
    </div>
  );
}

function EnergyTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '10px 14px', fontSize: 12,
      boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
    }}>
      <div style={{ color: 'var(--text3)', marginBottom: 6 }}>{label}</div>
      <div style={{ color: '#f59e0b', fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: 16 }}>
        {payload[0]?.value != null ? payload[0].value.toFixed(2) : '—'} kWh
      </div>
    </div>
  );
}

function Card({ children, style }) {
  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 16, padding: 20, boxShadow: 'var(--card-shadow)', ...style,
    }}>
      {children}
    </div>
  );
}

// ── SUB-TAB: Bojler / PV ──────────────────────────────────────

function BoilerChart() {
  const [range, setRange]           = useState('3h');
  const [layers, setLayers]         = useState(['temp_current', 'temp_target']);
  const [showBg, setShowBg]         = useState(true);
  const [data, setData]             = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo]     = useState('');
  const [useCustom, setUseCustom]   = useState(false);
  const [stats, setStats]           = useState(null);
  const [drawEvents, setDrawEvents] = useState([]);
  const [tuyaReadings, setTuyaReadings] = useState([]);
  const [pumpEvents, setPumpEvents] = useState([]);

  const hours = RANGES.find(r => r.id === range)?.hours || 3;

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      let url = useCustom && customFrom && customTo
        ? '/api/history?hours=168'
        : `/api/history?hours=${hours}`;

      const res = await fetch(url, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('boiler_token')}` }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      let raw = await res.json();

      if (useCustom && customFrom && customTo) {
        const from = new Date(customFrom).getTime();
        const to   = new Date(customTo).getTime();
        raw = raw.filter(r => {
          const t = new Date(r.ts).getTime();
          return t >= from && t <= to;
        });
      }

      // Usuń błędne odczyty temp=0
      raw = raw.map(r => ({
        ...r,
        temp_current: (r.temp_current === 0 || r.temp_current == null) ? null : r.temp_current,
      }));
      raw.sort((a, b) => new Date(a.ts) - new Date(b.ts));

      const temps = raw.map(r => r.temp_current).filter(v => v > 0);
      const pvs   = raw.map(r => r.pv_power_w).filter(v => v > 0);
      const modes = {};
      raw.forEach(r => { if (r.mode) modes[r.mode] = (modes[r.mode] || 0) + 1; });
      setStats({
        tempMin:  temps.length ? Math.min(...temps).toFixed(1) : '—',
        tempMax:  temps.length ? Math.max(...temps).toFixed(1) : '—',
        tempAvg:  temps.length ? (temps.reduce((a,b)=>a+b,0)/temps.length).toFixed(1) : '—',
        pvMax:    pvs.length   ? Math.max(...pvs).toFixed(0) : '—',
        pvAvg:    pvs.length   ? (pvs.reduce((a,b)=>a+b,0)/pvs.length).toFixed(0) : '—',
        dominant: Object.entries(modes).sort((a,b)=>b[1]-a[1])[0]?.[0] || '—',
        count:    raw.length,
      });
      setData(raw);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [hours, useCustom, customFrom, customTo]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (useCustom) return;
    const id = setInterval(() => { if (!document.hidden) load(); }, 60000);
    return () => clearInterval(id);
  }, [load, useCustom]);

  const toggleLayer = (id) => {
    setLayers(l => l.includes(id) ? l.filter(x => x !== id) : [...l, id]);
  };

  // Zdarzenia poboru wody — pobierane tylko gdy warstwa aktywna (eksperymentalne, doradcze)
  useEffect(() => {
    if (!layers.includes('draw_events')) { setDrawEvents([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/usage/events?hours=${hours}`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('boiler_token')}` }
        });
        if (!res.ok) return;
        const raw = await res.json();
        if (!cancelled) setDrawEvents(raw);
      } catch { /* nieistotne — warstwa opcjonalna */ }
    })();
    return () => { cancelled = true; };
  }, [layers, hours]);

  // Realna moc z Tuya — pobierana tylko gdy warstwa aktywna, dopinana do
  // najbliższej próbki boiler_history (dwa niezależne szeregi czasowe).
  useEffect(() => {
    if (!layers.includes('tuya_power_w')) { setTuyaReadings([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/tuya/history?hours=${hours}`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('boiler_token')}` }
        });
        if (!res.ok) return;
        const raw = await res.json();
        raw.sort((a, b) => new Date(a.ts) - new Date(b.ts));
        if (!cancelled) setTuyaReadings(raw);
      } catch { /* nieistotne — warstwa opcjonalna */ }
    })();
    return () => { cancelled = true; };
  }, [layers, hours]);

  // Praca pompy cyrkulacyjnej — pobierana tylko gdy warstwa aktywna.
  useEffect(() => {
    if (!layers.includes('pump_events')) { setPumpEvents([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/pump/history?hours=${hours}`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('boiler_token')}` }
        });
        if (!res.ok) return;
        const raw = await res.json();
        if (!cancelled) setPumpEvents(raw);
      } catch { /* nieistotne — warstwa opcjonalna */ }
    })();
    return () => { cancelled = true; };
  }, [layers, hours]);

  const chartData = useMemo(
    () => layers.includes('tuya_power_w') ? attachTuyaPower(data, tuyaReadings) : data,
    [data, tuyaReadings, layers]
  );

  const segments = buildModeSegments(data);
  const activeHours = useCustom && customFrom && customTo
    ? Math.abs(new Date(customTo) - new Date(customFrom)) / 3600000
    : hours;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Controls */}
      <Card style={{ padding: '14px 20px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 4 }}>
            {RANGES.map(r => (
              <button key={r.id} onClick={() => { setRange(r.id); setUseCustom(false); }} style={{
                padding: '6px 14px', borderRadius: 8,
                background: !useCustom && range === r.id ? 'var(--accent)' : 'var(--bg3)',
                color: !useCustom && range === r.id ? '#fff' : 'var(--text2)',
                border: '1px solid var(--border)', cursor: 'pointer',
                fontFamily: 'var(--font-main)', fontWeight: 600, fontSize: 13, transition: 'all 0.15s',
              }}>{r.label}</button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
            <input type="datetime-local" value={customFrom}
              onChange={e => setCustomFrom(e.target.value)}
              style={{ padding: '5px 10px', borderRadius: 8, background: 'var(--bg3)',
                border: '1px solid var(--border)', color: 'var(--text)',
                fontFamily: 'var(--font-mono)', fontSize: 12 }} />
            <span style={{ color: 'var(--text3)', fontSize: 12 }}>→</span>
            <input type="datetime-local" value={customTo}
              onChange={e => setCustomTo(e.target.value)}
              style={{ padding: '5px 10px', borderRadius: 8, background: 'var(--bg3)',
                border: '1px solid var(--border)', color: 'var(--text)',
                fontFamily: 'var(--font-mono)', fontSize: 12 }} />
            <button onClick={() => setUseCustom(true)} style={{
              padding: '5px 12px', borderRadius: 8,
              background: useCustom ? 'var(--accent)' : 'var(--bg3)',
              color: useCustom ? '#fff' : 'var(--text2)',
              border: '1px solid var(--border)', cursor: 'pointer',
              fontFamily: 'var(--font-main)', fontWeight: 600, fontSize: 12,
            }}>Zastosuj</button>
          </div>
          <button onClick={load} style={{
            padding: '6px 12px', borderRadius: 8,
            background: 'var(--bg3)', border: '1px solid var(--border)',
            color: 'var(--text2)', cursor: 'pointer', fontSize: 14,
          }}>↺</button>
        </div>
      </Card>

      {/* Layer toggles */}
      <Card style={{ padding: '12px 20px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text3)',
            textTransform: 'uppercase', letterSpacing: '0.08em', marginRight: 4 }}>
            Warstwy:
          </span>
          {LAYERS.map(l => (
            <button key={l.id} onClick={() => toggleLayer(l.id)} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '5px 12px', borderRadius: 20,
              background: layers.includes(l.id) ? `${l.color}33` : 'var(--bg3)',
              border: `2px solid ${layers.includes(l.id) ? l.color : 'var(--border)'}`,
              color: layers.includes(l.id) ? l.color : 'var(--text3)',
              cursor: 'pointer', fontFamily: 'var(--font-main)',
              fontSize: 12, fontWeight: 600, transition: 'all 0.15s',
            }}>
              <div style={{
                width: 10, height: 10, borderRadius: '50%',
                background: l.color, opacity: layers.includes(l.id) ? 1 : 0.3,
              }} />
              {l.label}
            </button>
          ))}
          <div style={{ marginLeft: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <button onClick={() => setShowBg(v => !v)} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '5px 12px', borderRadius: 20,
              background: showBg ? 'rgba(100,116,139,0.30)' : 'var(--bg3)',
              border: `2px solid ${showBg ? 'var(--text3)' : 'var(--border)'}`,
              color: showBg ? 'var(--text2)' : 'var(--text3)',
              cursor: 'pointer', fontFamily: 'var(--font-main)',
              fontSize: 12, fontWeight: 600, transition: 'all 0.15s',
            }}>
              <div style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--text3)', opacity: showBg ? 1 : 0.3 }} />
              Tryby sterowania
            </button>
          </div>
        </div>
      </Card>

      {/* Stats */}
      {stats && !loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10 }}>
          {[
            { label: 'Temp. min',   value: `${stats.tempMin}°C`, color: 'var(--teal, #0ea5e9)' },
            { label: 'Temp. max',   value: `${stats.tempMax}°C`, color: 'var(--orange)' },
            { label: 'Temp. śred.', value: `${stats.tempAvg}°C`, color: 'var(--accent)' },
            { label: 'PV max',      value: `${stats.pvMax}W`,    color: 'var(--green)' },
            { label: 'PV śred.',    value: `${stats.pvAvg}W`,    color: 'var(--green)' },
            { label: 'Dominujący',  value: MODE_LABELS[stats.dominant] || stats.dominant, color: MODE_BORDER[stats.dominant] || 'var(--text2)' },
            { label: 'Próbek',      value: stats.count,          color: 'var(--text2)' },
          ].map(s => (
            <div key={s.label} style={{
              background: 'var(--bg2)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '10px 14px',
            }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)',
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                {s.label}
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: s.color,
                fontFamily: 'var(--font-mono)' }}>
                {s.value}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Chart */}
      <Card style={{ padding: '16px 8px 8px 8px' }}>
        {loading && (
          <div style={{ height: 400, display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--text3)' }}>
            Ładowanie danych...
          </div>
        )}
        {error && (
          <div style={{ height: 200, display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--red)' }}>
            ⚠ {error}
          </div>
        )}
        {!loading && !error && data.length === 0 && (
          <div style={{ height: 200, display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--text3)', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 32 }}>📊</div>
            <div>Brak danych dla wybranego okresu</div>
          </div>
        )}
        {!loading && !error && data.length > 0 && (
          <ResponsiveContainer width="100%" height={420}>
            <ComposedChart data={chartData} margin={{ top: 10, right: 60, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
              <XAxis
                dataKey="ts"
                tickFormatter={ts => fmt(ts, activeHours)}
                stroke="var(--text3)"
                tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
                minTickGap={60}
              />
              <YAxis
                yAxisId="left"
                stroke="var(--text3)"
                tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
                domain={['auto', 'auto']}
                tickFormatter={v => `${v}°`}
                width={40}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                stroke="var(--text3)"
                tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
                domain={[0, 'auto']}
                tickFormatter={v => `${v}W`}
                width={55}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12, fontFamily: 'var(--font-main)', paddingTop: 8 }} />

              {showBg && segments.map((seg, i) => (
                <ReferenceArea
                  key={i} yAxisId="left"
                  x1={seg.start} x2={seg.end}
                  fill={MODE_COLORS[seg.mode] || 'transparent'}
                  stroke="none" ifOverflow="hidden"
                />
              ))}

              {layers.includes('temp_current') && (
                <Line yAxisId="left" type="monotone" dataKey="temp_current"
                  name="Temp. aktualna" stroke={LINE_COLORS.temp_current}
                  strokeWidth={2} dot={false} unit="°C" connectNulls />
              )}
              {layers.includes('temp_target') && (
                <Line yAxisId="left" type="stepAfter" dataKey="temp_target"
                  name="Temp. docelowa" stroke={LINE_COLORS.temp_target}
                  strokeWidth={1.5} strokeDasharray="5 3" dot={false} unit="°C" connectNulls />
              )}
              {layers.includes('power_w') && (
                <Line yAxisId="right" type="stepAfter" dataKey="power_w"
                  name="Moc grzania (zadana)" stroke={LINE_COLORS.power_w}
                  strokeWidth={1.5} dot={false} unit="W" connectNulls />
              )}
              {layers.includes('tuya_power_w') && (
                <Line yAxisId="right" type="monotone" dataKey="tuya_power_w"
                  name="Moc rzeczywista (Tuya)" stroke="#22d3ee"
                  strokeWidth={1.5} dot={false} unit="W" connectNulls={false} />
              )}
              {layers.includes('pv_power_w') && (
                <Line yAxisId="right" type="monotone" dataKey="pv_power_w"
                  name="Produkcja PV" stroke={LINE_COLORS.pv_power_w}
                  strokeWidth={1.5} dot={false} unit="W" connectNulls />
              )}
              {layers.includes('draw_events') && drawEvents
                .filter(e => e.category === 'session')
                .map(e => (
                  <ReferenceArea
                    key={`${e.start_ts}-${e.end_ts}`}
                    yAxisId="left"
                    x1={snapToNearestTs(e.start_ts, chartData)}
                    x2={snapToNearestTs(e.end_ts, chartData)}
                    fill={DRAW_EVENT_COLORS[e.category] || 'rgba(234,179,8,0.35)'}
                    stroke={DRAW_EVENT_BORDER[e.category] || '#eab308'}
                    strokeWidth={1}
                    ifOverflow="hidden"
                  />
                ))}
              {layers.includes('pump_events') && pumpEvents.map(e => (
                <ReferenceArea
                  key={`pump-${e.id}`}
                  yAxisId="left"
                  x1={snapToNearestTs(e.start_ts, chartData)}
                  x2={snapToNearestTs(e.end_ts || new Date().toISOString(), chartData)}
                  fill="rgba(168,85,247,0.30)"
                  stroke="#a855f7"
                  strokeWidth={1}
                  ifOverflow="hidden"
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </Card>

      {showBg && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
          {Object.entries(MODE_LABELS).slice(0, 5).map(([mode, label]) => (
            <div key={mode} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text2)' }}>
              <div style={{
                width: 16, height: 12, borderRadius: 3,
                background: MODE_COLORS[mode], border: `1px solid ${MODE_BORDER[mode]}`,
              }} />
              {label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── SUB-TAB: Zużyta energia ───────────────────────────────────

function EnergyChart() {
  const [range, setRange]     = useState('14d');
  const [data, setData]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [todayKwh, setTodayKwh] = useState(null);

  const days = ENERGY_RANGES.find(r => r.id === range)?.days || 14;

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const token = localStorage.getItem('boiler_token');
      const headers = { 'Authorization': `Bearer ${token}` };

      const [energyRes, statusRes] = await Promise.all([
        fetch(`/api/economy?range=${days <= 7 ? '7d' : days <= 30 ? '30d' : days <= 90 ? '3m' : '12m'}`, { headers }),
        fetch('/api/status', { headers }),
      ]);

      if (!energyRes.ok) throw new Error(`HTTP ${energyRes.status}`);
      const raw = await energyRes.json();

      if (statusRes.ok) {
        const st = await statusRes.json();
        setTodayKwh(st.energy_today_kwh ?? null);
      }

      // Oznacz dzisiejszy dzień
      const today = new Date().toISOString().slice(0, 10);
      const list = Array.isArray(raw) ? raw : (raw.daily || []);
      const mapped = list.map(r => ({
        ...r,
        label: fmtDay(r.day),
        isToday: r.day === today,
      }));

      setData(mapped);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const id = setInterval(() => { if (!document.hidden) load(); }, 60000);
    return () => clearInterval(id);
  }, [load]);

  const totalKwh = data.reduce((s, r) => s + (r.total || 0), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Controls */}
      <Card style={{ padding: '14px 20px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 4 }}>
            {ENERGY_RANGES.map(r => (
              <button key={r.id} onClick={() => setRange(r.id)} style={{
                padding: '6px 14px', borderRadius: 8,
                background: range === r.id ? 'var(--accent)' : 'var(--bg3)',
                color: range === r.id ? '#fff' : 'var(--text2)',
                border: '1px solid var(--border)', cursor: 'pointer',
                fontFamily: 'var(--font-main)', fontWeight: 600, fontSize: 13, transition: 'all 0.15s',
              }}>{r.label}</button>
            ))}
          </div>
          <button onClick={load} style={{
            padding: '6px 12px', borderRadius: 8,
            background: 'var(--bg3)', border: '1px solid var(--border)',
            color: 'var(--text2)', cursor: 'pointer', fontSize: 14,
          }}>↺</button>
        </div>
      </Card>

      {/* Summary cards */}
      {!loading && !error && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
          {[
            { label: 'Dziś (do teraz)', value: todayKwh != null ? `${todayKwh.toFixed(2)} kWh` : '—', color: '#f59e0b' },
            { label: `Suma (${days} dni)`, value: `${totalKwh.toFixed(2)} kWh`, color: 'var(--accent)' },
            { label: 'Średnio / dzień', value: data.length ? `${(totalKwh / data.length).toFixed(2)} kWh` : '—', color: 'var(--text2)' },
          ].map(s => (
            <div key={s.label} style={{
              background: 'var(--bg2)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '12px 16px',
            }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text3)',
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                {s.label}
              </div>
              <div style={{ fontSize: 20, fontWeight: 700, color: s.color,
                fontFamily: 'var(--font-mono)' }}>
                {s.value}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Bar chart */}
      <Card style={{ padding: '16px 8px 8px 8px' }}>
        {loading && (
          <div style={{ height: 340, display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--text3)' }}>
            Ładowanie danych...
          </div>
        )}
        {error && (
          <div style={{ height: 200, display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--red)' }}>
            ⚠ {error}
          </div>
        )}
        {!loading && !error && data.length === 0 && (
          <div style={{ height: 200, display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--text3)', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 32 }}>⚡</div>
            <div>Brak danych energetycznych</div>
          </div>
        )}
        {!loading && !error && data.length > 0 && (
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} vertical={false} />
              <XAxis
                dataKey="label"
                stroke="var(--text3)"
                tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
              />
              <YAxis
                stroke="var(--text3)"
                tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
                tickFormatter={v => `${v} kWh`}
                width={65}
              />
              <Tooltip content={<EnergyTooltip />} />
              <Bar
                dataKey="total"
                name="Zużycie"
                radius={[6, 6, 0, 0]}
                fill="#f59e0b"
                maxBarSize={48}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>

      <div style={{ fontSize: 11, color: 'var(--text3)', textAlign: 'center' }}>
        Zużycie obliczone jako całka mocy × czas. Próbkowanie co ~60s.
      </div>
    </div>
  );
}

// ── MAIN COMPONENT ────────────────────────────────────────────

const TABS = [
  { id: 'boiler', label: '🌡 Bojler / PV' },
  { id: 'energy', label: '⚡ Zużyta energia' },
];

export default function Charts() {
  const [tab, setTab] = useState('boiler');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4 }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '8px 20px', borderRadius: 10,
            background: tab === t.id ? 'var(--accent)' : 'var(--bg2)',
            color: tab === t.id ? '#fff' : 'var(--text2)',
            border: `1px solid ${tab === t.id ? 'var(--accent)' : 'var(--border)'}`,
            cursor: 'pointer', fontFamily: 'var(--font-main)',
            fontWeight: 600, fontSize: 14, transition: 'all 0.15s',
          }}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'boiler' && <BoilerChart />}
      {tab === 'energy' && <EnergyChart />}
    </div>
  );
}
