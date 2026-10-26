import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

export default function Login() {
  const { login } = useAuth();
  const { theme, toggle } = useTheme();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);

  const handle = async (e) => {
    e.preventDefault();
    setLoading(true); setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError('Nieprawidłowe dane logowania');
    } finally {
      setLoading(false);
    }
  };

  const inp = {
    width: '100%', padding: '13px 16px',
    background: 'var(--bg3)', border: '1px solid var(--border)',
    borderRadius: 10, color: 'var(--text)',
    fontFamily: 'var(--font-main)', fontSize: 15,
    outline: 'none', transition: 'border-color 0.2s',
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg)', padding: 20,
      position: 'relative',
    }}>
      <button onClick={toggle} style={{
        position: 'absolute', top: 20, right: 20,
        background: 'var(--bg2)', border: '1px solid var(--border)',
        borderRadius: 8, padding: '6px 10px', cursor: 'pointer',
        fontSize: 16,
      }}>
        {theme === 'dark' ? '☀️' : '🌙'}
      </button>

      <div style={{
        width: '100%', maxWidth: 380,
        background: 'var(--bg2)', borderRadius: 'var(--radius)',
        border: '1px solid var(--border)',
        padding: '40px 32px',
        boxShadow: 'var(--card-shadow)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 16,
            background: 'var(--accent)22', border: '1px solid var(--accent)44',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 24, margin: '0 auto 16px',
          }}>
            🌡️
          </div>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.5px' }}>
            Boiler Control
          </div>
          <div style={{ fontSize: 13, color: 'var(--text3)', marginTop: 4 }}>
            Zaloguj się aby kontynuować
          </div>
        </div>

        <form onSubmit={handle} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text3)', marginBottom: 6 }}>
              UŻYTKOWNIK
            </div>
            <input
              style={inp} type="text" value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="admin" autoComplete="username"
            />
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text3)', marginBottom: 6 }}>
              HASŁO
            </div>
            <input
              style={inp} type="password" value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••" autoComplete="current-password"
            />
          </div>

          {error && (
            <div style={{
              padding: '10px 14px', borderRadius: 8,
              background: 'var(--red)22', color: 'var(--red)',
              fontSize: 13, border: '1px solid var(--red)44',
            }}>
              ⚠️ {error}
            </div>
          )}

          <button type="submit" disabled={loading} style={{
            padding: '14px', borderRadius: 10, marginTop: 4,
            background: 'var(--accent)', border: 'none',
            color: '#fff', cursor: loading ? 'wait' : 'pointer',
            fontFamily: 'var(--font-main)', fontWeight: 700, fontSize: 15,
            boxShadow: 'var(--glow)', transition: 'opacity 0.2s',
            opacity: loading ? 0.7 : 1,
          }}>
            {loading ? 'Logowanie...' : 'Zaloguj się'}
          </button>
        </form>
      </div>
    </div>
  );
}
