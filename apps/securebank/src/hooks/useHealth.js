import { useEffect, useState } from 'react';
import { getHealth } from '../services/api.js';
export function useHealth() {
  const [status, setStatus] = useState('Checking backend…');
  useEffect(() => { let active = true; getHealth().then(() => { if (active) setStatus('Backend connected'); }).catch(() => { if (active) setStatus('Backend unavailable'); }); return () => { active = false; }; }, []);
  return status;
}
