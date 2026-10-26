import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

// ── Helpers ───────────────────────────────────────────────────

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

function Input({ label, value, onChange, type = 'text', placeholder }) {
  return (
    <div>
      {label && <Label>{label}</Label>}
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width: '100%', padding: '10px 14px',
          background: 'var(--bg3)', border: '1px solid var(--border)',
          borderRadius: 8, color: 'var(--text)',
          fontFamily: type === 'number' ? 'var(--font-mono)' : 'var(--font-main)',
          fontSize: 14,
        }}
      />
    </div>
  );
}

function Btn({ children, onClick, disabled, variant = 'primary', style }) {
  const bg = {
    primary:  'var(--accent)',
    danger:   'var(--red)',
    ghost:    'var(--bg3)',
    warning:  'var(--orange)',
  }[variant];
  const col = variant === 'ghost' ? 'var(--text2)' : '#fff';
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: '8px 16px', borderRadius: 8,
      background: disabled ? 'var(--bg4)' : bg,
      color: disabled ? 'var(--text3)' : col,
      border: variant === 'ghost' ? '1px solid var(--border)' : 'none',
      cursor: disabled ? 'not-allowed' : 'pointer',
      fontFamily: 'var(--font-main)', fontWeight: 600, fontSize: 13,
      transition: 'all 0.2s', ...style,
    }}>
      {children}
    </button>
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

// ── TABS ──────────────────────────────────────────────────────

const TABS = [
  { id: 'users',      label: 'Użytkownicy', icon: '👤' },
  { id: 'connection', label: 'Połączenie',  icon: '🔌' },
  { id: 'tuya',       label: 'Tuya',        icon: '🔋' },
  { id: 'tauron',     label: 'eLicznik',    icon: '⚡' },
  { id: 'system',     label: 'System',      icon: '⚙️' },
  { id: 'logs',       label: 'Logi',        icon: '📋' },
];

// ── USERS SECTION ─────────────────────────────────────────────

function UsersSection({ isAdmin }) {
  const [users, setUsers]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg]         = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [pwdModal, setPwdModal] = useState(null);

  const [newUser, setNewUser] = useState({ username: '', password: '', is_admin: false });
  const [newPwd, setNewPwd]   = useState('');

  const load = useCallback(async () => {
    try {
      const data = await fetch('/api/users', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('boiler_token')}` }
      }).then(r => r.json());
      if (Array.isArray(data)) setUsers(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const showMsg = (type, text) => { setMsg({ type, text }); setTimeout(() => setMsg(null), 3000); };

  const addUser = async () => {
    try {
      const res = await fetch('/api/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('boiler_token')}`,
        },
        body: JSON.stringify(newUser),
      }).then(r => r.json());
      if (res.ok) {
        showMsg('ok', 'Użytkownik dodany');
        setShowAdd(false);
        setNewUser({ username: '', password: '', is_admin: false });
        load();
      } else showMsg('err', res.error);
    } catch (e) { showMsg('err', e.message); }
  };

  const deleteUser = async (uid) => {
    if (!window.confirm('Usunąć użytkownika?')) return;
    try {
      const res = await fetch(`/api/users/${uid}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('boiler_token')}` },
      }).then(r => r.json());
      if (res.ok) { showMsg('ok', 'Użytkownik usunięty'); load(); }
      else showMsg('err', res.error);
    } catch (e) { showMsg('err', e.message); }
  };

  const changePassword = async () => {
    if (!newPwd || newPwd.length < 4) return showMsg('err', 'Hasło min. 4 znaki');
    try {
      const res = await fetch(`/api/users/${pwdModal.id}/password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('boiler_token')}`,
        },
        body: JSON.stringify({ password: newPwd }),
      }).then(r => r.json());
      if (res.ok) {
        showMsg('ok', 'Hasło zmienione');
        setPwdModal(null);
        setNewPwd('');
      } else showMsg('err', res.error);
    } catch (e) { showMsg('err', e.message); }
  };

  if (loading) return <div style={{ color: 'var(--text3)', padding: 20 }}>Ładowanie...</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* User list */}
      {users.map(u => (
        <div key={u.id} style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '12px 16px', borderRadius: 10,
          background: 'var(--bg3)', border: '1px solid var(--border)',
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            background: u.is_admin ? 'var(--accent)33' : 'var(--bg4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16,
          }}>
            {u.is_admin ? '👑' : '👤'}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{u.username}</div>
            <div style={{ fontSize: 12, color: 'var(--text3)' }}>
              {u.is_admin ? 'Administrator' : 'Użytkownik'} · od {u.created_at?.slice(0, 10)}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <Btn variant="ghost" onClick={() => { setPwdModal(u); setNewPwd(''); }}>
              🔑 Hasło
            </Btn>
            {isAdmin && (
              <Btn variant="danger" onClick={() => deleteUser(u.id)}>✕</Btn>
            )}
          </div>
        </div>
      ))}

      {/* Add user */}
      {isAdmin && !showAdd && (
        <Btn variant="primary" onClick={() => setShowAdd(true)} style={{ alignSelf: 'flex-start' }}>
          + Dodaj użytkownika
        </Btn>
      )}

      {isAdmin && showAdd && (
        <div style={{
          padding: 16, borderRadius: 10,
          background: 'var(--bg3)', border: '1px solid var(--accent)44',
          display: 'flex', flexDirection: 'column', gap: 12,
        }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>Nowy użytkownik</div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 140 }}>
              <Input label="Nazwa" value={newUser.username}
                onChange={v => setNewUser(f => ({ ...f, username: v }))}
                placeholder="nazwa użytkownika" />
            </div>
            <div style={{ flex: 1, minWidth: 140 }}>
              <Input label="Hasło" type="password" value={newUser.password}
                onChange={v => setNewUser(f => ({ ...f, password: v }))}
                placeholder="min. 4 znaki" />
            </div>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 14 }}>
            <input type="checkbox" checked={newUser.is_admin}
              onChange={e => setNewUser(f => ({ ...f, is_admin: e.target.checked }))} />
            Administrator
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn onClick={addUser}>Dodaj</Btn>
            <Btn variant="ghost" onClick={() => setShowAdd(false)}>Anuluj</Btn>
          </div>
        </div>
      )}

      <Msg msg={msg} />

      {/* Password modal */}
      {pwdModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 200,
          background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
        }} onClick={e => e.target === e.currentTarget && setPwdModal(null)}>
          <div style={{
            background: 'var(--bg2)', borderRadius: 'var(--radius)',
            border: '1px solid var(--border)', padding: 24, width: '100%', maxWidth: 360,
          }}>
            <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 16 }}>
              Zmień hasło — {pwdModal.username}
            </div>
            <Input label="Nowe hasło" type="password" value={newPwd}
              onChange={setNewPwd} placeholder="min. 4 znaki" />
            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <Btn onClick={changePassword}>Zmień hasło</Btn>
              <Btn variant="ghost" onClick={() => setPwdModal(null)}>Anuluj</Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── CONNECTION SECTION ────────────────────────────────────────

function ConnectionSection({ isAdmin }) {
  const [form, setForm]   = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);
  const [msg, setMsg]         = useState(null);
  const [changed, setChanged] = useState(false);

  useEffect(() => {
    fetch('/api/config/connection', {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('boiler_token')}` }
    }).then(r => r.json()).then(d => { setForm(d); setLoading(false); });
  }, []);

  const set = (k, v) => { setForm(f => ({ ...f, [k]: v })); setChanged(true); };

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch('/api/config/connection', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('boiler_token')}`,
        },
        body: JSON.stringify(form),
      }).then(r => r.json());
      if (res.ok) {
        setMsg({ type: 'ok', text: res.note || 'Zapisano' });
        setChanged(false);
      } else setMsg({ type: 'err', text: res.error });
    } catch (e) { setMsg({ type: 'err', text: e.message }); }
    finally { setSaving(false); setTimeout(() => setMsg(null), 4000); }
  };

  if (loading) return <div style={{ color: 'var(--text3)' }}>Ładowanie...</div>;

  const fields = [
    { key: 'boiler_ip',      label: 'IP Bojlera',             type: 'text' },
    { key: 'boiler_port',    label: 'Port Bojlera',           type: 'number' },
    { key: 'boiler_poll_s',  label: 'Polling bojlera [s]',    type: 'number' },
    { key: 'inverter_poll_s',label: 'Polling inwertera [s]',  type: 'number' },
    { key: 'hypon_station',  label: 'Hypontech Station ID',   type: 'text' },
    { key: 'hypon_user',     label: 'Hypontech użytkownik',   type: 'text' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {!isAdmin && (
        <div style={{
          padding: '10px 14px', borderRadius: 8,
          background: 'var(--orange)22', border: '1px solid var(--orange)44',
          color: 'var(--orange)', fontSize: 13,
        }}>
          ⚠️ Tylko administrator może zmieniać ustawienia połączenia
        </div>
      )}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 12,
      }}>
        {fields.map(f => (
          <Input key={f.key} label={f.label} type={f.type}
            value={form[f.key] ?? ''} onChange={v => set(f.key, v)} />
        ))}
      </div>
      {isAdmin && (
        <>
          <Btn onClick={save} disabled={!changed || saving}
            variant={changed ? 'primary' : 'ghost'}
            style={{ alignSelf: 'flex-start' }}>
            {saving ? 'Zapisuję...' : changed ? '✓ Zapisz połączenie' : 'Brak zmian'}
          </Btn>
          <div style={{
            padding: '10px 14px', borderRadius: 8,
            background: 'var(--bg3)', fontSize: 12, color: 'var(--text3)',
          }}>
            ℹ️ Zmiana IP bojlera lub portów wymaga restartu serwisu:
            <code style={{ fontFamily: 'var(--font-mono)', marginLeft: 8 }}>
              sudo systemctl restart boiler2
            </code>
          </div>
        </>
      )}
      <Msg msg={msg} />
    </div>
  );
}

// ── TUYA SECTION ──────────────────────────────────────────────

function TuyaSection({ isAdmin }) {
  const [form, setForm]       = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);
  const [msg, setMsg]         = useState(null);
  const [changed, setChanged] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await api.getTuyaConfig();
      setForm(d);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const set = (k, v) => { setForm(f => ({ ...f, [k]: v })); setChanged(true); };

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...form };
      delete payload.tuya_client_secret_set; // pole tylko do odczytu
      if (!payload.tuya_client_secret) delete payload.tuya_client_secret; // puste = nie nadpisuj
      const res = await api.patchTuyaConfig(payload);
      if (res.ok) {
        setMsg({ type: 'ok', text: res.note || 'Zapisano' });
        setChanged(false);
        load();
      } else setMsg({ type: 'err', text: res.error });
    } catch (e) { setMsg({ type: 'err', text: e.message }); }
    finally { setSaving(false); setTimeout(() => setMsg(null), 4000); }
  };

  if (loading) return <div style={{ color: 'var(--text3)' }}>Ładowanie...</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {!isAdmin && (
        <div style={{
          padding: '10px 14px', borderRadius: 8,
          background: 'var(--orange)22', border: '1px solid var(--orange)44',
          color: 'var(--orange)', fontSize: 13,
        }}>
          ⚠️ Tylko administrator może zmieniać ustawienia Tuya
        </div>
      )}

      <div style={{
        padding: '10px 14px', borderRadius: 8,
        background: 'var(--bg3)', fontSize: 12, color: 'var(--text3)',
      }}>
        🔋 Opcjonalne, realne dane mocy z inteligentnej wtyczki Tuya podłączonej
        do bojlera. Gdy włączone, zastępują szacunki oparte na zadanej mocy
        (power_w) na Dashboardzie i w Ekonomii — wszędzie oznaczone jako "źródło: Tuya".
      </div>

      <label style={{
        display: 'flex', alignItems: 'center', gap: 10, cursor: isAdmin ? 'pointer' : 'default',
        padding: '12px 16px', borderRadius: 10,
        background: form.tuya_enabled ? 'var(--green)22' : 'var(--bg3)',
        border: `1px solid ${form.tuya_enabled ? 'var(--green)44' : 'var(--border)'}`,
      }}>
        <input type="checkbox" checked={!!form.tuya_enabled} disabled={!isAdmin}
          onChange={e => set('tuya_enabled', e.target.checked)} />
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, color: form.tuya_enabled ? 'var(--green)' : 'var(--text)' }}>
            Używaj danych z Tuya
          </div>
          <div style={{ fontSize: 12, color: 'var(--text3)' }}>
            {form.tuya_enabled ? 'W użyciu — dane realne z wtyczki' : 'Nieaktywne — dane jak dotychczas (power_w)'}
          </div>
        </div>
      </label>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 12,
      }}>
        <Input label="Client ID" value={form.tuya_client_id || ''}
          onChange={v => set('tuya_client_id', v)} />
        <Input label={`Client Secret ${form.tuya_client_secret_set ? '(ustawiony — wpisz aby zmienić)' : ''}`}
          type="password" value={form.tuya_client_secret || ''}
          onChange={v => set('tuya_client_secret', v)}
          placeholder={form.tuya_client_secret_set ? '••••••••' : ''} />
        <Input label="Device ID" value={form.tuya_device_id || ''}
          onChange={v => set('tuya_device_id', v)} />
        <Input label="Region (eu/weu/us/cn/in)" value={form.tuya_api_region || ''}
          onChange={v => set('tuya_api_region', v)} />
        <Input label="Odpytywanie [s]" type="number" value={form.tuya_poll_s ?? 60}
          onChange={v => set('tuya_poll_s', v)} />
      </div>

      {isAdmin && (
        <Btn onClick={save} disabled={!changed || saving}
          variant={changed ? 'primary' : 'ghost'}
          style={{ alignSelf: 'flex-start' }}>
          {saving ? 'Zapisuję...' : changed ? '✓ Zapisz ustawienia Tuya' : 'Brak zmian'}
        </Btn>
      )}
      <Msg msg={msg} />
    </div>
  );
}

// ── TAURON eLICZNIK SECTION ───────────────────────────────────

function TauronSection({ isAdmin }) {
  const [form, setForm]       = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);
  const [msg, setMsg]         = useState(null);
  const [changed, setChanged] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await api.getTauronConfig();
      setForm(d);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const set = (k, v) => { setForm(f => ({ ...f, [k]: v })); setChanged(true); };

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...form };
      delete payload.tauron_password_set; // pole tylko do odczytu
      if (!payload.tauron_password) delete payload.tauron_password; // puste = nie nadpisuj
      const res = await api.patchTauronConfig(payload);
      if (res.ok) {
        setMsg({ type: 'ok', text: res.note || 'Zapisano' });
        setChanged(false);
        load();
      } else setMsg({ type: 'err', text: res.error });
    } catch (e) { setMsg({ type: 'err', text: e.message }); }
    finally { setSaving(false); setTimeout(() => setMsg(null), 4000); }
  };

  if (loading) return <div style={{ color: 'var(--text3)' }}>Ładowanie...</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {!isAdmin && (
        <div style={{
          padding: '10px 14px', borderRadius: 8,
          background: 'var(--orange)22', border: '1px solid var(--orange)44',
          color: 'var(--orange)', fontSize: 13,
        }}>
          ⚠️ Tylko administrator może zmieniać ustawienia eLicznika
        </div>
      )}

      <div style={{
        padding: '10px 14px', borderRadius: 8,
        background: 'var(--bg3)', fontSize: 12, color: 'var(--text3)',
      }}>
        ⚡ Dane logowania takie same jak na stronie eLicznik Taurona
        (elicznik.tauron-dystrybucja.pl). Pokazuje tylko przepływ z/do sieci
        (pobór/oddanie) i depozyt net-meteringowy — osobno od prawdziwej
        produkcji PV (Ekonomia, z inwertera).
      </div>

      <label style={{
        display: 'flex', alignItems: 'center', gap: 10, cursor: isAdmin ? 'pointer' : 'default',
        padding: '12px 16px', borderRadius: 10,
        background: form.tauron_enabled ? 'var(--green)22' : 'var(--bg3)',
        border: `1px solid ${form.tauron_enabled ? 'var(--green)44' : 'var(--border)'}`,
      }}>
        <input type="checkbox" checked={!!form.tauron_enabled} disabled={!isAdmin}
          onChange={e => set('tauron_enabled', e.target.checked)} />
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, color: form.tauron_enabled ? 'var(--green)' : 'var(--text)' }}>
            Włącz integrację eLicznika
          </div>
          <div style={{ fontSize: 12, color: 'var(--text3)' }}>
            {form.tauron_enabled ? 'Aktywna — synchronizacja w tle' : 'Nieaktywna — zakładka eLicznik ukryta'}
          </div>
        </div>
      </label>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 12,
      }}>
        <Input label="Login (e-mail)" value={form.tauron_username || ''}
          onChange={v => set('tauron_username', v)} />
        <Input label={`Hasło ${form.tauron_password_set ? '(ustawione — wpisz aby zmienić)' : ''}`}
          type="password" value={form.tauron_password || ''}
          onChange={v => set('tauron_password', v)}
          placeholder={form.tauron_password_set ? '••••••••' : ''} />
        <Input label="ID licznika (opcjonalnie)" value={form.tauron_meter_id || ''}
          onChange={v => set('tauron_meter_id', v)}
          placeholder="puste = auto-detekcja" />
        <Input label="Współczynnik zwrotu depozytu" type="number" value={form.net_metering_rate ?? 0.8}
          onChange={v => set('net_metering_rate', v)}
          placeholder="0.8 dla ≤10kWp, 0.7 dla >10kWp" />
        <Input label="Cena 1 kWh [zł] (opcjonalnie)" type="number" value={form.energy_price_pln_kwh ?? ''}
          onChange={v => set('energy_price_pln_kwh', v)}
          placeholder="do szacowania oszczędności" />
        <Input label="Synchronizacja co [h]" type="number" value={form.tauron_sync_hours ?? 6}
          onChange={v => set('tauron_sync_hours', v)} />
      </div>

      {isAdmin && (
        <Btn onClick={save} disabled={!changed || saving}
          variant={changed ? 'primary' : 'ghost'}
          style={{ alignSelf: 'flex-start' }}>
          {saving ? 'Zapisuję...' : changed ? '✓ Zapisz ustawienia eLicznika' : 'Brak zmian'}
        </Btn>
      )}
      <Msg msg={msg} />
    </div>
  );
}

// ── SYSTEM SECTION ────────────────────────────────────────────

function SystemSection() {
  const [info, setInfo] = useState(null);

  useEffect(() => {
    fetch('/api/system/info', {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('boiler_token')}` }
    }).then(r => r.json()).then(setInfo);
  }, []);

  if (!info) return <div style={{ color: 'var(--text3)' }}>Ładowanie...</div>;

  const rows = [
    ['Wersja systemu',   info.version],
    ['Czas serwera',     info.server_time?.slice(0, 19).replace('T', ' ')],
    ['Stan systemu',     info.uptime_state],
    ['Baza danych',      info.db_path],
    ['Tryb dry_run',     info.dry_run ? '✓ Aktywny (komendy nie są wysyłane)' : '○ Nieaktywny'],
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map(([label, val]) => (
        <div key={label} style={{
          display: 'flex', gap: 12,
          padding: '10px 14px', borderRadius: 8,
          background: 'var(--bg3)', border: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: 13, color: 'var(--text3)', minWidth: 160 }}>{label}</div>
          <div style={{
            fontSize: 13, fontWeight: 500,
            fontFamily: label === 'Baza danych' || label === 'Wersja systemu'
              ? 'var(--font-mono)' : 'var(--font-main)',
          }}>
            {val ?? '—'}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── LOGS SECTION ──────────────────────────────────────────────

const EVENT_COLORS = {
  STATE_CHANGE: 'var(--accent)',
  COMMAND:      'var(--green)',
  USER_ACTION:  'var(--purple)',
  COMM_ERROR:   'var(--red)',
  SYSTEM:       'var(--yellow)',
};

function LogsSection() {
  const [logs, setLogs]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState('');

  const load = useCallback(async () => {
    try {
      const data = await fetch('/api/events/recent?limit=100', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('boiler_token')}` }
      }).then(r => r.json());
      if (Array.isArray(data)) setLogs(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = filter
    ? logs.filter(l =>
        l.category?.toLowerCase().includes(filter.toLowerCase()) ||
        l.message?.toLowerCase().includes(filter.toLowerCase()) ||
        l.reason?.toLowerCase().includes(filter.toLowerCase())
      )
    : logs;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <input
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filtruj logi..."
          style={{
            flex: 1, padding: '9px 14px',
            background: 'var(--bg3)', border: '1px solid var(--border)',
            borderRadius: 8, color: 'var(--text)',
            fontFamily: 'var(--font-main)', fontSize: 13,
          }}
        />
        <Btn variant="ghost" onClick={load}>↺ Odśwież</Btn>
      </div>

      {loading ? (
        <div style={{ color: 'var(--text3)', textAlign: 'center', padding: 20 }}>Ładowanie...</div>
      ) : (
        <div style={{
          maxHeight: 500, overflowY: 'auto',
          display: 'flex', flexDirection: 'column', gap: 4,
        }}>
          {filtered.length === 0 && (
            <div style={{ color: 'var(--text3)', textAlign: 'center', padding: 20 }}>
              Brak zdarzeń
            </div>
          )}
          {filtered.map(log => {
            const col = EVENT_COLORS[log.category] || 'var(--text3)';
            return (
              <div key={log.id} style={{
                display: 'flex', gap: 10,
                padding: '8px 12px', borderRadius: 8,
                background: 'var(--bg3)', border: '1px solid var(--border)',
                fontSize: 12,
              }}>
                <div style={{
                  color: 'var(--text3)', fontFamily: 'var(--font-mono)',
                  whiteSpace: 'nowrap', minWidth: 140,
                }}>
                  {log.ts?.slice(0, 19).replace('T', ' ')}
                </div>
                <div style={{
                  minWidth: 100, fontWeight: 600, color: col,
                  whiteSpace: 'nowrap',
                }}>
                  {log.category}
                </div>
                <div style={{ color: 'var(--text2)', flex: 1 }}>
                  {log.message}
                  {log.reason && (
                    <span style={{ color: 'var(--text3)', marginLeft: 8 }}>
                      · {log.reason}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── MAIN COMPONENT ────────────────────────────────────────────

export default function Settings() {
  const [tab, setTab]     = useState('users');
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    // Sprawdź czy zalogowany user jest adminem
    fetch('/api/users', {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('boiler_token')}` }
    }).then(r => {
      if (r.ok) setIsAdmin(true);
    }).catch(() => {});
  }, []);

  const content = {
    users:      <UsersSection isAdmin={isAdmin} />,
    connection: <ConnectionSection isAdmin={isAdmin} />,
    tuya:       <TuyaSection isAdmin={isAdmin} />,
    tauron:     <TauronSection isAdmin={isAdmin} />,
    system:     <SystemSection />,
    logs:       <LogsSection />,
  }[tab];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Sub-tabs */}
      <div style={{
        display: 'flex', gap: 6, flexWrap: 'wrap',
        borderBottom: '1px solid var(--border)', paddingBottom: 0,
      }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '10px 16px',
            background: 'none', border: 'none', cursor: 'pointer',
            fontFamily: 'var(--font-main)', fontSize: 13,
            fontWeight: tab === t.id ? 600 : 400,
            color: tab === t.id ? 'var(--accent)' : 'var(--text2)',
            borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
            marginBottom: -1,
            display: 'flex', alignItems: 'center', gap: 6,
            transition: 'all 0.2s',
          }}>
            <span>{t.icon}</span> {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <Card>
        <SectionTitle
          icon={TABS.find(t => t.id === tab)?.icon}
          title={TABS.find(t => t.id === tab)?.label}
        />
        {content}
      </Card>
    </div>
  );
}
