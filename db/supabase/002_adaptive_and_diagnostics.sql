-- Adaptive strategy profile + diagnostic payload cache extensions.
-- Keeps per-user and global adaptive scopes, with tenant isolation and admin-only global writes.

create table if not exists public.adaptive_strategy_profiles (
  profile_id text primary key,
  scope text not null check (scope in ('user', 'global')),
  owner_user_id text references public.users(id) on delete cascade,
  owner_tenant_id uuid references public.tenants(id) on delete cascade,
  ticker text not null,
  profile_name text not null,
  adaptive_version integer not null default 1,
  candidate jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint adaptive_strategy_profiles_scope_owner_ck check (
    (scope = 'global' and owner_user_id is null and owner_tenant_id is null)
    or
    (scope = 'user' and owner_user_id is not null and owner_tenant_id is not null)
  )
);

create index if not exists idx_adaptive_profiles_scope_owner_ticker_updated_at
  on public.adaptive_strategy_profiles(scope, owner_user_id, owner_tenant_id, ticker, updated_at desc);

create table if not exists public.diagnostic_payload_cache (
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cache_key text not null,
  ticker text not null,
  profile text not null,
  phase integer not null,
  source_path text not null,
  source_mtime_ns bigint not null,
  payload_gzip bytea not null,
  payload_sha256 text not null,
  payload_size_bytes integer not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, cache_key)
);

create index if not exists idx_diagnostic_cache_lookup
  on public.diagnostic_payload_cache(tenant_id, ticker, profile, phase, source_mtime_ns);

alter table public.adaptive_strategy_profiles enable row level security;
alter table public.diagnostic_payload_cache enable row level security;

create policy adaptive_profiles_select_isolation on public.adaptive_strategy_profiles
  for select
  using (
    scope = 'global'
    or owner_tenant_id::text = auth.jwt()->>'tenant_id'
  );

create policy adaptive_profiles_modify_isolation on public.adaptive_strategy_profiles
  for all
  using (
    (
      scope = 'global'
      and (
        coalesce(auth.jwt()->>'role', '') = 'admin'
        or coalesce(auth.jwt()->>'plan_tier', '') = 'admin'
      )
    )
    or (
      scope = 'user'
      and owner_tenant_id::text = auth.jwt()->>'tenant_id'
    )
  )
  with check (
    (
      scope = 'global'
      and (
        coalesce(auth.jwt()->>'role', '') = 'admin'
        or coalesce(auth.jwt()->>'plan_tier', '') = 'admin'
      )
    )
    or (
      scope = 'user'
      and owner_tenant_id::text = auth.jwt()->>'tenant_id'
    )
  );

create policy diagnostic_cache_isolation on public.diagnostic_payload_cache
  for all
  using (tenant_id::text = auth.jwt()->>'tenant_id')
  with check (tenant_id::text = auth.jwt()->>'tenant_id');
