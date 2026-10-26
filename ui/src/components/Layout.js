import React, { useState } from 'react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';

// Standalone = bez tytułu grupy, zawsze na górze/dole listy.
// Grupy porządkują zakładki tematycznie, żeby nie przewijać jednego
// długiego poziomego paska.
const NAV_GROUPS = [
  { items: [{ id: 'dashboard', label: 'Dashboard', icon: '⊡' }] },
  { title: 'Bojler', items: [
      { id: 'control',    label: 'Sterowanie',    icon: '⊕' },
      { id: 'schedule',   label: 'Harmonogram',   icon: '⊞' },
      { id: 'pvsettings', label: 'Ustawienia PV', icon: '☀' },
    ] },
  { title: 'Analityka', items: [
      { id: 'charts',   label: 'Wykresy',            icon: '◈' },
      { id: 'economy',  label: 'Ekonomia',            icon: '₿' },
      { id: 'elicznik', label: 'eLicznik',            icon: '🔌' },
      { id: 'usage',    label: 'Detekcja zużycia',    icon: '🚿' },
    ] },
  { title: 'Urządzenia', items: [
      { id: 'pump', label: 'Pompa cyrkulacyjna', icon: '🔄' },
    ] },
  { items: [{ id: 'settings', label: 'Konfiguracja', icon: '⚙' }] },
];

const ALL_ITEMS = NAV_GROUPS.flatMap(g => g.items);

function MenuIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export default function Layout({ tab, onTab, children }) {
  const { theme, toggle } = useTheme();
  const { logout } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const current = ALL_ITEMS.find(n => n.id === tab);

  const selectTab = (id) => {
    onTab(id);
    setDrawerOpen(false);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <style>{`
        @keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.6;transform:scale(.8)}}
        @keyframes drawerIn{from{transform:translateX(-100%)}to{transform:translateX(0)}}
      `}</style>

      <header style={{
        display:'flex',alignItems:'center',justifyContent:'space-between',
        padding:'0 16px',height:60,background:'var(--bg2)',
        borderBottom:'1px solid var(--border)',position:'sticky',top:0,zIndex:100,
      }}>
        <div style={{ display:'flex',alignItems:'center',gap:10 }}>
          <button onClick={() => setDrawerOpen(true)} aria-label="Menu" style={{
            width:36,height:36,borderRadius:8,
            background:'var(--bg3)',border:'1px solid var(--border)',
            color:'var(--text)',cursor:'pointer',
            display:'flex',alignItems:'center',justifyContent:'center',
          }}>
            <MenuIcon />
          </button>
          <div style={{ display:'flex',alignItems:'center',gap:10,fontWeight:700,fontSize:16 }}>
            <div style={{
              width:10,height:10,borderRadius:'50%',background:'var(--accent)',
              boxShadow:'0 0 8px var(--accent)',animation:'pulse 2s infinite',
            }}/>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {current && <span style={{ fontSize: 15 }}>{current.icon}</span>}
              {current ? current.label : 'Boiler Control'}
            </span>
          </div>
        </div>
        <div style={{ display:'flex',gap:12 }}>
          <button onClick={toggle} style={{
            background:'var(--bg3)',border:'1px solid var(--border)',
            borderRadius:8,padding:'6px 10px',cursor:'pointer',fontSize:16,
          }}>
            {theme==='dark'?'☀️':'🌙'}
          </button>
          <button onClick={logout} style={{
            background:'transparent',border:'1px solid var(--border)',
            borderRadius:8,padding:'6px 14px',cursor:'pointer',
            color:'var(--text2)',fontSize:13,fontFamily:'var(--font-main)',
          }}>
            Wyloguj
          </button>
        </div>
      </header>

      {/* Wysuwane menu boczne */}
      {drawerOpen && (
        <div
          onClick={e => e.target === e.currentTarget && setDrawerOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(2px)',
          }}
        >
          <nav style={{
            width: 260, maxWidth: '82vw', height: '100%',
            background: 'var(--bg2)', borderRight: '1px solid var(--border)',
            display: 'flex', flexDirection: 'column',
            animation: 'drawerIn 0.2s ease-out',
            boxShadow: '8px 0 24px rgba(0,0,0,0.3)',
            overflowY: 'auto',
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '16px 16px 12px',
            }}>
              <span style={{ fontWeight: 700, fontSize: 15 }}>Boiler Control</span>
              <button onClick={() => setDrawerOpen(false)} style={{
                background: 'none', border: 'none', color: 'var(--text3)',
                cursor: 'pointer', fontSize: 20, lineHeight: 1, padding: 4,
              }}>×</button>
            </div>

            {NAV_GROUPS.map((group, gi) => (
              <div key={gi} style={{ padding: '4px 10px', marginBottom: 4 }}>
                {group.title && (
                  <div style={{
                    fontSize: 11, fontWeight: 600, letterSpacing: '0.08em',
                    textTransform: 'uppercase', color: 'var(--text3)',
                    padding: '10px 10px 4px',
                  }}>
                    {group.title}
                  </div>
                )}
                {group.items.map(n => (
                  <button key={n.id} onClick={() => selectTab(n.id)} style={{
                    width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                    padding: '11px 10px', borderRadius: 8,
                    background: tab === n.id ? 'var(--accent)15' : 'none',
                    border: 'none', cursor: 'pointer', textAlign: 'left',
                    fontFamily: 'var(--font-main)', fontSize: 14,
                    fontWeight: tab === n.id ? 600 : 400,
                    color: tab === n.id ? 'var(--accent)' : 'var(--text2)',
                  }}>
                    <span style={{ fontSize: 16, width: 20, textAlign: 'center' }}>{n.icon}</span>
                    {n.label}
                  </button>
                ))}
                {!group.title && gi < NAV_GROUPS.length - 1 && (
                  <div style={{ height: 1, background: 'var(--border)', margin: '8px 6px' }} />
                )}
              </div>
            ))}
          </nav>
        </div>
      )}

      <main style={{
        flex:1,padding:'24px 20px',
        maxWidth:1200,margin:'0 auto',width:'100%',
      }}>
        {children}
      </main>
    </div>
  );
}
