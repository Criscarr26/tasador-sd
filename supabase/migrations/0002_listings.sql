-- Market listings collected by the data agent. This is training data,
-- not user data: RLS is enabled with NO policies on purpose, so only
-- the service role (the agent, the retraining pipeline) can touch it.
-- Clients never read this table directly.
--
-- Apply in the Supabase dashboard: SQL Editor > New query > paste > Run.

create table public.listings (
  id uuid primary key default gen_random_uuid(),
  sector text not null,
  area_m2 numeric not null,
  bedrooms integer not null,
  bathrooms integer not null,
  parking_spots integer not null,
  furnished boolean not null,
  age_years integer not null,
  price_dop numeric not null,
  source_url text not null unique,
  run_id text,
  collected_at timestamptz not null default now()
);

alter table public.listings enable row level security;

-- Dedupe is enforced by the unique constraint on source_url: the agent
-- upserts with on_conflict=source_url so re-running a collection is safe.
