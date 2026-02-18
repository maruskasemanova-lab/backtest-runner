-- Public market-data bucket + manifest table for shared read-only datasets.

insert into storage.buckets (id, name, public)
values ('market-data', 'market-data', true)
on conflict (id) do update set public = excluded.public;

create table if not exists public.market_data_manifest (
  id bigserial primary key,
  ticker text not null,
  schema text not null,
  dataset text not null default 'XNAS.ITCH',
  start_date date not null,
  end_date date not null,
  file_mbn text,
  file_parquet text,
  file_csv text,
  size_bytes bigint not null default 0,
  row_count bigint not null default 0,
  source_root text not null default 'supabase-storage',
  status text not null default 'ready',
  downloaded_at timestamptz,
  uploaded_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_market_data_manifest_ticker_schema_dates
  on public.market_data_manifest(ticker, schema, start_date, end_date);
create unique index if not exists idx_market_data_manifest_unique_object
  on public.market_data_manifest(ticker, schema, start_date, end_date, coalesce(file_parquet, file_csv, file_mbn));

alter table public.market_data_manifest enable row level security;

grant select on public.market_data_manifest to anon, authenticated;

drop policy if exists market_data_manifest_public_read on public.market_data_manifest;
create policy market_data_manifest_public_read
  on public.market_data_manifest
  for select
  using (true);

drop policy if exists market_data_manifest_service_role_write on public.market_data_manifest;
create policy market_data_manifest_service_role_write
  on public.market_data_manifest
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
