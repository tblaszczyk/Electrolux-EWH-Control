const BASE = '';

let _token = localStorage.getItem('boiler_token') || '';

export function setToken(t) {
  _token = t;
  localStorage.setItem('boiler_token', t);
}

export function clearToken() {
  _token = '';
  localStorage.removeItem('boiler_token');
}

export function getToken() { return _token; }

async function req(method, path, body) {
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ..._token ? { 'Authorization': `Bearer ${_token}` } : {},
    },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  if (res.status === 401) {
    clearToken();
    window.location.reload();
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  login:  (username, password) => req('POST', '/api/login', { username, password }),
  logout: () => req('POST', '/api/logout'),
  status: () => req('GET', '/api/status'),
  ping:   () => req('GET', '/api/ping'),

  setManual: (temp, power_limit) => req('POST', '/api/control/manual', { temp, power_limit }),
  setAuto:   () => req('POST', '/api/control/auto'),
  setIdle:   (mode) => req('POST', '/api/control/idle_mode', { mode }),

  getSchedule:    () => req('GET', '/api/schedule'),
  addSlot:        (slot) => req('POST', '/api/schedule', slot),
  updateSlot:     (id, slot) => req('PUT', `/api/schedule/${id}`, slot),
  deleteSlot:     (id) => req('DELETE', `/api/schedule/${id}`),

  getConfig:    () => req('GET', '/api/config'),
  patchConfig:  (data) => req('PATCH', '/api/config', data),
};

// Dodaj do obiektu api
Object.assign(api, {
  togglePower: (enabled) => req('POST', '/api/control/power', { enabled }),
});

Object.assign(api, {
  getUsageEvents:  (hours = 168, category) =>
    req('GET', `/api/usage/events?hours=${hours}${category ? `&category=${category}` : ''}`),
  getUsageSummary: (range = '30d') => req('GET', `/api/usage/summary?range=${range}`),
});

Object.assign(api, {
  getTuyaConfig:   () => req('GET', '/api/config/tuya'),
  patchTuyaConfig: (data) => req('PATCH', '/api/config/tuya', data),
});

Object.assign(api, {
  getPumpStatus:    () => req('GET', '/api/pump/status'),
  setPumpMode:      (mode) => req('POST', '/api/pump/mode', { mode }),
  setPumpManual:    (on, minutes) => req('POST', '/api/pump/manual', { on, minutes }),
  getPumpConfig:    () => req('GET', '/api/pump/config'),
  patchPumpConfig:  (data) => req('PATCH', '/api/pump/config', data),
  getPumpSchedule:  () => req('GET', '/api/pump/schedule'),
  addPumpSlot:      (slot) => req('POST', '/api/pump/schedule', slot),
  updatePumpSlot:   (id, slot) => req('PUT', `/api/pump/schedule/${id}`, slot),
  deletePumpSlot:   (id) => req('DELETE', `/api/pump/schedule/${id}`),
  getPumpHistory:   (hours = 168) => req('GET', `/api/pump/history?hours=${hours}`),
});

Object.assign(api, {
  getEnergyConfigured: () => req('GET', '/api/energy/configured'),
  getEnergySummary:    () => req('GET', '/api/energy/summary'),
  getEnergyDaily:      (days = 90) => req('GET', `/api/energy/daily?days=${days}`),
  getEnergyMonthly:    (fromYear) => req('GET', `/api/energy/monthly${fromYear ? `?fromYear=${fromYear}` : ''}`),
  syncEnergy:          () => req('POST', '/api/energy/sync'),
  getTauronConfig:     () => req('GET', '/api/config/tauron'),
  patchTauronConfig:   (data) => req('PATCH', '/api/config/tauron', data),
});
