import React, { useState, useEffect, useCallback } from 'react';
import {
  ComposedChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Line
} from 'recharts';

// ── Helpers ───────────────────────────────────────────────────

const RANGES = [
  { id: '7d',  label: '7 dni' },
  { id: '30d', label: '30 dni' },
  { id: '3m',  label: '3 miesiące' },
  { id: '12m', label: '12 miesięcy' },
];

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
        fontSize: 26, fontWeight: 800,
        color, fontFamily: 'var(--font-mono)', lineHeight: 1,
      }}>
        {value}
        <span style={{ fontSize: 13, fontWeight: 400, marginLeft: 4, color: 'var(--text2)' }}>
          {unit}
        </span>
      </div>
      {sub && (
        <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 5 }}>{sub}</div>
      )}
    </div>
  );
}

function PvBar({ pct }) {
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: 'var(--green)', fontWeight: 600 }}>
          ☀ Z PV
        </span>
        <span style={{ fontSize: 12, color: 'var(--text3)', fontWeight: 600 }}>
          ⚡ Z sieci
        </span>
      </div>
      <div style={{
        height: 16, borderRadius: 8, overflow: 'hidden',
        background: 'var(--bg4)', display: 'flex',
      }}>
        <div style={{
          width: `${pct}%`, background: 'var(--green)',
          transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, fontWeight: 700, color: '#fff',
          minWidth: pct > 10 ? 'auto' : 0,
        }}>
          {pct > 12 ? `${pct}%` : ''}
        </div>
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, fontWeight: 700, color: 'var(--text2)',
        }}>
          {(100 - pct) > 12 ? `${(100 - pct).toFixed(1)}%` : ''}
        </div>
      </div>
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const pv   = payload.find(p => p.dataKey === 'pv')?.value   || 0;
  const grid = payload.find(p => p.dataKey === 'grid')?.value || 0;
  const total = pv + grid;
  const pct = total > 0 ? ((pv / total) * 100).toFixed(1) : 0;

  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '10px 14px', fontSize: 12,
      boxShadow: '0 8px 24px rgba(0,0,0,0.4)', minWidth: 160,
    }}>
      <div style={{ color: 'var(--text3)', marginBottom: 8, fontFamily: 'var(--font-mono)' }}>
        {label}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: 'var(--green)', marginBottom: 4 }}>
        <span>☀ PV</span>
        <strong>{pv.toFixed(3)} kWh</strong>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: '#94a3b8', marginBottom: 6 }}>
        <span>⚡ Sieć</span>
        <strong>{grid.toFixed(3)} kWh</strong>
      </div>
      <div style={{
        borderTop: '1px solid var(--border)', paddingTop: 6,
        display: 'flex', justifyContent: 'space-between',
        color: pct > 50 ? 'var(--green)' : 'var(--orange)',
        fontWeight: 700,
      }}>
        <span>Autokonsumpcja</span>
        <span>{pct}%</span>
      </div>
    </div>
  );
}

// ── MAIN ──────────────────────────────────────────────────────

export default function Economy() {
  const [range, setRange]     = useState('30d');
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [view, setView]       = useState('daily'); // daily | monthly

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`/api/economy?range=${range}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('boiler_token')}` }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => { load(); }, [load]);

  const chartData = data ? (view === 'daily' ? data.daily : data.monthly) : [];
  const xKey = view === 'daily' ? 'day' : 'month';

  // Formatuj etykiety osi X
  const fmtX = (v) => {
    if (!v) return '';
    if (view === 'monthly') {
      const [y, m] = v.split('-');
      const months = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];
      return `${months[+m-1]} ${y.slice(2)}`;
    }
    const d = new Date(v);
    return `${d.getDate().toString().padStart(2,'0')}.${(d.getMonth()+1).toString().padStart(2,'0')}`;
  };

  const s = data?.summary;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

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
      {s && (
        <>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: 12,
          }}>
            <SummaryCard
              label="Łącznie zużyte"
              value={s.total_kwh.toFixed(2)}
              unit="kWh"
              color="var(--accent)"
              sub={`za ${RANGES.find(r=>r.id===range)?.label}`}
            />
            <SummaryCard
              label="Z fotowoltaiki"
              value={s.pv_kwh.toFixed(2)}
              unit="kWh"
              color="var(--green)"
              sub="bezpośrednia autokonsumpcja"
            />
            <SummaryCard
              label="Z sieci"
              value={s.grid_kwh.toFixed(2)}
              unit="kWh"
              color="var(--orange)"
              sub="pobrane z sieci"
            />
            <SummaryCard
              label="Autokonsumpcja"
              value={s.pct_pv.toFixed(1)}
              unit="%"
              color={s.pct_pv >= 70 ? 'var(--green)' : s.pct_pv >= 40 ? 'var(--yellow)' : 'var(--red)'}
              sub={s.pct_pv >= 70 ? 'Bardzo dobra' : s.pct_pv >= 40 ? 'Dobra' : 'Do poprawy'}
            />
          </div>

          {/* PV bar */}
          <Card style={{ padding: '14px 20px' }}>
            <Label>Podział źródeł energii (cały okres)</Label>
            <PvBar pct={s.pct_pv} />
            <div style={{
              display: 'flex', flexDirection: 'column', gap: 4,
              marginTop: 10, fontSize: 12, color: 'var(--text3)',
            }}>
              <span>
                💡 Bojler zużył bezpośrednio <strong style={{ color: 'var(--green)' }}>{s.pv_kwh.toFixed(2)} kWh</strong> z PV —
                tyle mniej pobrałeś z sieci.
              </span>
              <span>
                💰 Gdybyś oddał tę energię do sieci i pobrał z powrotem (net metering 80%),
                straciłbyś dodatkowo <strong style={{ color: 'var(--orange)' }}>{(s.pv_kwh * 0.2).toFixed(2)} kWh</strong>.
                Autokonsumpcja to opłaca.
              </span>
            </div>
          </Card>
        </>
      )}

      {/* Chart */}
      <Card>
        {/* View toggle */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Label>{view === 'daily' ? 'Zużycie dzienne' : 'Zużycie miesięczne'}</Label>
          <div style={{ display: 'flex', gap: 4 }}>
            {[['daily','Dziennie'],['monthly','Miesięcznie']].map(([v,l]) => (
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
        {!loading && !error && chartData.length === 0 && (
          <div style={{ height: 200, display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--text3)', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 32 }}>📊</div>
            <div>Brak danych dla wybranego okresu</div>
            <div style={{ fontSize: 12 }}>Dane gromadzone są co 60 sekund podczas pracy systemu</div>
          </div>
        )}
        {!loading && !error && chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={340}>
            <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
              <XAxis
                dataKey={xKey}
                tickFormatter={fmtX}
                stroke="var(--text3)"
                tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
                minTickGap={view === 'daily' ? 20 : 5}
              />
              <YAxis
                stroke="var(--text3)"
                tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
                tickFormatter={v => `${v.toFixed(2)}`}
                width={50}
                label={{ value: 'kWh', angle: -90, position: 'insideLeft',
                  fill: 'var(--text3)', fontSize: 11, dy: 20 }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 12, fontFamily: 'var(--font-main)', paddingTop: 8 }}
                formatter={(v) => v === 'pv' ? '☀ Z PV' : '⚡ Z sieci'}
              />
              <Bar dataKey="pv"   name="pv"   stackId="a" fill="#22c55e" radius={[0,0,0,0]} maxBarSize={40} />
              <Bar dataKey="grid" name="grid" stackId="a" fill="#475569" radius={[4,4,0,0]} maxBarSize={40} />
              <Line
                type="monotone"
                dataKey="pct_pv"
                name="% PV"
                stroke="#f97316"
                strokeWidth={1.5}
                dot={false}
                yAxisId={0}
                hide
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Info */}
      <div style={{
        padding: '10px 14px', borderRadius: 10,
        background: 'var(--bg3)', fontSize: 12, color: 'var(--text3)',
        border: '1px solid var(--border)',
      }}>
        {data?.energy_source === 'tuya' ? (
          <>🔋 Suma dzienna z realnego pomiaru wtyczki Tuya. Podział PV/sieć to przybliżenie —
          proporcje z trybu sterowania, przeskalowane do realnej sumy.</>
        ) : (
          <>💡 Kalkulacja oparta na próbkach co 60s. Energia = Σ(moc × 1/60h).</>
        )}
        {' '}Autokonsumpcja = energia pobrana bezpośrednio z PV (tryb HEATING_PV).
        Oszczędność vs net metering = 20% wartości energii PV (utracone przy oddaniu do sieci).
      </div>
    </div>
  );
}
