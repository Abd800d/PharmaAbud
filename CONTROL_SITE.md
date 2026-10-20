# APH management site and data sync

**APH — © Dr. Abdulmajeed Abdullah Almakhedhi**

This repository now includes a browser administration page, a Cloudflare Worker API, and local SQLite sync support. The app remains usable offline. Cloud sync is **one-way: administrator publishes → app downloads and merges**. User pharmacy inventory, sales, and local edits are not uploaded to D1. This feature is **not live until the owner deploys/configures the Worker and database**.

```text
Admin page ── authenticated publish ──▶ Cloudflare Worker + D1
                                            │ public HTTPS read
                                            ▼
                          APH app pulls + merges into on-device SQLite
```

## 1. Deploy the data service (one-time owner setup)

Requirements: Cloudflare account, Node.js/npm, and Wrangler. No GitHub token, AI key, or secret is required in the app or dashboard.

1. Create a Cloudflare D1 database and record the ID Wrangler returns:
   ```bash
   cd cloudflare
   npx wrangler login
   npx wrangler d1 create aph-data
   ```
2. Put the returned `database_id` into `cloudflare/data-wrangler.toml`, replacing the placeholder. Apply the schema and deploy:
   ```bash
   npx wrangler d1 migrations apply aph-data --remote --config data-wrangler.toml
   npx wrangler secret put ADMIN_PASSWORD --config data-wrangler.toml
   npx wrangler secret put ADMIN_SESSION_SECRET --config data-wrangler.toml
   npx wrangler deploy --config data-wrangler.toml
   ```
   Use a unique, strong admin password and a separately generated random session secret (at least 32 random bytes). Wrangler prompts for the values interactively. Do not put either value in source files, GitHub, the APK, or chat. Keep the Cloudflare account and secret recovery method secure.
3. Wrangler prints a public `workers.dev` URL. It is an endpoint, not a secret. D1 usage, Worker limits, availability, and pricing depend on Cloudflare's current plan; no unlimited-free service is promised.

The Worker exposes:
- `POST /api/v1/admin/login` — exchanges the admin password for a short-lived signed session.
- `GET /api/v1/database` — public read of the published APH database.
- `POST /api/v1/database` — authenticated publish with revision-conflict protection.

## 2. Use the administration page

1. Enable GitHub Pages for the repository if it is not already enabled (Settings → Pages → deploy from `main`, root folder). Then open `https://abd800d.github.io/PharmaAbud/admin/`; alternatively serve `webapp/` over HTTPS. Local file mode can be used for drafts but may restrict browser features.
2. Enter the Worker base URL and the admin password. The password is sent only to the Worker for login; the page keeps the short-lived session in memory and does not save the password. The Worker allows this repository's GitHub Pages origin and `*.pages.dev`/Arena preview origins by default; if you host the page on a custom domain, add that exact HTTPS origin to `ALLOWED_ORIGINS` in `cloudflare/aph-data-worker.js` and redeploy.
3. Review/edit APH records, import data, add announcements, or archive/restore medicines and products. Archive is reversible and safer than deleting records needed by older app databases or pharmacy stock history.
4. Click **Publish and sync now**. The page uploads the database to D1. A revision conflict means another admin published first: reload the server version, reapply changes, and publish again.
5. For offline draft work, use **Open local draft only**. Those edits stay in that browser until exported or connected and published; they are not shared automatically.

Only enter verified, sourced medicine and product facts. Do not invent indications, doses, manufacturers, or Yemen agents. Record source details in the data where available.

## 3. Connect the installed app

In the app open **More → Settings → Published database URL (JSON)** and set the exact URL:

```text
https://<your-worker-host>/api/v1/database
```

Save it, then press **Sync now** (or leave auto-sync enabled). The app downloads the public snapshot and merges it into local SQLite: non-empty shared fields from the admin snapshot are authoritative, while blank remote fields do not erase device data. It does not replace the user's pharmacy tables. The app remains usable offline. A published archive marker hides the record from normal catalogue search without destructively deleting it; existing stock tied to an archived product remains available for sale until depleted.

The repository's static JSON URL remains a fallback/default for installations not configured to use the Worker. If the Worker is unavailable or the D1 database has not yet been initialized, sync may fall back to that older static snapshot; this is not evidence that a live publish succeeded.

## 4. Scope and privacy

- This is **not bidirectional sync** and does not provide an incoming user chat. Messages typed into the admin page are announcements delivered to the app on its next successful pull. Contact support via WhatsApp **781733795** or email **7a8b1d@gmail.com**.
- D1 contains the published shared catalogue and announcements only. Pharmacy stock, sales, and other device-local data are not sent to the service.
- Public database reads have no user authentication; do not publish private or patient-identifiable information.
- The Cloudflare Worker source, migration, and offline API test are in `cloudflare/` and `tools/test_data_worker.mjs`. Run `node tools/test_data_worker.mjs` to test the API's login, publish, validation, and revision-conflict behavior against a local D1-compatible mock. This does not deploy or test a real Cloudflare account.
- AI proxy setup is separate; see `cloudflare/README.md`. Never put provider keys in the APK, JavaScript, repository, or chat. Provider quotas and free tiers can change.
