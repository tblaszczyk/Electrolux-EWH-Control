import React, { useState, useEffect, useCallback } from 'react';
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { api } from '../api/client';

// ── Helpers (wzorem Economy.js) ─────────────────────────────────

const RANGES = [
  { id: '7d',  label: '7 dni' },
  { id: '30d', label: '30 dni' },
  { id: '3m',  label: '3 miesiące' },
  { id: '12m', label: '12 miesięcy' },
];

const CATEGORY_LABELS = {
  session:      'Sesja poboru wody',
  subthreshold: 'Podprogowe (możliwa pompa cyrkulacyjna)',
};

const CATEGORY_COLORS = {
  session:      '#38bdf8',
  subthreshold: '#f59e0b',
};

const SIGNAL_LABELS = {
  normal:            'Normalnie',
  below_baseline:    'Poniżej typowej liczby',
  zero:              'Brak zdarzeń',
  zero_baseline:     'Brak punktu odniesienia',
  insufficient_data: 'Za mało danych (< 4 tyg. historii)',
};

const SIGNAL_COLORS = {
  normal:            'var(--green)',
  below_baseline:    'var(--orange)',
  zero:              'var(--red)',
  zero_baseline:     'var(--text3)',
  insufficient_data: 'var(--text3)',
};

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

function Label({ children }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, letterSpacing: '0.08em',
      textTransform: 'uppercase', color: 'var(--text3)', marginBottom: 6,
    }}>
      {children}
    </div>
  );
}

function SummaryCard({ label, value, unit, color, sub }) {
  return (
    <div style={{
      background: 'var(--bg3)', borderRadius: 12,
      padding: '14px 18px', border: '1px solid var(--border)',
      borderLeft: `4px solid ${color}`,
    }}>
      <Label>{label}</Label>
      <div style={{
        fontSize: 22, fontWeight: 800,
        color, fontFamily: 'var(--font-mono)', lineHeight: 1,
      }}>
        {value}
        {unit && <span style={{ fontSize: 13, fontWeight: 400, marginLeft: 4, color: 'var(--text2)' }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 5 }}>{sub}</div>}
    </div>
  );
}

function fmtDay(day) {
  if (!day) return '';
  const d = new Date(day + 'T00:00:00');
  return d.toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit' });
}

function fmtDateTime(ts) {
  if (!ts) return '';
  return new Date(ts).toLocaleString('pl-PL', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

function hourFrac(dateObj) {
  return dateObj.getHours() + dateObj.getMinutes() / 60 + dateObj.getSeconds() / 3600;
}

// Buduje listę segmentów (jeden dzień = jeden wiersz), dzieląc sesje
// przechodzące przez północ na dwie części.
function buildDaySegments(events) {
  const byDay = new Map();
  const push = (day, seg) => {
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day).push(seg);
  };

  for (const e of events) {
    const startDay = e.start_ts.slice(0, 10);
    const endDay = e.end_ts.slice(0, 10);
    const startD = new Date(e.start_ts);
    const endD = new Date(e.end_ts);

    if (startDay === endDay) {
      push(startDay, { from: hourFrac(startD), to: hourFrac(endD), e });
    } else {
      push(startDay, { from: hourFrac(startD), to: 24, e });
      push(endDay, { from: 0, to: hourFrac(endD), e });
    }
  }
  return byDay;
}

function DayTimeline({ days, events, showSubthreshold }) {
  const visible = events.filter(e => showSubthreshold || e.category !== 'subthreshold');
  const byDay = buildDaySegments(visible);
  const rows = [...days].reverse(); // najnowszy dzień na górze

  const HOUR_TICKS = [0, 3, 6, 9, 12, 15, 18, 21, 24];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Oś godzin */}
      <div style={{ display: 'flex', paddingLeft: 92 }}>
        <div style={{ position: 'relative', flex: 1, height: 16 }}>
          {HOUR_TICKS.map(h => (
            <span key={h} style={{
              position: 'absolute', left: `${(h / 24) * 100}%`,
              transform: h === 24 ? 'translateX(-100%)' : h === 0 ? 'none' : 'translateX(-50%)',
              fontSize: 10, color: 'var(--text3)', fontFamily: 'var(--font-mono)',
            }}>
              {String(h).padStart(2, '0')}
            </span>
          ))}
        </div>
      </div>

      {rows.map(d => {
        const segs = byDay.get(d.day) || [];
        const isWeekend = [0, 6].includes(new Date(d.day + 'T00:00:00').getDay());
        return (
          <div key={d.day} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 84, flexShrink: 0, fontSize: 11, fontFamily: 'var(--font-mono)',
              color: isWeekend ? 'var(--accent)' : 'var(--text2)', textAlign: 'right',
            }}>
              {new Date(d.day + 'T00:00:00').toLocaleDateString('pl-PL', { weekday: 'short' })} {fmtDay(d.day)}
            </div>
            <div style={{
              position: 'relative', flex: 1, height: 18, borderRadius: 4,
              background: 'var(--bg3)', border: '1px solid var(--border)', overflow: 'hidden',
            }}>
              {HOUR_TICKS.slice(1, -1).map(h => (
                <div key={h} style={{
                  position: 'absolute', left: `${(h / 24) * 100}%`, top: 0, bottom: 0,
                  width: 1, background: 'var(--border)', opacity: 0.5,
                }} />
              ))}
              {segs.map((seg, i) => {
                const widthPct = Math.max(((seg.to - seg.from) / 24) * 100, 0.4);
                return (
                  <div
                    key={i}
                    title={`${seg.e.start_ts.slice(11, 16)}–${seg.e.end_ts.slice(11, 16)} · ${seg.e.drop_c}°C · ${seg.e.duration_min} min · ${seg.e.n_bursts ?? '?'} faz${CATEGORY_LABELS[seg.e.category] ? ' · ' + CATEGORY_LABELS[seg.e.category] : ''}`}
                    style={{
                      position: 'absolute', top: 1, bottom: 1,
                      left: `${(seg.from / 24) * 100}%`,
                      width: `${widthPct}%`,
                      background: CATEGORY_COLORS[seg.e.category] || '#38bdf8',
                      opacity: seg.e.category === 'subthreshold' ? 0.55 : 0.9,
                      borderRadius: 2, cursor: 'default',
                    }}
                  />
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SummaryTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '10px 14px', fontSize: 12,
      boxShadow: '0 8px 24px rgba(0,0,0,0.4)', minWidth: 180,
    }}>
      <div style={{ color: 'var(--text3)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>{fmtDay(label)}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: '#38bdf8' }}>
        <span>Zdarzenia (17–23h)</span>
        <strong>{d?.count}</strong>
      </div>
      {d?.baseline_median != null && (
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: 'var(--text3)' }}>
          <span>Typowo (8 tyg.)</span>
          <strong>{d.baseline_median}</strong>
        </div>
      )}
      {d?.signal && (
        <div style={{
          marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--border)',
          color: SIGNAL_COLORS[d.signal] || 'var(--text3)', fontSize: 11,
        }}>
          {SIGNAL_LABELS[d.signal] || d.signal}
        </div>
      )}
    </div>
  );
}

// ── MAIN ──────────────────────────────────────────────────────

export default function UsageDetection() {
  const [range, setRange]           = useState('30d');
  const [summary, setSummary]       = useState(null);
  const [events, setEvents]         = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [showSubthreshold, setShowSubthreshold] = useState(false);
  const [view, setView] = useState('summary'); // summary | timeline

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const hoursMap = { '7d': 168, '30d': 720, '3m': 2160, '12m': 8760 };
      const hours = hoursMap[range] || 720;
      const [summaryRes, eventsRes] = await Promise.all([
        api.getUsageSummary(range),
        api.getUsageEvents(hours),
      ]);
      setSummary(summaryRes);
      setEvents(eventsRes);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => { load(); }, [load]);

  const daily = summary?.daily || [];
  const today = daily[daily.length - 1];
  const zeroDays = daily.filter(d => d.signal === 'zero').length;

  const visibleEvents = events
    .filter(e => showSubthreshold || e.category !== 'subthreshold')
    .slice(0, 200);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Info banner */}
      <div style={{
        padding: '10px 14px', borderRadius: 10,
        background: 'var(--bg3)', fontSize: 12, color: 'var(--text3)',
        border: '1px solid var(--border)',
      }}>
        🧪 Funkcja eksperymentalna, czysto doradcza — nie wpływa na sterowanie bojlerem.
        Zdarzenia wykrywane są ze spadków temperatury w historii, bez dodatkowych czujników.
      </div>

      {/* Range selector */}
      <Card style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{
            fontSize: 11, fontWeight: 600, color: 'var(--text3)',
            textTransform: 'uppercase', letterSpacing: '0.08em', marginRight: 6,
          }}>
            Zakres:
          </span>
          {RANGES.map(r => (
            <button key={r.id} onClick={() => setRange(r.id)} style={{
              padding: '6px 14px', borderRadius: 8,
              background: range === r.id ? 'var(--accent)' : 'var(--bg3)',
              color: range === r.id ? '#fff' : 'var(--text2)',
              border: '1px solid var(--border)', cursor: 'pointer',
              fontFamily: 'var(--font-main)', fontWeight: 600, fontSize: 13,
              transition: 'all 0.15s',
            }}>
              {r.label}
            </button>
          ))}
          <button onClick={load} style={{
            marginLeft: 'auto', padding: '6px 10px', borderRadius: 8,
            background: 'var(--bg3)', border: '1px solid var(--border)',
            color: 'var(--text2)', cursor: 'pointer', fontSize: 14,
          }}>↺</button>
        </div>
      </Card>

      {/* Summary cards */}
      {today && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
          gap: 12,
        }}>
          <SummaryCard
            label="Sesji dziś (17–23h)"
            value={today.count}
            color="#38bdf8"
            sub="wykryte sesje poboru wody"
          />
          <SummaryCard
            label="Typowo dla tego dnia tyg."
            value={today.baseline_median ?? '—'}
            color="var(--text2)"
            sub="mediana z ost. 8 tygodni"
          />
          <SummaryCard
            label="Łączny czas dziś"
            value={today.total_duration_min ?? 0}
            unit="min"
            color="#a855f7"
            sub="suma czasu trwania sesji wieczorem"
          />
          <SummaryCard
            label="Sygnał dziś"
            value={SIGNAL_LABELS[today.signal] || today.signal}
            color={SIGNAL_COLORS[today.signal] || 'var(--text3)'}
            sub="wnioskowanie statystyczne, bez etykiet"
          />
          <SummaryCard
            label="Dni zerowych w oknie"
            value={zeroDays}
            unit={`/ ${daily.length}`}
            color="var(--orange)"
            sub="dni bez wykrytego poboru wieczorem"
          />
        </div>
      )}

      {/* Chart */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <Label>
            {view === 'summary'
              ? 'Dzienna liczba wykrytych poborów (17–23h) vs typowa (baseline)'
              : 'Oś czasu — pory dnia z wykrytym zużyciem wody'}
          </Label>
          <div style={{ display: 'flex', gap: 4 }}>
            {[['summary', 'Podsumowanie'], ['timeline', 'Oś czasu']].map(([v, l]) => (
              <button key={v} onClick={() => setView(v)} style={{
                padding: '4px 12px', borderRadius: 6,
                background: view === v ? 'var(--accent)' : 'var(--bg3)',
                color: view === v ? '#fff' : 'var(--text2)',
                border: '1px solid var(--border)', cursor: 'pointer',
                fontFamily: 'var(--font-main)', fontSize: 12, fontWeight: 600,
              }}>
                {l}
              </button>
            ))}
          </div>
        </div>
        {loading && (
          <div style={{ height: 300, display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--text3)' }}>
            Ładowanie...
          </div>
        )}
        {error && (
          <div style={{ height: 200, display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--red)' }}>
            ⚠ {error}
          </div>
        )}
        {!loading && !error && daily.length === 0 && (
          <div style={{ height: 200, display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--text3)', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 32 }}>🚿</div>
            <div>Brak danych — uruchom backfill: scripts/backfill_usage.py</div>
          </div>
        )}
        {!loading && !error && daily.length > 0 && view === 'summary' && (
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={daily} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
              <XAxis
                dataKey="day"
                tickFormatter={fmtDay}
                stroke="var(--text3)"
                tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
                minTickGap={20}
              />
              <YAxis
                stroke="var(--text3)"
                tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
                allowDecimals={false}
                width={30}
              />
              <Tooltip content={<SummaryTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12, fontFamily: 'var(--font-main)', paddingTop: 8 }} />
              <Bar dataKey="count" name="Zdarzenia" fill="#38bdf8" radius={[4, 4, 0, 0]} maxBarSize={24} />
              <Line
                type="monotone" dataKey="baseline_median" name="Typowo (baseline)"
                stroke="#f97316" strokeWidth={1.5} dot={false} connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
        {!loading && !error && daily.length > 0 && view === 'timeline' && (
          <div style={{ maxHeight: 600, overflowY: 'auto' }}>
            <DayTimeline days={daily} events={events} showSubthreshold={showSubthreshold} />
          </div>
        )}
      </Card>

      {/* Events list */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <Label>Wykryte zdarzenia</Label>
          <button onClick={() => setShowSubthreshold(v => !v)} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '5px 12px', borderRadius: 20,
            background: showSubthreshold ? 'rgba(245,158,11,0.2)' : 'var(--bg3)',
            border: `2px solid ${showSubthreshold ? '#f59e0b' : 'var(--border)'}`,
            color: showSubthreshold ? '#f59e0b' : 'var(--text3)',
            cursor: 'pointer', fontFamily: 'var(--font-main)',
            fontSize: 12, fontWeight: 600,
          }}>
            Pokaż podprogowe (pompa cyrkulacyjna?)
          </button>
        </div>
        {!loading && visibleEvents.length === 0 && (
          <div style={{ color: 'var(--text3)', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
            Brak zdarzeń w wybranym zakresie.
          </div>
        )}
        {visibleEvents.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ color: 'var(--text3)', textAlign: 'left' }}>
                  <th style={{ padding: '6px 10px' }}>Początek</th>
                  <th style={{ padding: '6px 10px' }}>Koniec</th>
                  <th style={{ padding: '6px 10px' }}>Spadek</th>
                  <th style={{ padding: '6px 10px' }}>Czas trwania</th>
                  <th style={{ padding: '6px 10px' }}>Fazy (eksperymentalne)</th>
                  <th style={{ padding: '6px 10px' }}>Kategoria</th>
                  <th style={{ padding: '6px 10px' }}>Klasa (eksperymentalne)</th>
                </tr>
              </thead>
              <tbody>
                {visibleEvents.map(e => (
                  <tr key={`${e.start_ts}-${e.end_ts}`} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{fmtDateTime(e.start_ts)}</td>
                    <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{fmtDateTime(e.end_ts)}</td>
                    <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{e.drop_c}°C</td>
                    <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{e.duration_min} min</td>
                    <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{e.n_bursts ?? '—'}</td>
                    <td style={{ padding: '6px 10px', color: CATEGORY_COLORS[e.category] }}>
                      {CATEGORY_LABELS[e.category] || e.category}
                    </td>
                    <td style={{ padding: '6px 10px', color: 'var(--text3)' }}>
                      {e.duration_class ? (e.duration_class === 'long' ? 'dłuższe (dzieci?)' : 'krótsze (dorosły?)') : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
