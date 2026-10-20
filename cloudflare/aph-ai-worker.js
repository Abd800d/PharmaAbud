/*
 * APH provider proxy. API keys must only be configured as Cloudflare Worker Secrets.
 * Never place secrets in app code, JavaScript, build arguments, URLs, or logs.
 */
const ALLOWED_ORIGINS = new Set(['https://abd800d.github.io']);
const MAX_BODY_BYTES = 8 * 1024 * 1024;
const MAX_PROMPT_CHARS = 18000;
const MAX_SYSTEM_CHARS = 6000;
const MAX_TOKENS = 1600;
const GEMINI_MODELS = new Set(['gemini-2.5-flash', 'gemini-2.0-flash']);
const OPENAI_MODELS = new Set(['gpt-4o-mini']);

function cors(origin) {
  return {
    'Access-Control-Allow-Origin': origin || '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}
function json(data, status, origin) {
  return new Response(JSON.stringify(data), { status, headers: {
    ...cors(origin), 'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
  }});
}
function originAllowed(origin) {
  if (!origin || origin === 'null' || ALLOWED_ORIGINS.has(origin)) return true;
  try {
    const parsed = new URL(origin);
    return parsed.protocol === 'https:' && parsed.hostname.endsWith('.e2b.app');
  } catch (_) { return false; }
}
function safeError(value) {
  return String(value || 'AI provider request failed')
    .replace(/AIza[0-9A-Za-z_-]{10,}/g, 'AIza••••')
    .replace(/sk-[A-Za-z0-9_-]{10,}/g, 'sk-••••')
    .slice(0, 320);
}
async function rateAllowed(env, request) {
  if (!env.RATE_LIMIT || typeof env.RATE_LIMIT.limit !== 'function') return null;
  const ip = request.headers.get('CF-Connecting-IP') || 'native-unknown';
  const result = await env.RATE_LIMIT.limit({ key: ip });
  return result?.success === true;
}
function validImage(image, mime) {
  return typeof image === 'string' && image.length <= 7 * 1024 * 1024
    && /^[A-Za-z0-9+/]*={0,2}$/.test(image)
    && ['image/jpeg', 'image/png', 'image/webp'].includes(mime);
}
async function gemini(env, model, system, prompt, image, mime, maxTokens) {
  if (!env.GEMINI_API_KEY) throw new Error('GEMINI_API_KEY is not configured as a Worker Secret');
  const parts = [];
  if (image) parts.push({ inline_data: { mime_type: mime, data: image } });
  parts.push({ text: prompt });
  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,
    { method: 'POST', headers: {
      'Content-Type': 'application/json', 'x-goog-api-key': env.GEMINI_API_KEY,
    }, body: JSON.stringify({
      systemInstruction: { parts: [{ text: system }] },
      contents: [{ role: 'user', parts }],
      generationConfig: { temperature: 0.2, maxOutputTokens: maxTokens },
    }), signal: AbortSignal.timeout(85000) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`Gemini HTTP ${response.status}: ${data.error?.message || 'provider error'}`);
  const text = (data.candidates?.[0]?.content?.parts || []).map(part => part.text || '').join('').trim();
  if (!text) throw new Error(data.promptFeedback?.blockReason || 'Gemini returned an empty answer');
  return text;
}
async function openai(env, model, system, prompt, image, mime, maxTokens) {
  if (!env.OPENAI_API_KEY) throw new Error('OPENAI_API_KEY is not configured as a Worker Secret');
  const content = image ? [
    { type: 'text', text: prompt },
    { type: 'image_url', image_url: { url: `data:${mime};base64,${image}` } },
  ] : prompt;
  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST', headers: {
      'Content-Type': 'application/json', Authorization: `Bearer ${env.OPENAI_API_KEY}`,
    }, body: JSON.stringify({
      model, temperature: 0.2, max_tokens: maxTokens,
      messages: [{ role: 'system', content: system }, { role: 'user', content }],
    }), signal: AbortSignal.timeout(85000),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`OpenAI HTTP ${response.status}: ${data.error?.message || 'provider error'}`);
  const text = data.choices?.[0]?.message?.content?.trim();
  if (!text) throw new Error('OpenAI returned an empty answer');
  return text;
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin');
    if (!originAllowed(origin)) return json({ error: 'Origin not allowed' }, 403, origin);
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(origin) });
    if (request.method !== 'POST') return json({ error: 'POST only' }, 405, origin);
    if (Number(request.headers.get('Content-Length') || 0) > MAX_BODY_BYTES) {
      return json({ error: 'Request too large' }, 413, origin);
    }
    let allowed;
    try { allowed = await rateAllowed(env, request); }
    catch (_) { return json({ error: 'Rate limiter unavailable; request denied' }, 503, origin); }
    if (allowed === null) return json({ error: 'Rate limiter unavailable; request denied' }, 503, origin);
    if (!allowed) return json({ error: 'Rate limit reached. Try again shortly.' }, 429, origin);
    try {
      const raw = await request.text();
      if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) return json({ error: 'Request too large' }, 413, origin);
      const input = JSON.parse(raw);
      const provider = input.provider === 'openai' ? 'openai' : 'gemini';
      const defaultModel = provider === 'openai' ? 'gpt-4o-mini' : 'gemini-2.5-flash';
      const model = String(input.model || defaultModel);
      if (!(provider === 'openai' ? OPENAI_MODELS : GEMINI_MODELS).has(model)) return json({ error: 'Model not allowed' }, 400, origin);
      const prompt = String(input.prompt || '').trim();
      if (!prompt || prompt.length > MAX_PROMPT_CHARS) return json({ error: `Prompt must be 1-${MAX_PROMPT_CHARS} characters` }, 400, origin);
      const system = String(input.system || '').slice(0, MAX_SYSTEM_CHARS);
      const maxTokens = Math.max(64, Math.min(MAX_TOKENS, Number(input.maxTokens) || 1200));
      const image = input.image == null ? '' : String(input.image);
      const mime = String(input.mime || 'image/jpeg');
      if (image && !validImage(image, mime)) return json({ error: 'Invalid image type or size' }, 400, origin);
      const text = provider === 'openai'
        ? await openai(env, model, system, prompt, image, mime, maxTokens)
        : await gemini(env, model, system, prompt, image, mime, maxTokens);
      return json({ text, provider }, 200, origin);
    } catch (error) {
      return json({ error: safeError(error?.message || error) }, 502, origin);
    }
  },
};
