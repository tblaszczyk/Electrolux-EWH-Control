import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../api/client';
import { useStatus } from '../hooks/useStatus';

const POWER_LEVELS = [700, 1300, 2000];
const POWER_LABELS = { 700: 'Niski', 1300: 'Średni', 2000: 'Wysoki' };
const TEMPS = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70];

function tempColor(t) {
  if (t <= 30) return '#38bdf8';
  if (t <= 45) return '#22c55e';
  if (t <= 55) return '#eab308';
  if (t <= 65) return '#f97316';
  return '#ef4444';
}

function Card({ children, style }) {
  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', padding: '20px',
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

function Section({ title, children, disabled }) {
  return (
    <div style={{
      opacity: disabled ? 0.4 : 1,
      pointerEvents: disabled ? 'none' : 'auto',
      transition: 'opacity 0.3s',
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text2)', marginBottom: 12 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

export default function Control() {
  const { status, loading, refresh } = useStatus(10000);

  const [mode, setMode]         = useState('AUTO');
  const [temp, setTemp]         = useState(55);
  const [power, setPower]       = useState(1300);
  const [editing, setEditing]   = useState(false);
  const [saving, setSaving]     = useState(false);
  const [msg, setMsg]           = useState(null);
  const editTimerRef            = useRef(null);

  // Sync with status
  useEffect(() => {
    if (!status) return;
    setMode(status.mode || 'AUTO');
    if (status.manual_temp) setTemp(status.manual_temp);
    if (status.manual_power_limit) setPower(status.manual_power_limit);
  }, [status]);

  // Edit button — deactivates after 3s inactivity
  const startEdit = useCallback(() => {
    setEditing(true);
    clearTimeout(editTimerRef.current);
    editTimerRef.current = setTimeout(() => {
      setEditing(false);
    }, 3000);
  }, []);

  const resetEditTimer = useCallback(() => {
    if (!editing) return;
    clearTimeout(editTimerRef.current);
    editTimerRef.current = setTimeout(() => setEditing(false), 3000);
  }, [editing]);

  useEffect(() => () => clearTimeout(editTimerRef.current), []);

  const switchMode = async (newMode) => {
    setSaving(true);
    try {
      if (newMode === 'MANUAL') {
        await api.setManual(temp, power);
        setMode('MANUAL');
        setMsg({ type: "ok", text: "Tryb manualny aktywny" });
      } else {
        await api.setAuto();
        setMode('AUTO');
        setMsg({ type: 'ok', text: 'Tryb automatyczny aktywny' });
      }
      refresh(); setTimeout(refresh, 3000); setTimeout(refresh, 7000); setTimeout(refresh, 12000);
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setSaving(false);
      setTimeout(() => setMsg(null), 3000);
    }
  };

  const applyManual = async () => {
    setSaving(true);
    try {
      await api.setManual(temp, power);
      setEditing(false);
      setMsg({ type: 'ok', text: `Ustawiono: ${temp}°C, ${power}W` });
      refresh();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setSaving(false);
      setTimeout(() => setMsg(null), 3000);
    }
  };

  const tempIdx  = TEMPS.indexOf(temp);
  const tempPct  = (tempIdx / (TEMPS.length - 1)) * 100;
  const color    = tempColor(temp);

  if (loading) return (
    <div style={{ textAlign: 'center', padding: 60, color: 'var(--text3)' }}>
      Ładowanie...
    </div>
  );

  const isManual = mode === 'MANUAL';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 560 }}>

      {/* Mode toggle */}
      <Card>
        <Label>Tryb sterowania</Label>
        <div style={{ display: 'flex', gap: 0, borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border)' }}>
          {['AUTO', 'MANUAL'].map(m => (
            <button key={m} onClick={() => switchMode(m)} disabled={saving} style={{
              flex: 1, padding: '12px 0',
              background: mode === m
                ? m === 'MANUAL' ? 'var(--purple)' : 'var(--accent)'
                : 'var(--bg3)',
              color: mode === m ? '#fff' : 'var(--text2)',
              border: 'none', cursor: 'pointer',
              fontFamily: 'var(--font-main)', fontWeight: 600, fontSize: 14,
              transition: 'all 0.2s',
            }}>
              {m === 'AUTO' ? '⚡ Automatyczny' : '✋ Ręczny'}
            </button>
          ))}
        </div>
        {!isManual && (
          <div style={{
            marginTop: 12, padding: '10px 14px', borderRadius: 8,
            background: 'var(--bg3)', fontSize: 13, color: 'var(--text2)',
          }}>
            Sterowanie PV i harmonogram są aktywne. Wybór temperatury i mocy dostępny tylko w trybie ręcznym.
          </div>
        )}
      </Card>

      {/* Temperature */}
      <Card style={{ opacity: isManual ? 1 : 0.45, pointerEvents: isManual ? 'auto' : 'none', transition: 'opacity 0.3s' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Label>Temperatura docelowa</Label>
          <button
            onClick={startEdit}
            style={{
              padding: '5px 14px', borderRadius: 8,
              background: editing ? 'var(--accent)' : 'var(--bg3)',
              color: editing ? '#fff' : 'var(--text2)',
              border: `1px solid ${editing ? 'var(--accent)' : 'var(--border)'}`,
              cursor: 'pointer', fontFamily: 'var(--font-main)',
              fontSize: 12, fontWeight: 600, transition: 'all 0.2s',
            }}
          >
            {editing ? '● Edytowanie' : '✎ Edytuj'}
          </button>
        </div>

        {/* Big temp display */}
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <div style={{
            fontSize: 64, fontWeight: 800,
            color, fontFamily: 'var(--font-mono)',
            lineHeight: 1, transition: 'color 0.3s',
          }}>
            {temp}°
          </div>
          <div style={{ fontSize: 13, color: 'var(--text3)' }}>Celsjusz</div>
        </div>

        {/* Color slider */}
        <div style={{ position: 'relative', padding: '0 4px' }}
          onClick={resetEditTimer}
          onChange={resetEditTimer}
        >
          <div style={{
            height: 12, borderRadius: 6, marginBottom: 12,
            background: 'linear-gradient(to right, #38bdf8, #22c55e, #eab308, #f97316, #ef4444)',
            position: 'relative',
          }}>
            <div style={{
              position: 'absolute',
              left: `calc(${tempPct}% - 10px)`,
              top: -4, width: 20, height: 20,
              borderRadius: '50%',
              background: color,
              border: '3px solid var(--bg2)',
              boxShadow: `0 0 10px ${color}`,
              transition: 'left 0.15s, background 0.3s',
              pointerEvents: 'none',
            }} />
          </div>
          <input
            type="range"
            min={0} max={TEMPS.length - 1}
            value={tempIdx === -1 ? 0 : tempIdx}
            onChange={e => {
              if (!editing) return;
              setTemp(TEMPS[+e.target.value]);
              resetEditTimer();
            }}
            disabled={!editing}
            style={{
              position: 'absolute', top: 0, left: 4, right: 4,
              width: 'calc(100% - 8px)',
              opacity: 0, cursor: editing ? 'pointer' : 'not-allowed',
              height: 20, margin: 0,
            }}
          />
          {/* Temp labels */}
          <div style={{
            display: 'flex', justifyContent: 'space-between',
            fontSize: 11, color: 'var(--text3)', marginTop: 4,
          }}>
            <span>20°C</span>
            <span>45°C</span>
            <span>70°C</span>
          </div>
        </div>
      </Card>

      {/* Power */}
      <Card style={{ opacity: isManual ? 1 : 0.45, pointerEvents: isManual ? 'auto' : 'none', transition: 'opacity 0.3s' }}>
        <Label>Limit mocy grzania</Label>
        <div style={{ display: 'flex', gap: 10 }}>
          {POWER_LEVELS.map(w => {
            const active = power === w;
            const c = w === 700 ? 'var(--yellow)' : w === 1300 ? 'var(--orange)' : 'var(--red)';
            return (
              <button
                key={w}
                onClick={() => { if (editing) { setPower(w); resetEditTimer(); } }}
                disabled={!editing}
                style={{
                  flex: 1, padding: '14px 0',
                  borderRadius: 10,
                  background: active ? `${c}22` : 'var(--bg3)',
                  border: `2px solid ${active ? c : 'var(--border)'}`,
                  color: active ? c : 'var(--text2)',
                  cursor: editing ? 'pointer' : 'not-allowed',
                  fontFamily: 'var(--font-main)',
                  transition: 'all 0.2s',
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', gap: 4,
                }}
              >
                <div style={{ fontWeight: 700, fontSize: 16 }}>{w}W</div>
                <div style={{ fontSize: 11, opacity: 0.7 }}>{POWER_LABELS[w]}</div>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Apply button */}
      {isManual && (
        <button
          onClick={applyManual}
          disabled={!editing || saving}
          style={{
            padding: '15px', borderRadius: 'var(--radius)',
            background: editing ? 'var(--accent)' : 'var(--bg3)',
            color: editing ? '#fff' : 'var(--text3)',
            border: 'none', cursor: editing ? 'pointer' : 'not-allowed',
            fontFamily: 'var(--font-main)', fontWeight: 700, fontSize: 16,
            transition: 'all 0.2s',
            boxShadow: editing ? 'var(--glow)' : 'none',
          }}
        >
          {saving ? 'Zapisywanie...' : '✓ Zastosuj ustawienia'}
        </button>
      )}

      {/* Message */}
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
