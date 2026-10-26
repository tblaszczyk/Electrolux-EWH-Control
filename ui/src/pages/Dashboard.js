import React from 'react';
import { useStatus } from '../hooks/useStatus';
import { api } from '../api/client';

const STATE_META = {
  HEATING_MANUAL:   { label: 'Grzanie ręczne',      color: '#a855f7', icon: '✋' },
  HEATING_SCHEDULE: { label: 'Grzanie harmonogram',  color: '#38bdf8', icon: '📅' },
  HEATING_PV:       { label: 'Grzanie PV',           color: '#22c55e', icon: '☀️' },
  IDLE:             { label: 'Tryb czuwania',         color: '#64748b', icon: '💤' },
  COOLING:          { label: 'Stygnięcie',            color: '#f97316', icon: '❄️' },
  ERROR:            { label: 'Błąd',                  color: '#ef4444', icon: '⚠️' },
  NO_COMMUNICATION: { label: 'Brak komunikacji',      color: '#ef4444', icon: '📡' },
  STARTING:         { label: 'Uruchamianie',          color: '#eab308', icon: '⟳'  },
  OFF:              { label: 'Wyłączony',             color: '#475569', icon: '○'  },
};

const MODE_LABELS = {
  MANUAL:   'Ręczny',
  SCHEDULE: 'Harmonogram',
  PV:       'PV',
  IDLE:     'Czuwanie',
  ERROR:    'Błąd',
  NO_COMM:  'Brak komun.',
};

function Card({ children, style }) {
  return (
    <div style={{
      background: 'var(--bg2)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: '20px',
      boxShadow: 'var(--card-shadow)',
      ...style,
    }}>
      {children}
    </div>
  );
}

function Label({ children }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, letterSpacing: '0.08em',
      textTransform: 'uppercase', color: 'var(--text3)',
      marginBottom: 6,
    }}>
      {children}
    </div>
  );
}

function TempGauge({ current, target }) {
  const pct = Math.min(100, Math.max(0, ((current - 10) / 65) * 100));
  const color = current >= target
    ? 'var(--orange)'
    : current > target - 5
    ? 'var(--yellow)'
    : 'var(--accent)';

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ position: 'relative', width: 160, height: 160, margin: '0 auto' }}>
        <svg width="160" height="160" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="80" cy="80" r="68"
            fill="none" stroke="var(--bg3)" strokeWidth="12" />
          <circle cx="80" cy="80" r="68"
            fill="none" stroke={color} strokeWidth="12"
            strokeDasharray={`${2 * Math.PI * 68}`}
            strokeDashoffset={`${2 * Math.PI * 68 * (1 - pct / 100)}`}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 1s ease, stroke 0.5s' }}
          />
        </svg>
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            fontSize: 40, fontWeight: 700, lineHeight: 1,
            color: color, fontFamily: 'var(--font-mono)',
            transition: 'color 0.5s',
          }}>
            {current > 0 ? `${current}°` : '—'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 4 }}>
            cel: {target > 0 ? `${target}°C` : '—'}
          </div>
        </div>
      </div>
      <div style={{ fontSize: 13, color: 'var(--text2)', marginTop: 8 }}>
        Temperatura wody
      </div>
    </div>
  );
}

function StatChip({ label, value, color, unit, note }) {
  return (
    <div style={{
      background: 'var(--bg3)', borderRadius: 'var(--radius-sm)',
      padding: '12px 16px', border: '1px solid var(--border)',
    }}>
      <Label>{label}</Label>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || 'var(--text)', fontFamily: 'var(--font-mono)' }}>
        {value}<span style={{ fontSize: 13, fontWeight: 400, marginLeft: 3, color: 'var(--text2)' }}>{unit}</span>
      </div>
      {note && (
        <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 3 }}>{note}</div>
      )}
    </div>
  );
}

function OnlineDot({ online }) {
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
      background: online ? 'var(--green)' : 'var(--red)',
      marginRight: 6, boxShadow: online ? '0 0 6px var(--green)' : 'none',
    }} />
  );
}

function PowerBar({ power }) {
  const levels = [0, 700, 1300, 2000];
  const colors = ['var(--bg4)', 'var(--yellow)', 'var(--orange)', 'var(--red)'];
  const idx = levels.indexOf(power);
  return (
    <div>
      <Label>Limit mocy grzania</Label>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        {levels.slice(1).map((w, i) => (
          <div key={w} style={{
            flex: 1, height: 8, borderRadius: 4,
            background: idx > i ? colors[i + 1] : 'var(--bg4)',
            transition: 'background 0.4s',
          }} />
        ))}
        <span style={{
          fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
          color: power > 0 ? 'var(--orange)' : 'var(--text3)',
          minWidth: 50, textAlign: 'right',
        }}>
          {power > 0 ? `${power}W` : 'OFF'}
        </span>
      </div>
    </div>
  );
}

function PowerButton({ enabled, toggling, onClick }) {
  return (
    <Card style={{
      padding: '14px 16px',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      minWidth: 90, cursor: 'default',
    }}>
      <button
        onClick={onClick}
        disabled={toggling}
        style={{
          width: 54, height: 54, borderRadius: '50%',
          background: enabled
            ? 'radial-gradient(circle, #22c55e33, #22c55e11)'
            : 'radial-gradient(circle, #ef444433, #ef444411)',
          border: `3px solid ${enabled ? 'var(--green)' : 'var(--red)'}`,
          cursor: toggling ? 'wait' : 'pointer',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 2,
          transition: 'all 0.3s',
          boxShadow: enabled
            ? '0 0 16px rgba(34,197,94,0.4)'
            : '0 0 16px rgba(239,68,68,0.3)',
        }}
      >
        <span style={{ fontSize: 22 }}>⏻</span>
      </button>
      <span style={{
        fontSize: 10, fontWeight: 700, marginTop: 6,
        color: enabled ? 'var(--green)' : 'var(--red)',
        letterSpacing: '0.12em',
      }}>
        {toggling ? '...' : enabled ? 'ON' : 'OFF'}
      </span>
    </Card>
  );
}

export default function Dashboard() {
  const { status, loading, error, refresh } = useStatus(8000);
  const [toggling, setToggling] = React.useState(false);
  const [pump, setPump] = React.useState(null);
  const [pumpMenu, setPumpMenu] = React.useState(false);
  const [pumpBusy, setPumpBusy] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    const loadPump = () => {
      api.getPumpStatus().then(d => { if (!cancelled) setPump(d); }).catch(() => {});
    };
    loadPump();
    const id = setInterval(loadPump, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const startPump = async (on, minutes) => {
    setPumpBusy(true);
    setPumpMenu(false);
    try {
      await api.setPumpManual(on, minutes);
      setTimeout(() => api.getPumpStatus().then(setPump).catch(() => {}), 1500);
    } catch (e) {
      console.error(e);
    } finally {
      setPumpBusy(false);
    }
  };

  const togglePower = async () => {
    if (!status) return;
    setToggling(true);
    try {
      await api.togglePower(!status.system_enabled);
      setTimeout(refresh, 2000);
      setTimeout(refresh, 5000);
    } catch (e) {
      console.error(e);
    } finally {
      setToggling(false);
    }
  };

  if (loading) return (
    <div style={{ textAlign: 'center', padding: 60, color: 'var(--text3)' }}>Ładowanie...</div>
  );

  if (error) return (
    <div style={{
      textAlign: 'center', padding: 40, color: 'var(--red)',
      background: 'var(--bg2)', borderRadius: 'var(--radius)', border: '1px solid var(--red)',
    }}>
      ⚠️ Błąd połączenia: {error}
    </div>
  );

  if (!status) return null;

  const state = STATE_META[status.state] || { label: status.state, color: 'var(--text2)', icon: '?' };
  const decisionMode = MODE_LABELS[status.last_decision_mode] || status.last_decision_mode;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Status bar */}
      <Card style={{ padding: '16px 20px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexWrap: 'wrap', gap: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 44, height: 44, borderRadius: 12,
              background: `${state.color}22`, border: `1px solid ${state.color}44`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22,
            }}>
              {state.icon}
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: state.color }}>
                {state.label}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>
                {status.reason}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 13, alignItems: 'center' }}>
            <span><OnlineDot online={status.boiler_online} />Bojler</span>
            <span><OnlineDot online={status.pv_online} />PV</span>
            {pump && (
              <span style={{ position: 'relative' }}>
                <button
                  onClick={() => setPumpMenu(o => !o)}
                  disabled={pumpBusy}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '3px 10px', borderRadius: 20, border: 'none', cursor: 'pointer',
                    background: pump.current_on ? 'var(--green)22' : 'var(--bg3)',
                    color: pump.current_on ? 'var(--green)' : 'var(--text3)',
                    fontWeight: 600, fontSize: 'inherit', fontFamily: 'inherit',
                  }}
                >
                  🔄 {pump.current_on ? 'Pompa: pracuje' : 'Pompa: OFF'}
                </button>
                {pumpMenu && (
                  <div style={{
                    position: 'absolute', right: 0, top: '100%', marginTop: 6, zIndex: 20,
                    display: 'flex', gap: 6, padding: 8, borderRadius: 12,
                    background: 'var(--bg2)', border: '1px solid var(--border)',
                    boxShadow: '0 4px 16px rgba(0,0,0,.3)',
                  }}>
                    {[5, 10, 15].map(m => (
                      <button key={m} onClick={() => startPump(true, m)} style={{
                        padding: '6px 12px', borderRadius: 8, border: 'none', cursor: 'pointer',
                        background: 'var(--bg3)', color: 'var(--text)', fontWeight: 600,
                        fontFamily: 'inherit', whiteSpace: 'nowrap',
                      }}>
                        {m} min
                      </button>
                    ))}
                    {pump.current_on && (
                      <button onClick={() => startPump(false, 5)} style={{
                        padding: '6px 12px', borderRadius: 8, border: 'none', cursor: 'pointer',
                        background: 'var(--red)22', color: 'var(--red)', fontWeight: 600,
                        fontFamily: 'inherit', whiteSpace: 'nowrap',
                      }}>
                        Wyłącz
                      </button>
                    )}
                  </div>
                )}
              </span>
            )}
          </div>
        </div>
      </Card>

      {/* Main grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: 20,
      }}>
        {/* Temperature gauge */}
        <Card style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
          <TempGauge
            current={status.boiler_temp_current || 0}
            target={status.last_decision_temp || status.boiler_temp_target || 0}
          />
          <div style={{ width: '100%' }}>
            <PowerBar power={status.boiler_power_w || 0} />
          </div>
        </Card>

        {/* PV + stats + tryb + ON/OFF */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 120 }}><StatChip
              label="Produkcja PV"
              value={status.pv_power_w != null ? Math.round(status.pv_power_w) : '—'}
              unit="W"
              color={status.pv_power_w > 1000 ? 'var(--green)' : status.pv_power_w > 0 ? 'var(--yellow)' : 'var(--text2)'}
            /></div>
            <div style={{ flex: 1, minWidth: 120 }}><StatChip
              label="Energia PV dziś"
              value={status.pv_today_kwh != null ? status.pv_today_kwh.toFixed(1) : '—'}
              unit="kWh"
              color="var(--accent)"
            /></div>
            <div style={{ flex: 1, minWidth: 120 }}><StatChip
              label="Zużycie dziś"
              value={status.energy_today_kwh != null ? status.energy_today_kwh.toFixed(2) : '—'}
              unit="kWh"
              color="#f59e0b"
              note={status.energy_source === 'tuya' ? '🔋 źródło: Tuya' : null}
            /></div>
            {status.energy_source === 'tuya' && (
              <div style={{ flex: 1, minWidth: 120 }}><StatChip
                label="Bieżący pobór"
                value={status.tuya_online && status.tuya_power_w != null ? Math.round(status.tuya_power_w) : '—'}
                unit="W"
                color={status.tuya_online ? '#f59e0b' : 'var(--text3)'}
                note={status.tuya_online ? '🔋 źródło: Tuya' : '⚠ wtyczka offline'}
              /></div>
            )}
          </div>

          {/* ON/OFF + Tryb sterowania w jednej linii */}
          <div style={{ display: 'flex', gap: 12, alignItems: 'stretch' }}>
            <PowerButton
              enabled={status.system_enabled !== false}
              toggling={toggling}
              onClick={togglePower}
            />
            <Card style={{ padding: '14px 16px', flex: 1 }}>
              <Label>Aktywny tryb sterowania</Label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6, flexWrap: 'wrap' }}>
                <div style={{
                  padding: '4px 12px', borderRadius: 20,
                  background: status.mode === 'MANUAL' ? 'var(--purple)22' : 'var(--accent)22',
                  border: `1px solid ${status.mode === 'MANUAL' ? 'var(--purple)' : 'var(--accent)'}44`,
                  color: status.mode === 'MANUAL' ? 'var(--purple)' : 'var(--accent)',
                  fontSize: 13, fontWeight: 600,
                }}>
                  {status.mode === 'MANUAL' ? '✋ Ręczny' : '⚡ Automatyczny'}
                </div>
                {status.last_decision_mode && (
                  <span style={{ fontSize: 12, color: 'var(--text3)' }}>
                    źródło: {decisionMode}
                  </span>
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>

      {/* Grzanie aktywne */}
      {status.boiler_heating && status.last_decision_mode !== 'IDLE' && (
        <Card style={{
          background: 'linear-gradient(135deg, var(--bg2), var(--bg3))',
          borderColor: 'var(--orange)33', padding: '14px 20px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>🔥</span>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--orange)' }}>
                Grzanie aktywne
              </div>
              <div style={{ fontSize: 12, color: 'var(--text3)' }}>
                Włączone przez: <strong>{decisionMode}</strong>
                {status.last_command_sent && (
                  <> · {status.last_command_sent.temp}°C · {status.last_command_sent.power_w}W</>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
