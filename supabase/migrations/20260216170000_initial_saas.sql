-- Initial SaaS schema for Supabase/PostgreSQL.
-- Mirrors the v2 API ownership model and quota/billing lifecycle.

create table if not exists public.tenants (
  id uuid primary key default gen_random_uuid(),
  owner_user_id text not null,
  name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.users (
  id text primary key,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  email text,
  role text not null default 'free',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.plans (
  id text primary key,
  concurrent_runs integer not null,
  max_range_days integer not null,
  req_per_min integer not null,
  retention_days integer not null,
  ads_enabled boolean not null
);

insert into public.plans(id, concurrent_runs, max_range_days, req_per_min, retention_days, ads_enabled)
values
  ('free', 1, 5, 30, 7, true),
  ('premium', 5, 60, 300, 180, false),
  ('admin', 20, 365, 2000, 365, false)
on conflict (id) do nothing;

create table if not exists public.subscriptions (
  user_id text primary key references public.users(id) on delete cascade,
  plan_id text not null references public.plans(id),
  status text not null default 'active',
  stripe_customer_id text,
  stripe_subscription_id text,
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.entitlements (
  user_id text primary key references public.users(id) on delete cascade,
  plan_id text not null references public.plans(id),
  effective_from timestamptz not null default now(),
  effective_to timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists public.runs (
  run_key text primary key,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id text not null references public.users(id) on delete cascade,
  run_id text not null,
  ticker text not null,
  date_label text not null,
  status text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_runs_tenant_created_at on public.runs(tenant_id, created_at desc);
create index if not exists idx_runs_user_created_at on public.runs(user_id, created_at desc);

create table if not exists public.run_jobs (
  id text primary key,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id text not null references public.users(id) on delete cascade,
  job_type text not null,
  status text not null,
  payload jsonb not null default '{}'::jsonb,
  result jsonb,
  error text,
  run_key text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_run_jobs_user_status on public.run_jobs(user_id, status);

create table if not exists public.run_events (
  id bigserial primary key,
  run_key text not null,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id text not null references public.users(id) on delete cascade,
  event_type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_run_events_run_key_created_at on public.run_events(run_key, created_at desc);

create table if not exists public.run_summaries (
  run_key text primary key,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id text not null references public.users(id) on delete cascade,
  summary jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.usage_counters_daily (
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id text not null references public.users(id) on delete cascade,
  day_key date not null,
  metric text not null,
  value bigint not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, day_key, metric)
);

create table if not exists public.artifacts (
  id bigserial primary key,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id text not null references public.users(id) on delete cascade,
  run_key text,
  artifact_type text not null,
  storage_url text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- RLS baseline (tenant isolation by JWT claim: tenant_id)
alter table public.tenants enable row level security;
alter table public.users enable row level security;
alter table public.subscriptions enable row level security;
alter table public.entitlements enable row level security;
alter table public.runs enable row level security;
alter table public.run_jobs enable row level security;
alter table public.run_events enable row level security;
alter table public.run_summaries enable row level security;
alter table public.usage_counters_daily enable row level security;
alter table public.artifacts enable row level security;

create policy tenants_isolation on public.tenants
  using (id::text = auth.jwt()->>'tenant_id');

create policy users_isolation on public.users
  using (tenant_id::text = auth.jwt()->>'tenant_id');

create policy subscriptions_isolation on public.subscriptions
  using (user_id = auth.uid()::text);

create policy entitlements_isolation on public.entitlements
  using (user_id = auth.uid()::text);

create policy runs_isolation on public.runs
  using (tenant_id::text = auth.jwt()->>'tenant_id');

create policy run_jobs_isolation on public.run_jobs
  using (tenant_id::text = auth.jwt()->>'tenant_id');

create policy run_events_isolation on public.run_events
  using (tenant_id::text = auth.jwt()->>'tenant_id');

create policy run_summaries_isolation on public.run_summaries
  using (tenant_id::text = auth.jwt()->>'tenant_id');

create policy usage_isolation on public.usage_counters_daily
  using (tenant_id::text = auth.jwt()->>'tenant_id');

create policy artifacts_isolation on public.artifacts
  using (tenant_id::text = auth.jwt()->>'tenant_id');
