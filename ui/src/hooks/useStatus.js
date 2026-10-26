import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

export function useStatus(intervalMs = 10000) {
  const [status, setStatus] = useState(null);
  const [error, setError]   = useState(null);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const data = await api.status();
      setStatus(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    const id = setInterval(fetch, intervalMs);
    return () => clearInterval(id);
  }, [fetch, intervalMs]);

  return { status, error, loading, refresh: fetch };
}
