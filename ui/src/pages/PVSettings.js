import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

const TEMPS = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70];
const POWER_MODES = [
  { id: 'auto',  label: 'Auto',   desc: 'Moc zależy od nadwyżki PV ponad próg' },
  { id: '700',   label: '700W',   desc: 'Stała moc niska' },
  { id: '1300',  label: '1300W',  desc: 'Stała moc średnia' },
  { id: '2000',  label: '2000W',  desc: 'Stała moc pełna' },
];

function Card({ children, style }) {
  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', padding: 20,
      boxShadow: 'var(--card-shadow)', ...style,
    }}>
      {children}
    </div>
  );
}

function Label({ children }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, letterSpacing: '0.08em',
      textTransform: 'uppercase', color: 'var(--text3)', marginBottom: 8,
    }}>
      {children}
    </div>
  );
}

function SectionTitle({ icon, title, desc }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 20 }}>{icon}</span>
        <div style={{ fontSize: 16, fontWeight: 700 }}>{title}</div>
      </div>
      {desc && (
        <div style={{ fontSize: 13, color: 'var(--text3)', marginTop: 4, marginLeft: 30 }}>
          {desc}
        </div>
      )}
    </div>
  );
}

function NumberInput({ value, onChange, min, max, step = 1, unit }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <button onClick={() => onChange(Math.max(min, value - step))} style={{
        width: 36, height: 36, borderRadius: 8,
        background: 'var(--bg3)', border: '1px solid var(--border)',
        color: 'var(--text)', cursor: 'pointer', fontSize: 18,
      }}>−</button>
      <div style={{
        minWidth: 80, textAlign: 'center',
        fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700,
        color: 'var(--accent)',
      }}>
        {value}{unit && <span style={{ fontSize: 13, color: 'var(--text3)', marginLeft: 3 }}>{unit}</span>}
      </div>
      <button onClick={() => onChange(Math.min(max, value + step))} style={{
        width: 36, height: 36, borderRadius: 8,
        background: 'var(--bg3)', border: '1px solid var(--border)',
        color: 'var(--text)', cursor: 'pointer', fontSize: 18,
      }}>+</button>
    </div>
  );
}

export default function PVSettings() {
  const [cfg, setCfg]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);
  const [msg, setMsg]         = useState(null);
  const [changed, setChanged] = useState(false);

  const [form, setForm] = useState({
    pv_min_power_w:  700,
    pv_window_start: '00:00',
    pv_window_stop:  '23:59',
    pv_hysteresis_s: 30,
    pv_target_temp:  65,
    pv_power_mode:   'auto',
    pv_power_fixed_w: 2000,
  });

  const load = useCallback(async () => {
    try {
      const c = await api.getConfig();
      setCfg(c);
      setForm(f => ({
        ...f,
        pv_min_power_w:   c.pv_min_power_w   ?? 700,
        pv_window_start:  c.pv_window_start   ?? '00:00',
        pv_window_stop:   c.pv_window_stop    ?? '23:59',
        pv_hysteresis_s:  c.pv_hysteresis_s   ?? 30,
        pv_target_temp:   c.pv_target_temp    ?? 65,
        pv_power_mode:    c.pv_power_mode     ?? 'auto',
        pv_power_fixed_w: c.pv_power_fixed_w  ?? 2000,
      }));
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const set = (key, val) => {
    setForm(f => ({ ...f, [key]: val }));
    setChanged(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.patchConfig(form);
      setChanged(false);
      setMsg({ type: 'ok', text: 'Ustawienia PV zapisane' });
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setSaving(false);
      setTimeout(() => setMsg(null), 3000);
    }
  };

  if (loading) return (
    <div style={{ textAlign: 'center', padding: 60, color: 'var(--text3)' }}>Ładowanie...</div>
  );

  // Auto power explanation
  const p = form.pv_min_power_w;
  const autoExplain = [
    { label: `PV ≥ ${p}W`,        power: '700W',  example: `np. PV ${p+100}W → 700W` },
    { label: `PV ≥ ${p+600}W`,    power: '1300W', example: `np. PV ${p+700}W → 1300W` },
    { label: `PV ≥ ${p+1300}W`,   power: '2000W', example: `np. PV ${p+1400}W → 2000W` },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 600 }}>

      {/* Próg minimalny */}
      <Card>
        <SectionTitle
          icon="⚡"
          title="Minimalna moc PV"
          desc="Poniżej tego progu PV nie załącza grzania"
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
          <NumberInput
            value={form.pv_min_power_w}
            onChange={v => set('pv_min_power_w', v)}
            min={100} max={3000} step={50} unit="W"
          />
          <div style={{
            flex: 1, padding: '10px 14px', borderRadius: 8,
            background: 'var(--bg3)', fontSize: 13, color: 'var(--text2)',
          }}>
            Minimalna produkcja PV do uruchomienia grzania (700W / 1300W / 2000W liczone jako nadwyżka ponad) <strong>{form.pv_min_power_w}W</strong>
          </div>
        </div>
      </Card>

      {/* Okno czasowe */}
      <Card>
        <SectionTitle
          icon="🕐"
          title="Okno czasowe"
          desc="PV może załączyć grzanie tylko w tym przedziale czasu"
        />
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {[
            ['pv_window_start', 'Od godziny'],
            ['pv_window_stop',  'Do godziny'],
          ].map(([key, lbl]) => (
            <div key={key} style={{ flex: 1, minWidth: 140 }}>
              <Label>{lbl}</Label>
              <input
                type="time"
                value={form[key]}
                onChange={e => set(key, e.target.value)}
                style={{
                  width: '100%', padding: '11px 14px',
                  background: 'var(--bg3)', border: '1px solid var(--border)',
                  borderRadius: 8, color: 'var(--text)',
                  fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 600,
                }}
              />
            </div>
          ))}
        </div>
        <div style={{
          marginTop: 12, padding: '10px 14px', borderRadius: 8,
          background: 'var(--accent)11', border: '1px solid var(--accent)33',
          fontSize: 13, color: 'var(--text2)',
        }}>
          💡 PV może grzać między <strong>{form.pv_window_start}</strong> a <strong>{form.pv_window_stop}</strong>.
          Poza tym oknem — bojler nie jest załączany przez PV nawet jeśli moc jest wystarczająca.
        </div>
      </Card>

      {/* Histereza */}
      <Card>
        <SectionTitle
          icon="⏱"
          title="Histereza"
          desc="Czas stabilności zanim PV zmieni stan — zapobiega migotaniu przy chwilowych spadkach"
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
          <NumberInput
            value={form.pv_hysteresis_s}
            onChange={v => set('pv_hysteresis_s', v)}
            min={5} max={300} step={5} unit="s"
          />
          <div style={{
            flex: 1, padding: '10px 14px', borderRadius: 8,
            background: 'var(--bg3)', fontSize: 13, color: 'var(--text2)',
          }}>
            PV musi spełniać (lub nie spełniać) warunki przez <strong>{form.pv_hysteresis_s}s</strong> zanim zmieni stan grzania.
          </div>
        </div>
      </Card>

      {/* Temperatura */}
      <Card>
        <SectionTitle
          icon="🌡️"
          title="Temperatura docelowa"
          desc="Do jakiej temperatury PV ma nagrzewać wodę"
        />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {TEMPS.map(t => (
            <button key={t} onClick={() => set('pv_target_temp', t)} style={{
              padding: '8px 14px', borderRadius: 8,
              background: form.pv_target_temp === t ? 'var(--accent)22' : 'var(--bg3)',
              border: `2px solid ${form.pv_target_temp === t ? 'var(--accent)' : 'var(--border)'}`,
              color: form.pv_target_temp === t ? 'var(--accent)' : 'var(--text2)',
              fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700,
              cursor: 'pointer', transition: 'all 0.15s',
            }}>
              {t}°C
            </button>
          ))}
        </div>
      </Card>

      {/* Tryb mocy */}
      <Card>
        <SectionTitle
          icon="⚙️"
          title="Tryb mocy grzania"
          desc="Jak dobierana jest moc bojlera gdy PV grzeje"
        />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
          {POWER_MODES.map(pm => (
            <button key={pm.id} onClick={() => set('pv_power_mode', pm.id)} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '12px 16px', borderRadius: 10, textAlign: 'left',
              background: form.pv_power_mode === pm.id ? 'var(--accent)15' : 'var(--bg3)',
              border: `2px solid ${form.pv_power_mode === pm.id ? 'var(--accent)' : 'var(--border)'}`,
              cursor: 'pointer', transition: 'all 0.15s',
              fontFamily: 'var(--font-main)',
            }}>
              <div style={{
                width: 44, height: 44, borderRadius: 10, flexShrink: 0,
                background: form.pv_power_mode === pm.id ? 'var(--accent)' : 'var(--bg4)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 800, fontSize: 14,
                color: form.pv_power_mode === pm.id ? '#fff' : 'var(--text2)',
                transition: 'all 0.15s',
              }}>
                {pm.label}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{
                  fontWeight: 700, fontSize: 14,
                  color: form.pv_power_mode === pm.id ? 'var(--accent)' : 'var(--text)',
                }}>
                  {pm.label === 'Auto' ? 'Auto (wg produkcji PV)' : `Stała ${pm.label}`}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>{pm.desc}</div>
              </div>
              {form.pv_power_mode === pm.id && (
                <div style={{ color: 'var(--accent)', fontSize: 18 }}>✓</div>
              )}
            </button>
          ))}
        </div>

        {/* Auto power explanation */}
        {form.pv_power_mode === 'auto' && (
          <div style={{
            background: 'var(--bg3)', borderRadius: 10,
            padding: '14px 16px', border: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text3)', marginBottom: 10 }}>
              LOGIKA AUTO (próg aktywacji: {form.pv_min_power_w}W):
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {autoExplain.map((row, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  fontSize: 13,
                }}>
                  <div style={{
                    padding: '3px 10px', borderRadius: 20,
                    background: i === 0 ? 'var(--yellow)22' : i === 1 ? 'var(--orange)22' : 'var(--red)22',
                    color: i === 0 ? 'var(--yellow)' : i === 1 ? 'var(--orange)' : 'var(--red)',
                    fontWeight: 700, fontSize: 12, minWidth: 52, textAlign: 'center',
                  }}>
                    {row.power}
                  </div>
                  <span style={{ color: 'var(--text2)' }}>{row.label}</span>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 11,
                    color: 'var(--text3)', marginLeft: 'auto',
                  }}>
                    np. {row.example}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Save button */}
      <button
        onClick={save}
        disabled={!changed || saving}
        style={{
          padding: '15px', borderRadius: 'var(--radius)',
          background: changed ? 'var(--accent)' : 'var(--bg3)',
          color: changed ? '#fff' : 'var(--text3)',
          border: 'none', cursor: changed ? 'pointer' : 'not-allowed',
          fontFamily: 'var(--font-main)', fontWeight: 700, fontSize: 16,
          transition: 'all 0.2s',
          boxShadow: changed ? 'var(--glow)' : 'none',
        }}
      >
        {saving ? 'Zapisuję...' : changed ? '✓ Zapisz ustawienia PV' : 'Brak zmian'}
      </button>

      {msg && (
        <div style={{
          padding: '12px 16px', borderRadius: 10,
          background: msg.type === 'ok' ? 'var(--green)22' : 'var(--red)22',
          border: `1px solid ${msg.type === 'ok' ? 'var(--green)' : 'var(--red)'}44`,
          color: msg.type === 'ok' ? 'var(--green)' : 'var(--red)',
          fontSize: 14, fontWeight: 500,
        }}>
          {msg.type === 'ok' ? '✓' : '⚠'} {msg.text}
        </div>
      )}
    </div>
  );
}
