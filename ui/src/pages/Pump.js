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

const MODE_OPTIONS = [
  { id: 'off',      label: 'Wyłączona',  desc: 'Pompa nigdy nie włącza się automatycznie', icon: '○' },
  { id: 'manual',   label: 'Ręczny',     desc: 'Włączasz na zadany czas z tej zakładki',    icon: '✋' },
  { id: 'schedule', label: 'Harmonogram', desc: 'Praca wg zdefiniowanych okien czasowych',  icon: '📅' },
];

const MANUAL_MINUTES = [5, 10, 15, 30];

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

function Msg({ msg }) {
  if (!msg) return null;
  return (
    <div style={{
      padding: '10px 14px', borderRadius: 8, marginTop: 10,
      background: msg.type === 'ok' ? 'var(--green)22' : 'var(--red)22',
      border: `1px solid ${msg.type === 'ok' ? 'var(--green)' : 'var(--red)'}44`,
      color: msg.type === 'ok' ? 'var(--green)' : 'var(--red)',
      fontSize: 13, fontWeight: 500,
    }}>
      {msg.type === 'ok' ? '✓' : '⚠'} {msg.text}
    </div>
  );
}

function fmtDateTime(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString('pl-PL', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

// ── Modal edycji slotu ──────────────────────────────────────────

const EMPTY_SLOT = {
  days: [], time_start: '06:00', time_stop: '08:00',
  label: '', pulsing: false, cycle_on_min: 5, cycle_off_min: 15,
};

function SlotModal({ slot, onSave, onClose }) {
  const initial = slot
    ? { ...slot, days: JSON.parse(slot.days || '[]'), pulsing: !!slot.cycle_on_min }
    : { ...EMPTY_SLOT };
  const [form, setForm] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);

  const toggleDay = (d) => setForm(f => ({
    ...f, days: f.days.includes(d) ? f.days.filter(x => x !== d) : [...f.days, d],
  }));

  const handleSave = async () => {
    if (!form.days.length) return setErr('Wybierz przynajmniej jeden dzień');
    if (form.time_start >= form.time_stop) return setErr('Czas zakończenia musi być po czasie startu');
    setSaving(true);
    try {
      const payload = {
        days: form.days, time_start: form.time_start, time_stop: form.time_stop,
        label: form.label,
        cycle_on_min:  form.pulsing ? Number(form.cycle_on_min) : null,
        cycle_off_min: form.pulsing ? Number(form.cycle_off_min) : null,
      };
      if (form.id) payload.id = form.id;
      await onSave(payload);
      onClose();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = {
    width: '100%', padding: '10px 14px',
    background: 'var(--bg3)', border: '1px solid var(--border)',
    borderRadius: 8, color: 'var(--text)',
    fontFamily: 'var(--font-mono)', fontSize: 14,
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: 'var(--bg2)', borderRadius: 'var(--radius)',
        border: '1px solid var(--border)', padding: 24,
        width: '100%', maxWidth: 480, boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
      }}>
        <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 20 }}>
          {slot ? 'Edytuj slot' : 'Nowy slot'}
        </div>

        <div style={{ marginBottom: 16 }}>
          <Label>Nazwa (opcjonalna)</Label>
          <input value={form.label} onChange={e => setForm(f => ({ ...f, label: e.target.value }))}
            placeholder="np. Rano, Wieczór..." style={{ ...inputStyle, fontFamily: 'var(--font-main)' }} />
        </div>

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
              }}>
                {d.label}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          {[['time_start', 'Godzina start'], ['time_stop', 'Godzina stop']].map(([k, lbl]) => (
            <div key={k} style={{ flex: 1 }}>
              <Label>{lbl}</Label>
              <input type="time" value={form[k]}
                onChange={e => setForm(f => ({ ...f, [k]: e.target.value }))} style={inputStyle} />
            </div>
          ))}
        </div>

        <div style={{ marginBottom: 20 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 10 }}>
            <input type="checkbox" checked={form.pulsing}
              onChange={e => setForm(f => ({ ...f, pulsing: e.target.checked }))} />
            <span style={{ fontSize: 14, fontWeight: 600 }}>Praca pulsacyjna</span>
          </label>
          {form.pulsing ? (
            <div style={{ display: 'flex', gap: 12 }}>
              <div style={{ flex: 1 }}>
                <Label>Włączona [min]</Label>
                <input type="number" min={1} value={form.cycle_on_min}
                  onChange={e => setForm(f => ({ ...f, cycle_on_min: e.target.value }))} style={inputStyle} />
              </div>
              <div style={{ flex: 1 }}>
                <Label>Przerwa [min]</Label>
                <input type="number" min={0} value={form.cycle_off_min}
                  onChange={e => setForm(f => ({ ...f, cycle_off_min: e.target.value }))} style={inputStyle} />
              </div>
            </div>
          ) : (
            <div style={{ fontSize: 12, color: 'var(--text3)' }}>
              Pompa będzie pracować ciągle przez całe okno czasowe.
            </div>
          )}
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
      borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
      opacity: slot.enabled ? 1 : 0.6,
    }}>
      <button onClick={() => onToggle(slot)} style={{
        width: 40, height: 22, borderRadius: 11,
        background: slot.enabled ? 'var(--green)' : 'var(--bg4)',
        border: 'none', cursor: 'pointer', position: 'relative', flexShrink: 0,
      }}>
        <div style={{
          position: 'absolute', top: 3, left: slot.enabled ? 21 : 3,
          width: 16, height: 16, borderRadius: '50%', background: '#fff',
          transition: 'left 0.2s',
        }} />
      </button>

      <div style={{ flex: 1, minWidth: 0 }}>
        {slot.label && <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>{slot.label}</div>}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px', fontSize: 13, color: 'var(--text2)' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>
            {slot.time_start} – {slot.time_stop}
          </span>
          <span style={{ color: 'var(--text3)' }}>{dayLabels}</span>
        </div>
      </div>

      <span style={{
        padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
        background: slot.cycle_on_min ? 'var(--accent)22' : 'var(--bg4)',
        color: slot.cycle_on_min ? 'var(--accent)' : 'var(--text3)',
      }}>
        {slot.cycle_on_min ? `${slot.cycle_on_min}/${slot.cycle_off_min || 0} min` : 'ciągle'}
      </span>

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

// ── MAIN ──────────────────────────────────────────────────────

export default function Pump() {
  const [status, setStatus]   = useState(null);
  const [slots, setSlots]     = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal]     = useState(null);
  const [msg, setMsg]         = useState(null);
  const [deviceForm, setDeviceForm] = useState(null);

  const load = useCallback(async () => {
    try {
      const [st, sl, hi, cfg] = await Promise.all([
        api.getPumpStatus(), api.getPumpSchedule(), api.getPumpHistory(168), api.getPumpConfig(),
      ]);
      setStatus(st); setSlots(sl); setHistory(hi);
      setDeviceForm(f => f || cfg);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = setInterval(() => { if (!document.hidden) load(); }, 10000);
    return () => clearInterval(id);
  }, [load]);

  const showMsg = (type, text) => { setMsg({ type, text }); setTimeout(() => setMsg(null), 3000); };

  const handleModeChange = async (mode) => {
    try { await api.setPumpMode(mode); await load(); showMsg('ok', 'Tryb zmieniony'); }
    catch (e) { showMsg('err', e.message); }
  };

  const handleManual = async (on, minutes) => {
    try { await api.setPumpManual(on, minutes); await load(); showMsg('ok', on ? `Włączono na ${minutes} min` : 'Wyłączono'); }
    catch (e) { showMsg('err', e.message); }
  };

  const handleSaveSlot = async (form) => {
    if (form.id) await api.updatePumpSlot(form.id, form);
    else await api.addPumpSlot(form);
    await load();
    showMsg('ok', form.id ? 'Slot zaktualizowany' : 'Slot dodany');
  };

  const handleDeleteSlot = async (id) => {
    if (!window.confirm('Usunąć ten slot?')) return;
    await api.deletePumpSlot(id);
    await load();
    showMsg('ok', 'Slot usunięty');
  };

  const handleToggleSlot = async (slot) => {
    await api.updatePumpSlot(slot.id, { enabled: slot.enabled ? 0 : 1 });
    await load();
  };

  const saveDeviceConfig = async () => {
    try {
      await api.patchPumpConfig({
        pump_device_id: deviceForm.pump_device_id,
        pump_switch_dp: deviceForm.pump_switch_dp,
      });
      showMsg('ok', 'Zapisano konfigurację urządzenia');
      await load();
    } catch (e) { showMsg('err', e.message); }
  };

  if (loading) return <div style={{ textAlign: 'center', padding: 60, color: 'var(--text3)' }}>Ładowanie...</div>;

  const mode = status?.mode || 'off';
  const isOn = !!status?.current_on;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Status */}
      <Card style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: isOn ? 'var(--green)22' : 'var(--bg3)',
            border: `1px solid ${isOn ? 'var(--green)44' : 'var(--border)'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22,
          }}>
            🔄
          </div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: isOn ? 'var(--green)' : 'var(--text2)' }}>
              {isOn ? 'Pracuje' : 'Wyłączona'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>{status?.reason}</div>
          </div>
          <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Dziś łącznie
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
              {status?.today_minutes ?? 0} <span style={{ fontSize: 12, fontWeight: 400 }}>min</span>
            </div>
          </div>
        </div>
        {!status?.device_configured && (
          <div style={{
            marginTop: 12, padding: '10px 14px', borderRadius: 8,
            background: 'var(--orange)22', border: '1px solid var(--orange)44',
            color: 'var(--orange)', fontSize: 13,
          }}>
            ⚠️ Nie skonfigurowano Device ID pompy — uzupełnij poniżej, żeby sterowanie zaczęło działać.
          </div>
        )}
      </Card>

      {/* Konfiguracja urządzenia */}
      {deviceForm && (
        <Card>
          <Label>Urządzenie Tuya</Label>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <Label>Device ID</Label>
              <input value={deviceForm.pump_device_id || ''}
                onChange={e => setDeviceForm(f => ({ ...f, pump_device_id: e.target.value }))}
                style={{
                  width: '100%', padding: '10px 14px', background: 'var(--bg3)',
                  border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)',
                  fontFamily: 'var(--font-mono)', fontSize: 14,
                }} />
            </div>
            <div style={{ flex: 1, minWidth: 160 }}>
              <Label>Kod DP przełącznika</Label>
              <input value={deviceForm.pump_switch_dp || ''}
                onChange={e => setDeviceForm(f => ({ ...f, pump_switch_dp: e.target.value }))}
                style={{
                  width: '100%', padding: '10px 14px', background: 'var(--bg3)',
                  border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)',
                  fontFamily: 'var(--font-mono)', fontSize: 14,
                }} />
            </div>
            <button onClick={saveDeviceConfig} style={{
              padding: '10px 18px', borderRadius: 8, background: 'var(--accent)',
              border: 'none', color: '#fff', cursor: 'pointer',
              fontFamily: 'var(--font-main)', fontWeight: 700, fontSize: 14,
            }}>
              Zapisz
            </button>
          </div>
        </Card>
      )}

      {/* Tryb pracy */}
      <Card>
        <Label>Tryb pracy</Label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {MODE_OPTIONS.map(opt => (
            <button key={opt.id} onClick={() => handleModeChange(opt.id)} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '14px 16px', borderRadius: 'var(--radius-sm)',
              background: mode === opt.id ? 'var(--accent)15' : 'var(--bg3)',
              border: `2px solid ${mode === opt.id ? 'var(--accent)' : 'var(--border)'}`,
              cursor: 'pointer', textAlign: 'left',
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: mode === opt.id ? 'var(--accent)' : 'var(--bg4)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
                flexShrink: 0,
              }}>
                {opt.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: mode === opt.id ? 'var(--accent)' : 'var(--text)' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>{opt.desc}</div>
              </div>
              {mode === opt.id && <div style={{ color: 'var(--accent)', fontSize: 18 }}>✓</div>}
            </button>
          ))}
        </div>

        {/* Panel ręczny */}
        {mode === 'manual' && (
          <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
            {status?.manual_remaining_s > 0 ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ fontSize: 14, color: 'var(--text2)' }}>
                  Pozostało: <strong style={{ fontFamily: 'var(--font-mono)' }}>
                    {Math.floor(status.manual_remaining_s / 60)}:{String(status.manual_remaining_s % 60).padStart(2, '0')}
                  </strong>
                </div>
                <button onClick={() => handleManual(false, 5)} style={{
                  padding: '8px 16px', borderRadius: 8, background: 'var(--red)11',
                  border: '1px solid var(--red)33', color: 'var(--red)', cursor: 'pointer',
                  fontFamily: 'var(--font-main)', fontWeight: 600, fontSize: 13,
                }}>
                  Wyłącz teraz
                </button>
              </div>
            ) : (
              <div>
                <Label>Włącz na</Label>
                <div style={{ display: 'flex', gap: 8 }}>
                  {MANUAL_MINUTES.map(min => (
                    <button key={min} onClick={() => handleManual(true, min)} style={{
                      flex: 1, padding: '12px 0', borderRadius: 8,
                      background: 'var(--bg3)', border: '1px solid var(--border)',
                      color: 'var(--text)', cursor: 'pointer',
                      fontFamily: 'var(--font-main)', fontWeight: 700, fontSize: 14,
                    }}>
                      {min} min
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Harmonogram */}
      {mode === 'schedule' && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700 }}>Sloty harmonogramu</div>
              <div style={{ fontSize: 13, color: 'var(--text3)', marginTop: 2 }}>
                {slots.length} {slots.length === 1 ? 'slot' : 'slotów'}
              </div>
            </div>
            <button onClick={() => setModal('new')} style={{
              padding: '10px 18px', borderRadius: 10, background: 'var(--accent)',
              border: 'none', color: '#fff', cursor: 'pointer',
              fontFamily: 'var(--font-main)', fontWeight: 700, fontSize: 14, boxShadow: 'var(--glow)',
            }}>
              + Dodaj slot
            </button>
          </div>

          {slots.length === 0 ? (
            <Card style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text3)' }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>🔄</div>
              <div style={{ fontSize: 15, fontWeight: 600 }}>Brak slotów</div>
              <div style={{ fontSize: 13, marginTop: 4 }}>Dodaj pierwszy slot harmonogramu pompy</div>
            </Card>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {slots.map(slot => (
                <SlotRow key={slot.id} slot={slot} onEdit={s => setModal(s)}
                  onDelete={handleDeleteSlot} onToggle={handleToggleSlot} />
              ))}
            </div>
          )}
        </>
      )}

      {/* Historia */}
      <Card>
        <Label>Ostatnie uruchomienia</Label>
        {history.length === 0 ? (
          <div style={{ color: 'var(--text3)', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
            Brak zarejestrowanych uruchomień.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ color: 'var(--text3)', textAlign: 'left' }}>
                  <th style={{ padding: '6px 10px' }}>Start</th>
                  <th style={{ padding: '6px 10px' }}>Koniec</th>
                  <th style={{ padding: '6px 10px' }}>Czas trwania</th>
                  <th style={{ padding: '6px 10px' }}>Źródło</th>
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 100).map(h => (
                  <tr key={h.id} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{fmtDateTime(h.start_ts)}</td>
                    <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>
                      {h.end_ts ? fmtDateTime(h.end_ts) : <span style={{ color: 'var(--green)' }}>trwa</span>}
                    </td>
                    <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>
                      {h.duration_min != null ? `${h.duration_min} min` : '—'}
                    </td>
                    <td style={{ padding: '6px 10px', color: 'var(--text2)' }}>
                      {h.trigger === 'manual' ? '✋ ręcznie' : `📅 ${h.source_label || 'harmonogram'}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Msg msg={msg} />

      {modal && (
        <SlotModal slot={modal === 'new' ? null : modal} onSave={handleSaveSlot} onClose={() => setModal(null)} />
      )}
    </div>
  );
}
