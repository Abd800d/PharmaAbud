#!/usr/bin/env node
/* Offline regression for APH's shared D1 admin/read API. */
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('../cloudflare/aph-data-worker.js', import.meta.url), 'utf8');
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

class FakeD1 {
  constructor() { this.data = null; this.attempts = new Map(); }
  prepare(sql) { return new FakeStatement(this, sql); }
}
class FakeStatement {
  constructor(db, sql) { this.db = db; this.sql = sql; this.args = []; }
  bind(...args) { this.args = args; return this; }
  async first() {
    if (this.sql.includes('FROM aph_data')) return this.db.data ? {
      revision: this.db.data.revision, payload: this.db.data.payload,
      updated_at: this.db.data.updated_at,
    } : null;
    if (this.sql.includes('FROM aph_login_attempts')) return this.db.attempts.get(this.args[0]) || null;
    throw new Error(`Unexpected first query: ${this.sql}`);
  }
  async run() {
    if (this.sql.startsWith('INSERT INTO aph_login_attempts')) {
      this.db.attempts.set(this.args[0], { window_started: this.args[1], attempts: this.args[2] });
      return { meta: { changes: 1 } };
    }
    if (this.sql.startsWith('DELETE FROM aph_login_attempts WHERE ip_hash')) {
      this.db.attempts.delete(this.args[0]); return { meta: { changes: 1 } };
    }
    if (this.sql.startsWith('DELETE FROM aph_login_attempts WHERE window_started')) return { meta: { changes: 0 } };
    if (this.sql.startsWith('UPDATE aph_data')) {
      const [revision, payload, updated_at, expected] = this.args;
      if (!this.db.data || this.db.data.revision !== expected) return { meta: { changes: 0 } };
      this.db.data = { revision, payload, updated_at };
      return { meta: { changes: 1 } };
    }
    if (this.sql.startsWith('INSERT INTO aph_data')) {
      const [revision, payload, updated_at] = this.args;
      if (this.db.data) throw new Error('duplicate row');
      this.db.data = { revision, payload, updated_at };
      return { meta: { changes: 1 } };
    }
    throw new Error(`Unexpected run query: ${this.sql}`);
  }
}

const db = new FakeD1();
const env = { APH_DB: db, ADMIN_PASSWORD: 'test-password', ADMIN_SESSION_SECRET: 'test-only-secret-long-enough' };
const trustedOrigin = 'https://abd800d.github.io';
const request = (path, { method = 'GET', body, token, origin = trustedOrigin } = {}) =>
  new Request(`https://aph-data.example.workers.dev${path}`, {
    method,
    headers: {
      Origin: origin,
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });

assert.equal((await worker.fetch(request('/health'), env)).status, 200);
assert.equal((await worker.fetch(request('/api/v1/database'), env)).status, 404,
  'uninitialized DB should allow the client to use the public fallback');
assert.equal((await worker.fetch(request('/api/v1/admin/login', {
  method: 'POST', body: { password: 'wrong' },
}), env)).status, 401);
const login = await worker.fetch(request('/api/v1/admin/login', {
  method: 'POST', body: { password: env.ADMIN_PASSWORD },
}), env);
assert.equal(login.status, 200);
const { token } = await login.json();
assert.ok(token);
const data = {
  app: 'APH', systems: [{ id: 'misc', en: 'Misc', ar: 'متنوع' }],
  drugs: [{ genericEn: 'Test medicine', products: [{ brand: 'Test brand' }] }],
  announcements: [],
};
assert.equal((await worker.fetch(request('/api/v1/database', {
  method: 'POST', body: { revision: 0, database: data },
}), env)).status, 401);
const published = await worker.fetch(request('/api/v1/database', {
  method: 'POST', token, body: { revision: 0, database: data },
}), env);
assert.equal(published.status, 200);
assert.equal((await published.json()).revision, 1);
const read = await worker.fetch(request('/api/v1/database'), env);
assert.equal(read.status, 200);
assert.equal(read.headers.get('X-APH-Revision'), '1');
assert.match(read.headers.get('Access-Control-Expose-Headers') || '', /X-APH-Revision/);
assert.deepEqual((await read.json()).drugs, data.drugs);
assert.equal((await worker.fetch(request('/api/v1/database', {
  method: 'POST', token, body: { revision: 0, database: data },
}), env)).status, 409, 'stale admin publishes must not overwrite newer data');
assert.equal((await worker.fetch(request('/api/v1/database', {
  method: 'POST', token, body: { revision: 1, database: { drugs: 'bad', systems: [] } },
}), env)).status, 400);
assert.equal((await worker.fetch(request('/api/v1/database', {
  origin: 'https://evil.example',
}), env)).status, 403);
console.log('APH data Worker tests passed: auth, session signing, publish/read, optimistic conflict and validation.');
