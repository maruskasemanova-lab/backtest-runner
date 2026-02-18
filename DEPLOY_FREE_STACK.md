# Free Deploy (FE + BE)

If you want persistent always-on playback with lower latency, use Fly + Cloudflare Pages guide:

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/DEPLOY_CLOUDFLARE_STACK.md`

This is the simplest low-cost stack for this project:

- Frontend: Netlify (free static hosting)
- Backend API: Render Web Service (free plan)
- DB/Auth baseline: Supabase (free project)

Why not serverless backend:

- Interactive run playback (`/api/run/start`, `/api/run/*/play|step|state`) keeps active run state in process memory.
- Serverless platforms (for example Vercel/Lambda) do not guarantee sticky process state between requests, which leads to `Run not found` errors after start.

DB decision (cheapest practical):

- Use **Supabase Postgres (free tier)** as primary DB for:
  - user-scoped adaptive strategy profiles
  - superuser/global adaptive profiles
  - diagnostics/report indexes + cached payload metadata/blobs
- Keep local SQLite only as fallback/dev cache.
- Use **Cloudflare R2** for shared market-data objects (e.g. MU Jan/Feb bundles) and expose a public manifest JSON.

## 1. Backend (Render)

1. Push this repo to GitHub.
2. In Render, create **Blueprint** from repo root.
3. Render will read `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/render.yaml`.
4. Set required env vars in Render:
   - `BACKTEST_INTERNAL_STRATEGY_API_URL=https://<your-strategy-api>.onrender.com`
   - `BACKTEST_STRATEGY_API_ALLOWLIST=https://<your-strategy-api>.onrender.com`
   - `BACKTEST_CORS_ALLOW_ORIGINS=https://<your-netlify-site>.netlify.app,http://localhost:5173`
   - `BACKTEST_JWT_SECRET=<secret>`
   - `SUPABASE_JWT_SECRET=<supabase-jwt-secret>`
   - `DATABENTO_API_KEY=<key>`
   - `BACKTEST_SUPABASE_USER_SETTINGS_ENABLED=1`
   - `BACKTEST_SUPABASE_URL=https://<your-project-ref>.supabase.co`
   - `BACKTEST_SUPABASE_SERVICE_ROLE_KEY=<supabase-service-role-secret>`

Optional quick deploy trigger:

```bash
RENDER_DEPLOY_HOOK_URL="<your-render-hook>" ./scripts/deploy_backend_render.sh
```

## 2. Strategy API (second backend service)

Deploy `market_regime_detection` as a separate Render Web Service:

- Build command: `pip install --upgrade pip && pip install -r requirements.txt`
- Start command: `uvicorn api_server:app --host 0.0.0.0 --port $PORT`

Set CORS env:

- `STRATEGY_CORS_ALLOW_ORIGINS=https://<your-netlify-site>.netlify.app`

## 3. Frontend (Netlify)

From `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend`:

```bash
npm ci
npm run deploy:app
```

Set Netlify env vars (Site settings -> Environment variables):

- `VITE_API_BASE_URL=https://<your-backtest-runner-api>.onrender.com`
- optional hybrid mode (keep stateless API on Vercel, playback on persistent backend):
  - `VITE_API_BASE_URL=https://<your-backtest-runner>.vercel.app`
  - `VITE_PLAYBACK_API_BASE_URL=https://<your-backtest-runner-api>.onrender.com`
- `VITE_STRATEGY_API_URL=https://<your-strategy-api>.onrender.com`
- optional `VITE_WS_BASE_URL=wss://<your-backtest-runner-api>.onrender.com`

Template env file:

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/.env.example`

## 4. Supabase (free)

Use Supabase for JWT/Auth + Postgres project bootstrap:

1. Create a free Supabase project.
2. Run SQL from:
   - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/db/supabase/001_initial_saas.sql`
   - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/db/supabase/002_adaptive_and_diagnostics.sql`
   - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/db/supabase/004_user_settings.sql`
3. Put JWT secret in backend env:
   - `SUPABASE_JWT_SECRET=<supabase-jwt-secret>`
4. Do not expose service role key to frontend (`VITE_*` env). Keep it backend-only.
5. In Supabase Dashboard (`Authentication -> URL Configuration`) set:
   - `Site URL = https://<your-frontend-domain>`
   - add Redirect URLs:
     - `https://<your-frontend-domain>/auth/callback`
     - local dev callbacks you use (for example `http://localhost:5173/auth/callback`)
6. In `Authentication -> Providers -> Google`, enable provider and set OAuth client credentials.
   - Google Cloud OAuth redirect URI must be:
     - `https://<your-project-ref>.supabase.co/auth/v1/callback`

## 5. Minimal smoke check

- FE opens: `https://<your-netlify-site>.netlify.app`
- Backend health: `https://<your-backtest-runner-api>.onrender.com/api/health`
- Strategy health: `https://<your-strategy-api>.onrender.com/`

## 6. R2 Market-Data Publish (MU Jan/Feb)

Use script:

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/scripts/publish_mu_r2_janfeb.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/scripts/upload_mu_r2_wrangler.sh` (Wrangler upload path)

Required env vars:

- `R2_ACCOUNT_ID`
- `R2_BUCKET`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_MANIFEST_MODE=private` (or `public`)
- `R2_S3_ENDPOINT` (for your account: `https://bd3055453355b1ddfe7362df87a71576.r2.cloudflarestorage.com`)
- when `R2_MANIFEST_MODE=public`: `R2_PUBLIC_BASE_URL`

Then point backend to manifest:

- `BACKTEST_REMOTE_MANIFEST_URL=<public manifest url>`
- for private mode use `s3://<bucket>/<prefix>/manifests/mu_janfeb_manifest.json`
- and set backend R2 creds:
  - `BACKTEST_REMOTE_S3_ENDPOINT=https://bd3055453355b1ddfe7362df87a71576.r2.cloudflarestorage.com`
  - `BACKTEST_REMOTE_S3_ACCESS_KEY_ID=<key>`
  - `BACKTEST_REMOTE_S3_SECRET_ACCESS_KEY=<secret>`

Optional local preflight (no upload):

- `R2_DRY_RUN=1 python3 scripts/publish_mu_r2_janfeb.py`

Wrangler-based upload (no S3 key pair needed):

- ensure Wrangler login: `wrangler login`
- enable public bucket URL:
  - `npx -y wrangler@4.65.0 r2 bucket dev-url enable market-data`
- run:
  - `R2_ACCOUNT_ID=<account_id> R2_BUCKET=market-data R2_PUBLIC_BASE_URL=<r2_dev_url> ./scripts/upload_mu_r2_wrangler.sh`
