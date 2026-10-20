# APH secure AI proxy (Cloudflare Worker)

Provider keys must remain Cloudflare Worker Secrets. They must never be placed in the APK, web JavaScript, repository, GitHub Actions variables, URLs, or chat. The APK/PWA stores only the public Worker URL.

The app's automatic provider is Gemini only. The Google AI Studio quota may be free when available, but the provider determines its limits and availability and these can change. OpenAI is a separately selected option and may be paid. No unlimited-free service is promised.

## Deploy

Requirements: a Cloudflare account, Node.js/npm, Wrangler, and a fresh Gemini key from <https://aistudio.google.com/app/apikey>.

```bash
cd cloudflare
npx wrangler login
npx wrangler secret put GEMINI_API_KEY
npx wrangler deploy
```

Wrangler asks for the key interactively. Do not put it in `wrangler.toml`, the app, GitHub, or a message. Deployment prints a public URL such as `https://aph-ai-proxy.<account>.workers.dev`; the URL is not a secret.

If intentionally using OpenAI (may incur charges), add its key only as a Worker Secret:

```bash
npx wrangler secret put OPENAI_API_KEY
```

The automatic mode will still call Gemini only; OpenAI is used only when explicitly selected.

## Connect Android / PWA

- Android: Settings → AI Assistant → enter the HTTPS Worker URL only → Save → Test connection. Or set the GitHub Actions repository **Variable** `APH_AI_PROXY` to this URL before building. This variable is public and is not the provider key.
- PWA: AI settings → enter the HTTPS Worker URL only → Save → Test connection.
- If the URL is blank, both clients use their local APH behavior. A Worker must be deployed and have a valid provider secret for cloud answers.

## Limits and security

- `wrangler.toml` applies 30 requests per IP per minute as an abuse-control measure. The Worker denies requests if the rate-limit binding is unavailable.
- CORS is not authentication. The endpoint is callable by clients, so monitor provider quotas and usage. Do not rely on the IP limit as a billing guarantee.
- Only allowlisted models are accepted; prompts/images/tokens have limits. Provider errors are redacted and request bodies/secrets are not logged.
- Gemini's free quota and Cloudflare plan limits can change. If Gemini's quota is exhausted, automatic mode falls back to local APH answers, not paid OpenAI.

## APH shared catalogue and administration API

The separate `aph-data-worker.js` is for publishing the APH catalogue and announcements; it is not the AI proxy. It uses D1 and server-side admin secrets, and the APK/browser stores only the public endpoint URL. Follow [`../CONTROL_SITE.md`](../CONTROL_SITE.md) for setup, deployment, and app configuration.

- D1 binding: `APH_DB`; create the database, replace the `database_id` placeholder in `data-wrangler.toml`, apply `migrations/`, then deploy.
- Set `ADMIN_PASSWORD` and `ADMIN_SESSION_SECRET` as Wrangler secrets. Do not put these values in the repository or dashboard source.
- The public database read endpoint is `/api/v1/database`; the admin login endpoint is `/api/v1/admin/login`. Publishing requires a short-lived signed session and the current revision.
- Published payloads are limited to 1.25 MB. The dashboard supports reversible archive markers; the app's sync is one-way from admin to devices. D1 is not initialized until the owner completes setup and publishes the first snapshot.
- Test the Worker logic locally (mock D1; no Cloudflare deployment/network required) with `node tools/test_data_worker.mjs` from the repository root. This does not prove a live Cloudflare deployment or account configuration.
