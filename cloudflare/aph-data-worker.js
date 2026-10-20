/* APH shared data API. D1 stores the published public catalogue; only the
 * dashboard can write, using a server-side password and signed short session.
 * No GitHub token or AI-provider key is used by this Worker. */
const ALLOWED_ORIGINS = new Set(['https://abd800d.github.io']);
const MAX_BODY_BYTES = 1_250_000;
const SESSION_SECONDS = 30 * 60;
const encoder = new TextEncoder();

function allowedOrigin(origin) {
  if (!origin || origin === 'null' || ALLOWED_ORIGINS.has(origin)) return true;
  try {
    const u = new URL(origin);
    return u.protocol === 'https:' &&
      (u.hostname.endsWith('.e2b.app') || u.hostname.endsWith('.pages.dev'));
  } catch (_) { return false; }
}
function cors(origin) {
  return {
    'Access-Control-Allow-Origin': origin || '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Expose-Headers': 'ETag, X-APH-Revision, X-APH-Updated-At',
    'Access-Control-Max-Age': '86400', Vary: 'Origin',
  };
}
function json(data, status, origin, extra = {}) {
  return new Response(JSON.stringify(data), { status, headers: {
    ...cors(origin), ...extra, 'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
  }});
}
function base64url(bytes) {
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}
function unbase64url(text) {
  const padded = text.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - text.length % 4) % 4);
  return Uint8Array.from(atob(padded), c => c.charCodeAt(0));
}
async function hmac(message, secret) {
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', key, encoder.encode(message)));
}
async function secureEqual(a, b) {
  const [x, y] = await Promise.all([
    crypto.subtle.digest('SHA-256', encoder.encode(String(a))),
    crypto.subtle.digest('SHA-256', encoder.encode(String(b))),
  ]);
  const left = new Uint8Array(x), right = new Uint8Array(y);
  let diff = 0;
  for (let i = 0; i < left.length; i++) diff |= left[i] ^ right[i];
  return diff === 0;
}
async function newSession(env) {
  const now = Math.floor(Date.now() / 1000);
  const payload = base64url(encoder.encode(JSON.stringify({ role: 'admin', exp: now + SESSION_SECONDS })));
  const sig = base64url(await hmac(payload, env.ADMIN_SESSION_SECRET));
  return `${payload}.${sig}`;
}
async function validSession(request, env) {
  const match = /^Bearer ([A-Za-z0-9_.-]+)$/.exec(request.headers.get('Authorization') || '');
  if (!match || !env.ADMIN_SESSION_SECRET) return false;
  const [payload, signature, extra] = match[1].split('.');
  if (!payload || !signature || extra) return false;
  try {
    const expected = base64url(await hmac(payload, env.ADMIN_SESSION_SECRET));
    if (!(await secureEqual(signature, expected))) return false;
    const data = JSON.parse(new TextDecoder().decode(unbase64url(payload)));
    return data.role === 'admin' && Number(data.exp) > Math.floor(Date.now() / 1000);
  } catch (_) { return false; }
}
async function bodyJson(request, maxBytes = MAX_BODY_BYTES) {
  const len = Number(request.headers.get('Content-Length') || 0);
  if (len > maxBytes) throw new Error('Request too large');
  const raw = await request.text();
  if (encoder.encode(raw).byteLength > maxBytes) throw new Error('Request too large');
  return JSON.parse(raw);
}
function validateDatabase(data) {
  if (!data || typeof data !== 'object' || !Array.isArray(data.drugs) || !Array.isArray(data.systems)) {
    return 'Expected APH JSON with systems and drugs arrays.';
  }
  if (data.drugs.length > 30000 || data.systems.length > 100) return 'Database record limit exceeded.';
  if (data.announcements != null && (!Array.isArray(data.announcements) || data.announcements.length > 5000)) {
    return 'Invalid announcements list.';
  }
  for (const drug of data.drugs) {
    if (!drug || typeof drug !== 'object' || !String(drug.genericEn || '').trim()) return 'Every medicine needs a genericEn name.';
    if (drug.products != null && (!Array.isArray(drug.products) || drug.products.length > 500)) return 'Invalid product list.';
    if (drug.products) for (const product of drug.products) {
      if (!product || typeof product !== 'object' || !String(product.brand || '').trim()) return 'Every trade product needs a brand name.';
    }
  }
  return '';
}
async function readDatabase(env, origin) {
  const row = await env.APH_DB.prepare('SELECT revision, payload, updated_at FROM aph_data WHERE id=1').first();
  if (!row) return json({ error: 'APH database is not initialized yet.' }, 404, origin);
  return json(JSON.parse(row.payload), 200, origin, {
    ETag: `"aph-${row.revision}"`, 'X-APH-Revision': String(row.revision),
    'X-APH-Updated-At': row.updated_at,
  });
}
async function recordLoginAttempt(env, request) {
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  const digest = await crypto.subtle.digest('SHA-256', encoder.encode(ip));
  const key = base64url(new Uint8Array(digest));
  const now = Date.now();
  const old = await env.APH_DB.prepare('SELECT window_started, attempts FROM aph_login_attempts WHERE ip_hash=?').bind(key).first();
  if (old && now - Number(old.window_started) < 15 * 60 * 1000 && Number(old.attempts) >= 5) return { blocked: true, key, now };
  const attempts = old && now - Number(old.window_started) < 15 * 60 * 1000 ? Number(old.attempts) + 1 : 1;
  const start = attempts === 1 ? now : Number(old.window_started);
  await env.APH_DB.prepare(`INSERT INTO aph_login_attempts(ip_hash,window_started,attempts) VALUES(?,?,?)
    ON CONFLICT(ip_hash) DO UPDATE SET window_started=excluded.window_started, attempts=excluded.attempts`)
    .bind(key, start, attempts).run();
  // Keep the small login-protection table bounded.
  await env.APH_DB.prepare('DELETE FROM aph_login_attempts WHERE window_started < ?').bind(now - 24 * 60 * 60 * 1000).run();
  return { blocked: false, key, now };
}
async function login(request, env, origin) {
  if (request.method !== 'POST') return json({ error: 'POST only' }, 405, origin);
  if (!env.ADMIN_PASSWORD || !env.ADMIN_SESSION_SECRET || !env.APH_DB) {
    return json({ error: 'Admin backend is not configured.' }, 503, origin);
  }
  let input;
  try { input = await bodyJson(request, 4096); }
  catch (_) { return json({ error: 'Invalid login request.' }, 400, origin); }
  const attempt = await recordLoginAttempt(env, request);
  if (attempt.blocked) return json({ error: 'Too many attempts. Wait 15 minutes.' }, 429, origin);
  if (!(await secureEqual(input.password || '', env.ADMIN_PASSWORD))) {
    return json({ error: 'Incorrect administrator password.' }, 401, origin);
  }
  await env.APH_DB.prepare('DELETE FROM aph_login_attempts WHERE ip_hash=?').bind(attempt.key).run();
  return json({ token: await newSession(env), expiresIn: SESSION_SECONDS }, 200, origin);
}
async function publish(request, env, origin) {
  if (request.method !== 'POST') return json({ error: 'GET or POST only' }, 405, origin);
  if (!(await validSession(request, env))) return json({ error: 'Administrator session expired. Log in again.' }, 401, origin);
  let input;
  try { input = await bodyJson(request); }
  catch (error) { return json({ error: error.message === 'Request too large' ? error.message : 'Invalid JSON body.' }, error.message === 'Request too large' ? 413 : 400, origin); }
  const problem = validateDatabase(input.database);
  if (problem) return json({ error: problem }, 400, origin);
  const payload = JSON.stringify(input.database);
  if (encoder.encode(payload).byteLength > MAX_BODY_BYTES) return json({ error: 'Published database exceeds the 1.25 MB limit.' }, 413, origin);
  const current = await env.APH_DB.prepare('SELECT revision FROM aph_data WHERE id=1').first();
  const currentRevision = Number(current?.revision || 0);
  if (Number(input.revision) !== currentRevision) return json({
    error: 'A newer database was published. Reload the server copy before publishing.',
    currentRevision,
  }, 409, origin);
  const nextRevision = currentRevision + 1;
  const updatedAt = new Date().toISOString();
  if (current) {
    const result = await env.APH_DB.prepare('UPDATE aph_data SET revision=?, payload=?, updated_at=? WHERE id=1 AND revision=?')
      .bind(nextRevision, payload, updatedAt, currentRevision).run();
    if (Number(result.meta?.changes || 0) !== 1) return json({ error: 'Concurrent publish detected. Reload and try again.' }, 409, origin);
  } else {
    try {
      await env.APH_DB.prepare('INSERT INTO aph_data(id,revision,payload,updated_at) VALUES(1,?,?,?)')
        .bind(nextRevision, payload, updatedAt).run();
    } catch (_) { return json({ error: 'Another administrator initialized the database. Reload and try again.' }, 409, origin); }
  }
  return json({ ok: true, revision: nextRevision, updatedAt }, 200, origin);
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin');
    if (!allowedOrigin(origin)) return json({ error: 'Origin not allowed.' }, 403, origin);
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(origin) });
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/database') {
      if (!env.APH_DB) return json({ error: 'D1 database is not configured.' }, 503, origin);
      if (request.method === 'GET') return readDatabase(env, origin);
      if (request.method === 'POST') return publish(request, env, origin);
      return json({ error: 'GET or POST only.' }, 405, origin);
    }
    if (url.pathname === '/api/v1/admin/login') return login(request, env, origin);
    if (url.pathname === '/health') return json({ ok: true, service: 'APH data sync', revision: 'v1' }, 200, origin);
    return json({ error: 'Not found.' }, 404, origin);
  },
};
