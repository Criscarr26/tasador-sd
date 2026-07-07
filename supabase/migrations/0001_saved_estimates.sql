-- Baseline migration: the appraisal history table used by the mobile app.
-- NOTE: this already exists in production (applied manually on 2026-07-06
-- from the mobile repo's supabase/schema.sql). It is recorded here so the
-- migration history matches the deployed database from now on.

create table public.saved_estimates (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  label text not null,
  sector text not null,
  area_m2 numeric not null,
  bedrooms integer not null,
  bathrooms integer not null,
  parking_spots integer not null,
  furnished boolean not null,
  age_years integer not null,
  predicted_price numeric not null,
  created_at timestamptz not null default now()
);

-- Row Level Security: each user can only see and touch their own rows.
alter table public.saved_estimates enable row level security;

create policy "Users can read their own estimates"
  on public.saved_estimates for select
  using (auth.uid() = user_id);

create policy "Users can insert their own estimates"
  on public.saved_estimates for insert
  with check (auth.uid() = user_id);

create policy "Users can delete their own estimates"
  on public.saved_estimates for delete
  using (auth.uid() = user_id);
