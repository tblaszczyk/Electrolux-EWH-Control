import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

const DAYS = [
  { id: 'mon', label: 'Pon' },
  { id: 'tue', label: 'Wt'  },
  { id: 'wed', label: 'Śr'  },
  { id: 'thu', label: 'Czw' },
  { id: 'fri', label: 'Pt'  },
  { id: 'sat', label: 'Sob' },
  { id: 'sun', label: 'Nd'  },
];

const TEMPS = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70];
const POWERS = [700, 1300, 2000];
const POWER_LABELS = { 700: '700W', 1300: '1300W', 2000: '2000W' };

const IDLE_OPTIONS = [
  { id: 'off',    label: 'Wyłączony',     desc: 'Brak minimalnego grzania',   icon: '○' },
  { id: 'low_20', label: '20°C / 700W',   desc: 'Minimalny poziom ochronny',  icon: '◔' },
  { id: 'low_30', label: '30°C / 700W',   desc: 'Komfortowe czuwanie',        icon: '◑' },
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
      textTransform: 'uppercase', color: 'var(--text3)', marginBottom: 10,
    }}>
      {children}
    </div>
  );
}

const EMPTY_SLOT = {
  days: [],
  time_start: '06:00',
  time_stop: '08:00',
  temp_c: 55,
  power_w: 2000,
  label: '',
  enabled: 1,
};

function SlotModal({ slot, onSave, onClose }) {
  const [form, setForm] = useState(slot ? { ...slot, days: JSON.parse(slot.days || '[]') } : { ...EMPTY_SLOT });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState(null);

  const toggleDay = (d) => setForm(f => ({
    ...f,
    days: f.days.includes(d) ? f.days.filter(x => x !== d) : [...f.days, d],
  }));

  const handleSave = async () => {
    if (!form.days.length) return setErr('Wybierz przynajmniej jeden dzień');
    if (form.time_start >= form.time_stop) return setErr('Czas zakończenia musi być po czasie startu');
    setSaving(true);
    try {
      await onSave(form);
      onClose();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const overlay = {
    position: 'fixed', inset: 0, zIndex: 200,
    background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    padding: 16,
  };

  const modal = {
    background: 'var(--bg2)', borderRadius: 'var(--radius)',
    border: '1px solid var(--border)', padding: 24,
    width: '100%', maxWidth: 480,
    boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
  };

  return (
    <div style={overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={modal}>
        <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 20 }}>
          {slot ? 'Edytuj slot' : 'Nowy slot'}
        </div>

        {/* Label */}
        <div style={{ marginBottom: 16 }}>
          <Label>Nazwa (opcjonalna)</Label>
          <input
            value={form.label}
            onChange={e => setForm(f => ({ ...f, label: e.target.value }))}
            placeholder="np. Rano, Wieczór..."
            style={{
              width: '100%', padding: '10px 14px',
              background: 'var(--bg3)', border: '1px solid var(--border)',
              borderRadius: 8, color: 'var(--text)',
              fontFamily: 'var(--font-main)', fontSize: 14,
            }}
          />
        </div>

        {/* Days */}
        <div style={{ marginBottom: 16 }}>
          <Label>Dni tygodnia</Label>
          <div style={{ display: 'flex', gap: 6 }}>
            {DAYS.map(d => (
              <button key={d.id} onClick={() => toggleDay(d.id)} style={{
                flex: 1, padding: '8px 0',
                background: form.days.includes(d.id) ? 'var(--accent)' : 'var(--bg3)',
                color: form.days.includes(d.id) ? '#fff' : 'var(--text2)',
                border: `1px solid ${form.days.includes(d.id) ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 8, cursor: 'pointer',
                fontFamily: 'var(--font-main)', fontSize: 13, fontWeight: 600,
                transition: 'all 0.15s',
              }}>
                {d.label}
              </button>
            ))}
          </div>
        </div>

        {/* Time */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          {[['time_start', 'Godzina start'], ['time_stop', 'Godzina stop']].map(([k, lbl]) => (
            <div key={k} style={{ flex: 1 }}>
              <Label>{lbl}</Label>
              <input
                type="time"
                value={form[k]}
                onChange={e => setForm(f => ({ ...f, [k]: e.target.value }))}
                style={{
                  width: '100%', padding: '10px 14px',
                  background: 'var(--bg3)', border: '1px solid var(--border)',
                  borderRadius: 8, color: 'var(--text)',
                  fontFamily: 'var(--font-mono)', fontSize: 15,
                }}
              />
            </div>
          ))}
        </div>

        {/* Temp */}
        <div style={{ marginBottom: 16 }}>
          <Label>Temperatura</Label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {TEMPS.map(t => (
              <button key={t} onClick={() => setForm(f => ({ ...f, temp_c: t }))} style={{
                padding: '6px 12px', borderRadius: 8,
                background: form.temp_c === t ? 'var(--accent)22' : 'var(--bg3)',
                border: `1px solid ${form.temp_c === t ? 'var(--accent)' : 'var(--border)'}`,
                color: form.temp_c === t ? 'var(--accent)' : 'var(--text2)',
                fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600,
                cursor: 'pointer', transition: 'all 0.15s',
              }}>
                {t}°C
              </button>
            ))}
          </div>
        </div>

        {/* Power */}
        <div style={{ marginBottom: 20 }}>
          <Label>Limit mocy</Label>
          <div style={{ display: 'flex', gap: 8 }}>
            {POWERS.map(w => {
              const c = w === 700 ? 'var(--yellow)' : w === 1300 ? 'var(--orange)' : 'var(--red)';
              return (
                <button key={w} onClick={() => setForm(f => ({ ...f, power_w: w }))} style={{
                  flex: 1, padding: '10px 0',
                  background: form.power_w === w ? `${c}22` : 'var(--bg3)',
                  border: `2px solid ${form.power_w === w ? c : 'var(--border)'}`,
                  color: form.power_w === w ? c : 'var(--text2)',
                  borderRadius: 8, cursor: 'pointer',
                  fontFamily: 'var(--font-main)', fontWeight: 700, fontSize: 15,
                  transition: 'all 0.15s',
                }}>
                  {POWER_LABELS[w]}
                </button>
              );
            })}
          </div>
        </div>

        {err && (
          <div style={{
            marginBottom: 14, padding: '8px 12px', borderRadius: 8,
            background: 'var(--red)22', color: 'var(--red)', fontSize: 13,
          }}>
            {err}
          </div>
        )}

        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={onClose} style={{
            flex: 1, padding: '12px 0', borderRadius: 10,
            background: 'var(--bg3)', border: '1px solid var(--border)',
            color: 'var(--text2)', cursor: 'pointer',
            fontFamily: 'var(--font-main)', fontWeight: 600,
          }}>
            Anuluj
          </button>
          <button onClick={handleSave} disabled={saving} style={{
            flex: 2, padding: '12px 0', borderRadius: 10,
            background: 'var(--accent)', border: 'none',
            color: '#fff', cursor: 'pointer',
            fontFamily: 'var(--font-main)', fontWeight: 700, fontSize: 15,
          }}>
            {saving ? 'Zapisuję...' : '✓ Zapisz'}
          </button>
        </div>
      </div>
    </div>
  );
}

function SlotRow({ slot, onEdit, onDelete, onToggle }) {
  const days = JSON.parse(slot.days || '[]');
  const dayLabels = DAYS.filter(d => days.includes(d.id)).map(d => d.label).join(', ');

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 14,
      padding: '14px 16px',
      background: slot.enabled ? 'var(--bg2)' : 'var(--bg3)',
      borderRadius: 'var(--radius-sm)',
      border: '1px solid var(--border)',
      opacity: slot.enabled ? 1 : 0.6,
      transition: 'all 0.2s',
    }}>
      {/* Toggle */}
      <button onClick={() => onToggle(slot)} style={{
        width: 40, height: 22, borderRadius: 11,
        background: slot.enabled ? 'var(--green)' : 'var(--bg4)',
        border: 'none', cursor: 'pointer', position: 'relative',
        transition: 'background 0.2s', flexShrink: 0,
      }}>
        <div style={{
          position: 'absolute', top: 3,
          left: slot.enabled ? 21 : 3,
          width: 16, height: 16, borderRadius: '50%',
          background: '#fff', transition: 'left 0.2s',
        }} />
      </button>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {slot.label && (
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>
            {slot.label}
          </div>
        )}
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: '4px 12px',
          fontSize: 13, color: 'var(--text2)',
        }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>
            {slot.time_start} – {slot.time_stop}
          </span>
          <span style={{ color: 'var(--text3)' }}>{dayLabels}</span>
        </div>
      </div>

      {/* Badges */}
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        <span style={{
          padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
          background: 'var(--accent)22', color: 'var(--accent)',
        }}>
          {slot.temp_c}°C
        </span>
        <span style={{
          padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
          background: 'var(--orange)22', color: 'var(--orange)',
        }}>
          {slot.power_w}W
        </span>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 6 }}>
        <button onClick={() => onEdit(slot)} style={{
          padding: '6px 10px', borderRadius: 8,
          background: 'var(--bg3)', border: '1px solid var(--border)',
          color: 'var(--text2)', cursor: 'pointer', fontSize: 14,
        }}>✎</button>
        <button onClick={() => onDelete(slot.id)} style={{
          padding: '6px 10px', borderRadius: 8,
          background: 'var(--red)11', border: '1px solid var(--red)33',
          color: 'var(--red)', cursor: 'pointer', fontSize: 14,
        }}>✕</button>
      </div>
    </div>
  );
}

export default function Schedule() {
  const [slots, setSlots]         = useState([]);
  const [idleMode, setIdleMode]   = useState('off');
  const [loading, setLoading]     = useState(true);
  const [modal, setModal]         = useState(null); // null | 'new' | slot
  const [msg, setMsg]             = useState(null);

  const load = useCallback(async () => {
    try {
      const [s, cfg] = await Promise.all([api.getSchedule(), api.getConfig()]);
      setSlots(s);
      setIdleMode(cfg.idle_mode || 'off');
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const showMsg = (type, text) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 3000);
  };

  const handleSave = async (form) => {
    if (form.id) {
      await api.updateSlot(form.id, form);
    } else {
      await api.addSlot(form);
    }
    await load();
    showMsg('ok', form.id ? 'Slot zaktualizowany' : 'Slot dodany');
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Usunąć ten slot?')) return;
    await api.deleteSlot(id);
    await load();
    showMsg('ok', 'Slot usunięty');
  };

  const handleToggle = async (slot) => {
    const days = typeof slot.days === 'string' ? slot.days : JSON.stringify(slot.days);
    await api.updateSlot(slot.id, { enabled: slot.enabled ? 0 : 1 });
    await load();
  };

  const handleIdleChange = async (mode) => {
    setIdleMode(mode);
    try {
      await api.setIdle(mode);
      await api.patchConfig({ idle_mode: mode });
      showMsg('ok', 'Tryb czuwania zaktualizowany');
    } catch (e) {
      showMsg('err', e.message);
    }
  };

  if (loading) return (
    <div style={{ textAlign: 'center', padding: 60, color: 'var(--text3)' }}>
      Ładowanie...
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* IDLE settings */}
      <Card>
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>
            Tryb czuwania (IDLE)
          </div>
          <div style={{ fontSize: 13, color: 'var(--text3)' }}>
            Co bojler ma robić gdy żaden slot harmonogramu nie jest aktywny i PV nie grzeje
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {IDLE_OPTIONS.map(opt => (
            <button key={opt.id} onClick={() => handleIdleChange(opt.id)} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '14px 16px', borderRadius: 'var(--radius-sm)',
              background: idleMode === opt.id ? 'var(--accent)15' : 'var(--bg3)',
              border: `2px solid ${idleMode === opt.id ? 'var(--accent)' : 'var(--border)'}`,
              cursor: 'pointer', textAlign: 'left',
              transition: 'all 0.2s',
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: idleMode === opt.id ? 'var(--accent)' : 'var(--bg4)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18, transition: 'background 0.2s',
                flexShrink: 0,
              }}>
                {opt.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 14, fontWeight: 700,
                  color: idleMode === opt.id ? 'var(--accent)' : 'var(--text)',
                }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>
                  {opt.desc}
                </div>
              </div>
              {idleMode === opt.id && (
                <div style={{ color: 'var(--accent)', fontSize: 18 }}>✓</div>
              )}
            </button>
          ))}
        </div>
      </Card>

      {/* Slots header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700 }}>Sloty harmonogramu</div>
          <div style={{ fontSize: 13, color: 'var(--text3)', marginTop: 2 }}>
            {slots.length} {slots.length === 1 ? 'slot' : 'slotów'}
          </div>
        </div>
        <button onClick={() => setModal('new')} style={{
          padding: '10px 18px', borderRadius: 10,
          background: 'var(--accent)', border: 'none',
          color: '#fff', cursor: 'pointer',
          fontFamily: 'var(--font-main)', fontWeight: 700, fontSize: 14,
          boxShadow: 'var(--glow)',
        }}>
          + Dodaj slot
        </button>
      </div>

      {/* Slots list */}
      {slots.length === 0 ? (
        <Card style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text3)' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>📅</div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>Brak slotów</div>
          <div style={{ fontSize: 13, marginTop: 4 }}>
            Dodaj pierwszy slot harmonogramu
          </div>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {slots.map(slot => (
            <SlotRow
              key={slot.id}
              slot={slot}
              onEdit={s => setModal(s)}
              onDelete={handleDelete}
              onToggle={handleToggle}
            />
          ))}
        </div>
      )}

      {/* Message */}
      {msg && (
        <div style={{
          padding: '12px 16px', borderRadius: 10,
          background: msg.type === 'ok' ? 'var(--green)22' : 'var(--red)22',
          border: `1px solid ${msg.type === 'ok' ? 'var(--green)' : 'var(--red)'}44`,
          color: msg.type === 'ok' ? 'var(--green)' : 'var(--red)',
          fontSize: 14, fontWeight: 500,
          position: 'fixed', bottom: 24, left: '50%',
          transform: 'translateX(-50%)',
          boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
          zIndex: 150, whiteSpace: 'nowrap',
        }}>
          {msg.type === 'ok' ? '✓' : '⚠'} {msg.text}
        </div>
      )}

      {/* Modal */}
      {modal && (
        <SlotModal
          slot={modal === 'new' ? null : modal}
          onSave={handleSave}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}
