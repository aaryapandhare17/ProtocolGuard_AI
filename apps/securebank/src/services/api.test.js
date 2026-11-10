import { afterEach, expect, it, vi } from 'vitest';
import { getHealth } from './api.js';
afterEach(() => vi.unstubAllGlobals());
it('rejects a failed health response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
  await expect(getHealth()).rejects.toThrow('Backend health check failed');
});
it('returns backend health data', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }));
  await expect(getHealth()).resolves.toEqual({ status: 'ok' });
});
