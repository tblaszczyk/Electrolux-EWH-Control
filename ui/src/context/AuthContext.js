import React, { createContext, useContext, useState } from 'react';
import { setToken, clearToken, getToken, api } from '../api/client';

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [authed, setAuthed] = useState(!!getToken());

  const login = async (username, password) => {
    const data = await api.login(username, password);
    setToken(data.token);
    setAuthed(true);
  };

  const logout = async () => {
    try { await api.logout(); } catch {}
    clearToken();
    setAuthed(false);
  };

  return (
    <AuthContext.Provider value={{ authed, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
