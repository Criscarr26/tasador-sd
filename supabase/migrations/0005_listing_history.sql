-- Market history: price trajectories, sighting metadata and the
-- discovery queue that feeds the collection agent.
--
-- Why: a listing does not have ONE price, it has a trajectory -- a drop
-- from RD$60k to RD$48k says the original ask was fiction. And a
-- listing that disappears from the portal was probably rented, which is
-- a weak label of "price accepted by the market". Overwriting rows
-- destroys both signals, so price changes are snapshotted by trigger
-- and sightings are tracked per row.
--
-- Same access model as listings (0002): RLS is enabled with NO policies
-- on purpose, so only the service role (the agent, discovery, n8n
-- workflows) can touch these tables. Clients never read them directly.
--
-- Apply in the Supabase dashboard: SQL Editor > New query > paste > Run.

-- 1) Sighting metadata on listings. Writers own the semantics: the
--    agent's upsert and the sitemap discovery refresh last_seen and
--    is_active; first_seen is set once on insert and never changes.
alter table public.listings
  add column first_seen timestamptz not null default now(),
  add column last_seen timestamptz not null default now(),
  add column is_active boolean not null default true;

update public.listings
  set first_seen = collected_at, last_seen = collected_at;

-- 2) Price trajectory: one row per observed price per listing.
--    captured_at defaults to clock_timestamp(), not now(): now() is
--    frozen per transaction, so two price changes of the SAME listing
--    inside one transaction (e.g. a two-step manual fix in the SQL
--    Editor) would collide on the primary key and abort the writer.
create table public.listing_prices (
  listing_id uuid not null references public.listings (id) on delete cascade,
  captured_at timestamptz not null default clock_timestamp(),
  price_dop numeric not null,
  run_id text,
  primary key (listing_id, captured_at)
);

alter table public.listing_prices enable row level security;

-- Seed the history with the price each existing listing was collected at.
insert into public.listing_prices (listing_id, captured_at, price_dop, run_id)
select id, collected_at, price_dop, run_id from public.listings;

-- Snapshot on insert and on every price change, no matter which writer
-- (agent upsert, n8n, a manual fix) touched the row.
create function public.listings_record_price()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'INSERT' or new.price_dop is distinct from old.price_dop then
    insert into public.listing_prices (listing_id, price_dop, run_id)
    values (new.id, new.price_dop, new.run_id);
  end if;
  return null;
end;
$$;

create trigger listings_price_history
after insert or update on public.listings
for each row execute function public.listings_record_price();

-- 3) Discovery queue: sitemap discovery (agents/listings-agent/
--    discovery.py) enqueues candidate detail URLs; collection runs
--    (agent.py --from-queue) pull pending ones and record the outcome.
--    status: pending  -> not scraped yet
--            done     -> scraped and saved as a listing
--            skipped  -> scraped but not eligible (sale, USD-only, ...)
--            failed   -> gave up after 3 fetch errors
create table public.listing_queue (
  url text primary key,
  source text not null default 'supercasas',
  status text not null default 'pending'
    check (status in ('pending', 'done', 'skipped', 'failed')),
  attempts integer not null default 0,
  last_error text,
  discovered_at timestamptz not null default now(),
  scraped_at timestamptz
);

alter table public.listing_queue enable row level security;

create index listing_queue_pending_idx
  on public.listing_queue (discovered_at)
  where status = 'pending';
