-- User-scoped dataset metadata registry for private parquet/object-storage uploads.
-- Backing store for `/api/v2/datasets`.

create table if not exists public.user_datasets (
  dataset_id text primary key,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id text not null references public.users(id) on delete cascade,
  dataset_name text not null,
  source_filename text,
  s3_path text not null,
  status text not null default 'ready',
  file_format text not null default 'parquet',
  source_format text,
  row_count bigint,
  size_bytes bigint,
  schema_name text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_user_datasets_user_updated_at
  on public.user_datasets(user_id, updated_at desc);

create index if not exists idx_user_datasets_user_status_updated_at
  on public.user_datasets(user_id, status, updated_at desc);

alter table public.user_datasets enable row level security;

drop policy if exists user_datasets_isolation on public.user_datasets;
create policy user_datasets_isolation on public.user_datasets
  for all
  using (user_id = auth.uid()::text)
  with check (user_id = auth.uid()::text);
