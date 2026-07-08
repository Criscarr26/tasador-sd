-- Plans and usage foundation: the groundwork for freemium without any
-- payment integration yet. Enforcement lives in the database (triggers),
-- so no client can bypass it.
--
-- Apply in the Supabase dashboard: SQL Editor > New query > paste > Run.

-- Every user has a profile with a plan (free until payments exist).
create table public.profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  plan text not null default 'free' check (plan in ('free', 'pro', 'agency')),
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "Users can read their own profile"
  on public.profiles for select
  using (auth.uid() = user_id);

-- Auto-create the profile on signup.
create or replace function public.handle_new_user()
returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (user_id) values (new.id) on conflict do nothing;
  return new;
end $$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Backfill profiles for users that signed up before this migration.
insert into public.profiles (user_id)
select id from auth.users
on conflict do nothing;

-- Monthly appraisal counters per user.
create table public.usage_counters (
  user_id uuid not null references auth.users (id) on delete cascade,
  period text not null, -- 'YYYY-MM'
  appraisals integer not null default 0,
  primary key (user_id, period)
);

alter table public.usage_counters enable row level security;

create policy "Users can read their own usage"
  on public.usage_counters for select
  using (auth.uid() = user_id);

-- Plan caps. NULL means unlimited. Tune freely: it is one row of logic.
create or replace function public.plan_limit(p text)
returns integer
language sql immutable as $$
  select case p when 'free' then 100 else null end
$$;

-- Count every saved appraisal and reject the insert once the monthly
-- cap is reached. Clients already surface insert errors to the user.
create or replace function public.count_appraisal()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  current_period text := to_char(now(), 'YYYY-MM');
  user_plan text;
  used integer;
  cap integer;
begin
  select plan into user_plan from profiles where user_id = new.user_id;
  cap := plan_limit(coalesce(user_plan, 'free'));

  insert into usage_counters (user_id, period)
  values (new.user_id, current_period)
  on conflict (user_id, period) do nothing;

  select appraisals into used
  from usage_counters
  where user_id = new.user_id and period = current_period
  for update;

  if cap is not null and used >= cap then
    raise exception 'Límite mensual del plan alcanzado (% tasaciones). Mejora tu plan para continuar.', cap;
  end if;

  update usage_counters
  set appraisals = appraisals + 1
  where user_id = new.user_id and period = current_period;

  return new;
end $$;

create trigger on_saved_estimate_insert
  before insert on public.saved_estimates
  for each row execute function public.count_appraisal();
