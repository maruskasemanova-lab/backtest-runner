-- Align Supabase run_jobs with the local v2 queue schema so Realtime consumers
-- can observe retries/idempotent replays with the same metadata shape.

alter table public.run_jobs
  add column if not exists idempotency_key text;

alter table public.run_jobs
  add column if not exists attempts integer not null default 0;

alter table public.run_jobs
  add column if not exists max_attempts integer not null default 1;

create unique index if not exists idx_run_jobs_user_type_idempotency
  on public.run_jobs(user_id, job_type, idempotency_key)
  where idempotency_key is not null;
