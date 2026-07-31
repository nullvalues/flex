import { afterEach, describe, expect, it } from 'vitest';
import type { FastifyInstance } from 'fastify';
import { buildServer, isLoopbackHost, resolveCorsOrigin } from '../src/server.js';

// INFRA-306 pin (INFRA-312 Ensures §3): the loopback-honest CORS contract as
// shipped — loopback binds keep the historical wildcard-origin behaviour;
// non-loopback binds default deny-all unless an explicit allow-list is set.
describe('CORS / loopback contract (INFRA-306)', () => {
  let app: FastifyInstance | undefined;
  const originalAllowed = process.env.FLEX_OBS_ALLOWED_ORIGINS;

  afterEach(async () => {
    if (app) {
      await app.close();
      app = undefined;
    }
    if (originalAllowed === undefined) delete process.env.FLEX_OBS_ALLOWED_ORIGINS;
    else process.env.FLEX_OBS_ALLOWED_ORIGINS = originalAllowed;
  });

  it('isLoopbackHost/resolveCorsOrigin: loopback hosts resolve to wildcard', () => {
    expect(isLoopbackHost('127.0.0.1')).toBe(true);
    expect(isLoopbackHost('localhost')).toBe(true);
    expect(isLoopbackHost('::1')).toBe(true);
    expect(isLoopbackHost('0.0.0.0')).toBe(false);
    expect(resolveCorsOrigin('127.0.0.1', undefined)).toBe('*');
  });

  it('resolveCorsOrigin: non-loopback with no allow-list denies all cross-origin requests', () => {
    expect(resolveCorsOrigin('0.0.0.0', undefined)).toBe(false);
  });

  it('resolveCorsOrigin: non-loopback with an allow-list permits only listed origins', () => {
    expect(resolveCorsOrigin('0.0.0.0', 'https://a.example, https://b.example')).toEqual([
      'https://a.example',
      'https://b.example',
    ]);
  });

  it('a loopback-bound server echoes Access-Control-Allow-Origin: * for any request origin', async () => {
    delete process.env.FLEX_OBS_ALLOWED_ORIGINS;
    app = await buildServer('127.0.0.1');
    const res = await app.inject({
      method: 'GET',
      url: '/health',
      headers: { origin: 'https://anything.example' },
    });
    expect(res.statusCode).toBe(200);
    expect(res.headers['access-control-allow-origin']).toBe('*');
  });

  it('a non-loopback-bound server with no allow-list omits the CORS allow header (denied)', async () => {
    delete process.env.FLEX_OBS_ALLOWED_ORIGINS;
    app = await buildServer('0.0.0.0');
    const res = await app.inject({
      method: 'GET',
      url: '/health',
      headers: { origin: 'https://anything.example' },
    });
    // @fastify/cors with origin: false never sets the allow-origin header —
    // the request still succeeds (no browser is enforcing CORS here), but a
    // real browser would block reading the response body cross-origin.
    expect(res.headers['access-control-allow-origin']).toBeUndefined();
  });
});
