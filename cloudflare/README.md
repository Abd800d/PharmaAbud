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
