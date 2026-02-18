# Cloudflare Pages + Fly.io Deploy (Production)

Recommended stack:

1. Frontend: Cloudflare Pages (free/static CDN)
2. Runner API: Fly.io (stateful, always-on)
3. Strategy API: Fly.io (stateful, always-on)

## Current Live Setup

1. Frontend: `https://backtest-runner-fe-sseman.pages.dev`
2. Runner API: `https://backtest-runner-api-sseman.fly.dev`
3. Strategy API: `https://mrd-strategy-api-sseman.fly.dev`

## 1. Deploy Backend APIs (Fly)

From repo root:

```bash
./scripts/deploy_fly_stack.sh
```

Set these before deploy for Pages CORS:

```bash
export BACKTEST_CORS_ALLOW_ORIGINS="https://<pages-project>.pages.dev,http://localhost:5173,http://127.0.0.1:5173"
export STRATEGY_CORS_ALLOW_ORIGINS="https://<pages-project>.pages.dev,http://localhost:5173,http://127.0.0.1:5173"
export BACKTEST_CORS_ALLOW_ORIGIN_REGEX='^https://(?:[a-z0-9-]+\.)?<pages-project>\.pages\.dev$'
export STRATEGY_CORS_ALLOW_ORIGIN_REGEX='^https://(?:[a-z0-9-]+\.)?<pages-project>\.pages\.dev$'
```

## 2. Deploy Frontend (Cloudflare Pages)

Create Pages project once:

```bash
wrangler pages project create <pages-project> --production-branch main
```

Deploy:

```bash
export CLOUDFLARE_PAGES_PROJECT=<pages-project>
export FLY_RUNNER_APP_NAME=<runner-app-name>
export FLY_STRATEGY_APP_NAME=<strategy-app-name>

export VITE_SUPABASE_URL=https://<supabase-project>.supabase.co
export VITE_SUPABASE_PUBLISHABLE_KEY=<supabase-publishable-key>
export VITE_SUPABASE_OAUTH_CALLBACK_PATH=/auth/callback

./scripts/deploy_frontend_cloudflare_pages.sh
```

## 3. Supabase OAuth Redirects

In Supabase Dashboard (`Authentication -> URL Configuration`), add:

1. `https://<pages-project>.pages.dev/auth/callback`
2. optional preview pattern URLs you use (per-deploy URLs)

Without this, Google sign-in callback can fail on Pages origin.

## 4. Smoke Checks

1. Runner health:

```bash
curl -s https://<runner-app-name>.fly.dev/api/health
```

Expected: `stateful_run_api_supported=true`

2. Strategy health:

```bash
curl -s https://<strategy-app-name>.fly.dev/api/system/health
```

3. Stateful playback flow:

```bash
curl -s -X POST "https://<runner-app-name>.fly.dev/api/run/start" \
  -H "content-type: application/json" \
  --data '{"run_id":"smoke","ticker":"MU","date":"2026-02-11","strategy_api_url":"https://<strategy-app-name>.fly.dev"}'
```

Then call `/step` and `/state` for the same run key.
