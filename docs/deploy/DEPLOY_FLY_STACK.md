# Fly.io Deploy (Production Stateful)

This is the recommended production path for fast stateful playback:

- Frontend: Cloudflare Pages
- Backtest runner API: Fly.io (always-on machine, persistent volume)
- Strategy API (`market_regime_detection`): Fly.io (always-on machine)

`/api/run/*` and `/api/session/*` are in-memory stateful flows. Keep both APIs on persistent services.

## 1. Prerequisites

1. Install and auth Fly CLI:

```bash
brew install flyctl
flyctl auth login
```

2. Prepare env vars (minimum):

```bash
export FLY_RUNNER_APP_NAME=backtest-runner-api
export FLY_STRATEGY_APP_NAME=market-regime-strategy-api
export FLY_PRIMARY_REGION=iad

export BACKTEST_CORS_ALLOW_ORIGINS=https://<your-pages-project>.pages.dev,http://localhost:5173
export STRATEGY_CORS_ALLOW_ORIGINS=https://<your-pages-project>.pages.dev,http://localhost:5173
export BACKTEST_CORS_ALLOW_ORIGIN_REGEX='^https://(?:[a-z0-9-]+\.)?<your-pages-project>\.pages\.dev$'
export STRATEGY_CORS_ALLOW_ORIGIN_REGEX='^https://(?:[a-z0-9-]+\.)?<your-pages-project>\.pages\.dev$'

export BACKTEST_JWT_SECRET=<secret>
export SUPABASE_JWT_SECRET=<secret>
export STRATEGY_INTERNAL_API_TOKEN=<same-in-both-services>
export BACKTEST_STRATEGY_INTERNAL_API_TOKEN=<same-in-both-services>
```

Optional (recommended for prod):

```bash
export BACKTEST_SUPABASE_USER_SETTINGS_ENABLED=1
export BACKTEST_SUPABASE_URL=https://<project-ref>.supabase.co
export BACKTEST_SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
export BACKTEST_REMOTE_MANIFEST_URL=<r2-public-manifest-url>
export DATABENTO_API_KEY=<key>
```

## 2. Deploy Both APIs

From `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner`:

```bash
./scripts/deploy_fly_stack.sh
```

What this does:

1. Deploys strategy API from sibling repo `../market_regime_detection`.
2. Deploys runner API from this repo using `fly.toml`.
3. Creates runner volume (`backtest_data`) for persistent SQLite/config/cache.
4. Forces single-machine deployment (`count=1`) on both services.

## 3. Connect Cloudflare Pages Frontend

Set frontend build env vars and deploy Pages:

1. `VITE_API_BASE_URL=https://<FLY_RUNNER_APP_NAME>.fly.dev`
2. `VITE_PLAYBACK_API_BASE_URL=https://<FLY_RUNNER_APP_NAME>.fly.dev`
3. `VITE_STRATEGY_API_URL=https://<FLY_STRATEGY_APP_NAME>.fly.dev`
4. `VITE_WS_BASE_URL=wss://<FLY_RUNNER_APP_NAME>.fly.dev`

Example:

```bash
export CLOUDFLARE_PAGES_PROJECT=<pages-project>
export VITE_SUPABASE_URL=https://<project-ref>.supabase.co
export VITE_SUPABASE_PUBLISHABLE_KEY=<publishable-key>
./scripts/deploy_frontend_cloudflare_pages.sh
```

## 4. Smoke Checks

1. Runner health:

```bash
curl -s https://<FLY_RUNNER_APP_NAME>.fly.dev/api/health
```

Expected:

- `"status": "healthy"`
- `"serverless_environment": false`
- `"stateful_run_api_supported": true`

2. Strategy health:

```bash
curl -s https://<FLY_STRATEGY_APP_NAME>.fly.dev/
```

3. Ensure one machine per app:

```bash
flyctl scale count 1 --app <FLY_RUNNER_APP_NAME>
flyctl scale count 1 --app <FLY_STRATEGY_APP_NAME>
```

## 5. Production Notes

1. Keep `auto_stop_machines = "off"` and `min_machines_running = 1` for both apps (already in Fly config).
2. Do not horizontally scale stateful APIs without externalizing run/session registry to shared storage.
3. Runner uses persistent paths from `fly.toml`:
   - `/data/saas_state.db`
   - `/data/config/*`
   - `/data/remote_cache/*`
