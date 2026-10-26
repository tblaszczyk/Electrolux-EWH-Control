import React, { useState, useEffect, useCallback } from 'react';
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { api } from '../api/client';

// ── Helpers ───────────────────────────────────────────────────

const MONTHS_PL = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];

function fmtMonth(period) {
  if (!period) return '';
  const [y, m] = period.split('-');
  return `${MONTHS_PL[+m - 1]} ${y.slice(2)}`;
}

function fmtDay(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return `${d.getDate().toString().padStart(2,'0')}.${(d.getMonth()+1).toString().padStart(2,'0')}`;
}

function fmtKwh(n, digits = 1) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return Number(n).toLocaleString('pl-PL', { maximumFractionDigits: digits });
}

function fmtPln(n) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return Number(n).toLocaleString('pl-PL', { style: 'currency', currency: 'PLN', maximumFractionDigits: 0 });
}

function Card({ children, style }) {
  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius, 16px)', padding: 20, boxShadow: 'var(--card-shadow)', ...style,
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
      <div style={{ fontSize: 24, fontWeight: 800, color, fontFamily: 'var(--font-mono)', lineHeight: 1 }}>
        {value}
        {unit && <span style={{ fontSize: 13, fontWeight: 400, marginLeft: 4, color: 'var(--text2)' }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 5 }}>{sub}</div>}
    </div>
  );
}

function MonthlyTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const imp = payload.find(p => p.dataKey === 'imported_kwh')?.value || 0;
  const exp = payload.find(p => p.dataKey === 'exported_kwh')?.value || 0;
  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10,
      padding: '10px 14px', fontSize: 12, boxShadow: '0 8px 24px rgba(0,0,0,0.4)', minWidth: 160,
    }}>
      <div style={{ color: 'var(--text3)', marginBottom: 8, fontFamily: 'var(--font-mono)' }}>{label}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: '#475569', marginBottom: 4 }}>
        <span>⚡ Pobór</span><strong>{fmtKwh(imp)} kWh</strong>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: '#22c55e' }}>
        <span>☀ Oddanie</span><strong>{fmtKwh(exp)} kWh</strong>
      </div>
    </div>
  );
}

function ExpiryBars({ expiringByMonth }) {
  const entries = Object.entries(expiringByMonth || {}).sort((a, b) => a[0].localeCompare(b[0]));
  if (entries.length === 0) {
    return <div style={{ color: 'var(--text3)', fontSize: 13 }}>Brak zaplanowanych wygaśnięć w widocznym horyzoncie (ok. 13 mies.).</div>;
  }
  const max = Math.max(...entries.map(([, v]) => v));
  const today = new Date();
  const soonCutoff = new Date(today.getTime() + 90 * 86400000);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {entries.map(([period, kwh]) => {
        const isSoon = new Date(`${period}-01`) <= soonCutoff;
        return (
          <div key={period} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 56, fontSize: 12, color: 'var(--text3)', fontFamily: 'var(--font-mono)' }}>
              {fmtMonth(period)}
            </div>
            <div style={{ flex: 1, height: 10, borderRadius: 5, background: 'var(--bg4)', overflow: 'hidden' }}>
              <div style={{
                width: `${(kwh / max) * 100}%`, height: '100%',
                background: isSoon ? 'var(--orange)' : '#22c55e',
                transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1)',
              }} />
            </div>
            <div style={{ width: 80, textAlign: 'right', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
              {fmtKwh(kwh)} kWh
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── MAIN ──────────────────────────────────────────────────────

export default function ELicznik() {
  const [configured, setConfigured] = useState(true);
  const [summary, setSummary]       = useState(null);
  const [daily, setDaily]           = useState([]);
  const [monthly, setMonthly]       = useState([]);
  const [loading, setLoading]       = useState(true);
  const [syncing, setSyncing]       = useState(false);
  const [error, setError]           = useState(null);
  const [view, setView]             = useState('monthly'); // monthly | daily

  const load = useCallback(async () => {
    try {
      const cfg = await api.getEnergyConfigured();
      setConfigured(cfg.configured);
      if (!cfg.configured) { setLoading(false); return; }
      const year = new Date().getFullYear();
      const [s, d, m] = await Promise.all([
        api.getEnergySummary(),
        api.getEnergyDaily(90),
        api.getEnergyMonthly(year - 1),
      ]);
      setSummary(s); setDaily(d); setMonthly(m);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onSync = async () => {
    setSyncing(true);
    try {
      await api.syncEnergy();
      setTimeout(load, 3000);
    } catch (e) {
      setError(e.message);
    } finally {
      setTimeout(() => setSyncing(false), 3000);
    }
  };

  if (loading) {
    return (
      <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)' }}>
        Ładowanie...
      </div>
    );
  }

  if (!configured) {
    return (
      <Card>
        <Label>eLicznik Tauron nieskonfigurowany</Label>
        <p style={{ fontSize: 14, color: 'var(--text2)' }}>
          Włącz integrację i podaj dane logowania w <strong>Ustawienia → eLicznik</strong>.
          Potrzebny jest login i hasło takie samo jak na stronie eLicznik Taurona.
        </p>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <div style={{ color: 'var(--red)' }}>⚠ {error}</div>
      </Card>
    );
  }

  const { deposit, projection } = summary;
  const bilansYtd = projection.actual_export_ytd_kwh * deposit.rate - projection.actual_import_ytd_kwh;
  const willBuy = projection.projected_grid_purchase_kwh > 0;

  const chartData = view === 'monthly' ? monthly : daily;
  const xKey = view === 'monthly' ? 'period' : 'date';
  const fmtX = view === 'monthly' ? fmtMonth : fmtDay;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Header / sync */}
      <Card style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ fontSize: 12, color: 'var(--text3)' }}>
            🔌 {summary.meter_label || summary.meter_id} · taryfa {summary.tariff}
          </div>
          <button onClick={onSync} disabled={syncing} style={{
            marginLeft: 'auto', padding: '6px 14px', borderRadius: 8,
            background: 'var(--bg3)', border: '1px solid var(--border)',
            color: 'var(--text2)', cursor: syncing ? 'not-allowed' : 'pointer', fontSize: 13,
            fontFamily: 'var(--font-main)',
          }}>
            {syncing ? '↻ Synchronizuję...' : '↺ Synchronizuj teraz'}
          </button>
        </div>
      </Card>

      {/* Do wykorzystania do końca roku */}
      <Card style={{ padding: '16px 18px' }}>
        <Label>Do wykorzystania do końca {projection.year} roku</Label>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 34, fontWeight: 800, color: 'var(--accent)', fontFamily: 'var(--font-mono)', lineHeight: 1 }}>
            {fmtKwh(projection.available_until_year_end_kwh, 0)}
          </span>
          <span style={{ fontSize: 14, color: 'var(--text3)' }}>kWh</span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--text2)', marginTop: 10, lineHeight: 1.7 }}>
          teraz w depozycie <strong>{fmtKwh(projection.balance_now_kwh, 0)}</strong>
          {' '}+ prognozowane oddanie do końca roku po {Math.round(deposit.rate * 100)}% <strong>{fmtKwh(projection.projected_new_credit_kwh, 0)}</strong>
          {projection.projected_expiring_unused_kwh > 0 && <> − przepadnie <strong>{fmtKwh(projection.projected_expiring_unused_kwh, 0)}</strong></>}
          <br />
          Prognozowany pobór do końca roku: <strong>{fmtKwh(projection.projected_rest_of_year_import_kwh, 0)} kWh</strong>
          {' → '}
          {willBuy
            ? <strong style={{ color: 'var(--red)' }}>zabraknie {fmtKwh(projection.projected_grid_purchase_kwh, 0)} kWh (do dokupienia)</strong>
            : <strong style={{ color: '#22c55e' }}>zostanie {fmtKwh(projection.projected_deposit_end_of_year_kwh, 0)} kWh na przyszły rok</strong>}
        </div>
      </Card>

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
        <SummaryCard label="Pobór z sieci (YTD)" value={fmtKwh(projection.actual_import_ytd_kwh, 0)} unit="kWh" color="#475569" sub="po bilansowaniu godzinowym" />
        <SummaryCard label="Oddanie do sieci (YTD)" value={fmtKwh(projection.actual_export_ytd_kwh, 0)} unit="kWh" color="#22c55e" sub="po bilansowaniu godzinowym" />
        <SummaryCard
          label={`Bilans YTD (oddanie × ${Math.round(deposit.rate * 100)}%)`} value={`${bilansYtd >= 0 ? '+' : ''}${fmtKwh(bilansYtd, 0)}`} unit="kWh"
          color={bilansYtd >= 0 ? '#22c55e' : 'var(--red)'}
          sub={bilansYtd >= 0 ? 'nadwyżka do odebrania' : 'niedobór'}
        />
        <SummaryCard
          label="Ważny depozyt" value={fmtKwh(deposit.current_balance_kwh, 0)} unit="kWh"
          color="var(--accent)" sub={`już po przeliczeniu ${Math.round(deposit.rate * 100)}% (do odebrania)`}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
        <SummaryCard
          label="Wygasa w 30 dni" value={fmtKwh(deposit.expiring_within_30d_kwh, 0)} unit="kWh"
          sub="o ile wcześniej nie zużyjesz"
          color={deposit.expiring_within_30d_kwh > 0 ? 'var(--orange)' : 'var(--text3)'}
        />
        <SummaryCard
          label="Wygasa w 90 dni" value={fmtKwh(deposit.expiring_within_90d_kwh, 0)} unit="kWh"
          sub="o ile wcześniej nie zużyjesz"
          color={deposit.expiring_within_90d_kwh > 0 ? 'var(--orange)' : 'var(--text3)'}
        />
        <SummaryCard
          label="Prognoza do końca roku"
          value={`${willBuy ? '−' : '+'}${fmtKwh(willBuy ? projection.projected_grid_purchase_kwh : projection.projected_deposit_end_of_year_kwh, 0)}`}
          unit="kWh"
          color={willBuy ? 'var(--red)' : '#22c55e'}
          sub={willBuy ? 'zabraknie depozytu — pobór do dokupienia' : (projection.projected_expiring_unused_kwh > 0 ? `depozyt na koniec roku (przepadnie ${fmtKwh(projection.projected_expiring_unused_kwh, 0)} kWh)` : 'depozyt na koniec roku')}
        />
        <SummaryCard
          label="Oszczędność z depozytu"
          value={summary.price_pln_kwh !== null ? fmtPln(summary.savings_from_deposit_pln) : '—'}
          color="var(--green)"
          sub={summary.price_pln_kwh === null ? 'ustaw cenę kWh w Ustawieniach' : `przy ${fmtKwh(summary.price_pln_kwh, 2)} zł/kWh`}
        />
      </div>

      {/* Chart */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Label>{view === 'monthly' ? 'Bilans miesięczny' : 'Ostatnie 90 dni'}</Label>
          <div style={{ display: 'flex', gap: 4 }}>
            {[['monthly','Miesięcznie'],['daily','Dziennie']].map(([v,l]) => (
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

        {chartData.length === 0 ? (
          <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--text3)', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 32 }}>📊</div>
            <div>Brak danych — kliknij "Synchronizuj teraz"</div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
              <XAxis
                dataKey={xKey} tickFormatter={fmtX} stroke="var(--text3)"
                tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                tickLine={false} minTickGap={view === 'daily' ? 20 : 5}
              />
              <YAxis
                stroke="var(--text3)" tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                tickLine={false} width={50}
                label={{ value: 'kWh', angle: -90, position: 'insideLeft', fill: 'var(--text3)', fontSize: 11, dy: 20 }}
              />
              <Tooltip content={<MonthlyTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 12, fontFamily: 'var(--font-main)', paddingTop: 8 }}
                formatter={(v) => v === 'imported_kwh' ? '⚡ Pobór z sieci' : '☀ Oddanie do sieci'}
              />
              {view === 'monthly' ? (
                <>
                  <Bar dataKey="imported_kwh" name="imported_kwh" fill="#475569" radius={[4,4,0,0]} maxBarSize={28} />
                  <Bar dataKey="exported_kwh" name="exported_kwh" fill="#22c55e" radius={[4,4,0,0]} maxBarSize={28} />
                </>
              ) : (
                <>
                  <Line type="monotone" dataKey="imported_kwh" name="imported_kwh" stroke="#475569" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="exported_kwh" name="exported_kwh" stroke="#22c55e" strokeWidth={2} dot={false} />
                </>
              )}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Deposit + projection */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <Card>
          <Label>Kiedy wygasa depozyt</Label>
          <ExpiryBars expiringByMonth={deposit.expiring_by_month} />
          <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 14, lineHeight: 1.6 }}>
            Ostatnie 12 miesięcy (od {deposit.window_from}); depozyt liczony od początku historii ({summary.history_from}).{' '}
            Pokryte opustem: <strong style={{ color: 'var(--text2)' }}>{fmtKwh(deposit.covered_by_deposit_kwh, 0)} kWh</strong> ·{' '}
            do zapłaty (ponad opust): <strong style={{ color: 'var(--text2)' }}>{fmtKwh(deposit.purchased_from_grid_kwh, 0)} kWh</strong> ·{' '}
            wygasło: <strong style={{ color: 'var(--text2)' }}>{fmtKwh(deposit.expired_total_kwh, 0)} kWh</strong>.
          </div>
        </Card>

        <Card>
          <Label>Prognoza do końca roku</Label>
          <p style={{ fontSize: 13, color: 'var(--text2)', marginTop: 0, marginBottom: 14 }}>
            Na bazie średniej z lat: {projection.history_years_available.join(', ') || 'brak historii'}.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <Label>Oddanie (reszta roku)</Label>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#22c55e', fontFamily: 'var(--font-mono)' }}>
                {fmtKwh(projection.projected_rest_of_year_export_kwh, 0)} kWh
              </div>
            </div>
            <div>
              <Label>Pobór (reszta roku)</Label>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#475569', fontFamily: 'var(--font-mono)' }}>
                {fmtKwh(projection.projected_rest_of_year_import_kwh, 0)} kWh
              </div>
            </div>
            <div>
              <Label>Oddanie (cały rok)</Label>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#22c55e', fontFamily: 'var(--font-mono)' }}>
                {fmtKwh(projection.projected_year_total_export_kwh, 0)} kWh
              </div>
            </div>
            <div>
              <Label>Pobór (cały rok)</Label>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#475569', fontFamily: 'var(--font-mono)' }}>
                {fmtKwh(projection.projected_year_total_import_kwh, 0)} kWh
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Info */}
      <div style={{
        padding: '10px 14px', borderRadius: 10, background: 'var(--bg3)',
        fontSize: 12, color: 'var(--text3)', border: '1px solid var(--border)',
      }}>
        💡 Rozliczenie jak w art. 4 ustawy o OZE (opust {Math.round(deposit.rate * 100)}%): pobór i oddanie są
        bilansowane <strong>godzinowo</strong> (różnice między fazami znoszą się 1:1), dopiero nadwyżka oddania
        tworzy depozyt w wysokości {Math.round(deposit.rate * 100)}%. Data wprowadzenia = ostatni dzień miesiąca oddania,
        depozyt ważny 12 miesięcy od tej daty, zużywany od najstarszego. Okres rozliczeniowy przyjęty jako miesiąc.
        eLicznik pokazuje tylko przepływ z/do sieci, nie całkowitą produkcję ani zużycie domu (to w zakładce Ekonomia).
      </div>
    </div>
  );
}
