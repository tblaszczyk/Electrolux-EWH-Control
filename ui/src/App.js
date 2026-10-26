import React, { useState } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Control from './pages/Control';
import Schedule from './pages/Schedule';
import PVSettings from './pages/PVSettings';
import Charts from './pages/Charts';
import Economy from './pages/Economy';
import ELicznik from './pages/ELicznik';
import UsageDetection from './pages/UsageDetection';
import Pump from './pages/Pump';
import Settings from './pages/Settings';

function AppContent() {
  const { authed } = useAuth();
  const [tab, setTab] = useState('dashboard');
  if (!authed) return <Login />;
  const page = {
    dashboard:  <Dashboard />,
    control:    <Control />,
    schedule:   <Schedule />,
    pvsettings: <PVSettings />,
    charts:     <Charts />,
    economy:    <Economy />,
    elicznik:   <ELicznik />,
    usage:      <UsageDetection />,
    pump:       <Pump />,
    settings:   <Settings />,
  }[tab] || <Dashboard />;
  return <Layout tab={tab} onTab={setTab}>{page}</Layout>;
}

export default function App() {
  return (
    <ThemeProvider><AuthProvider><AppContent /></AuthProvider></ThemeProvider>
  );
}
