-- User-scoped UI settings storage (frontend run-config draft, sidebar prefs, etc.).
-- Used by backend `/api/v2/user/settings` adapter.

create table if not exists public.user_settings (
  user_id text primary key,
  tenant_id text not null,
  settings_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_user_settings_tenant_updated_at
  on public.user_settings(tenant_id, updated_at desc);

alter table public.user_settings enable row level security;

drop policy if exists user_settings_isolation on public.user_settings;
create policy user_settings_isolation on public.user_settings
  for all
  using (user_id = auth.uid()::text)
  with check (user_id = auth.uid()::text);
