#!/usr/bin/env node
/* Offline Worker smoke test; never uses a real provider key or network. */
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('../cloudflare/aph-ai-worker.js', import.meta.url), 'utf8');
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const dummySecret = 'TEST_ONLY_SECRET_NOT_A_PROVIDER_KEY';
let upstream;
globalThis.fetch = async (url, init) => {
  upstream = { url: String(url), init };
  return new Response(JSON.stringify({ candidates: [{ content: { parts: [{ text: 'READY' }] } }] }),
    { status: 200, headers: { 'Content-Type': 'application/json' } });
};
const env = { GEMINI_API_KEY: dummySecret, RATE_LIMIT: { limit: async () => ({ success: true }) } };
const post = (body, headers = {}) => new Request('https://aph-ai-proxy.example.workers.dev/', {
  method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body),
});
const response = await worker.fetch(post({ provider: 'gemini', model: 'gemini-2.5-flash', prompt: 'test', system: 'system' },
  { Origin: 'https://abd800d.github.io', 'CF-Connecting-IP': '192.0.2.1' }), env);
assert.equal(response.status, 200);
assert.equal((await response.json()).text, 'READY');
assert.equal(upstream.init.headers['x-goog-api-key'], dummySecret);
assert.equal(upstream.url.includes(dummySecret), false, 'key must not appear in URL');
const rejected = await worker.fetch(post({}, { Origin: 'https://evil.example' }), env);
assert.equal(rejected.status, 403);
const limited = await worker.fetch(post({}), { ...env, RATE_LIMIT: { limit: async () => ({ success: false }) } });
assert.equal(limited.status, 429);
const failClosed = await worker.fetch(post({}), { GEMINI_API_KEY: dummySecret });
assert.equal(failClosed.status, 503);
const badModel = await worker.fetch(post({ provider: 'openai', model: 'expensive-model', prompt: 'test' }), env);
assert.equal(badModel.status, 400);
console.log('APH Worker smoke tests passed: provider routing, secret transport, origin/rate/model validation.');
