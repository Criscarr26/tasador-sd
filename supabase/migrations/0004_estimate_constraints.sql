-- Defense in depth for saved_estimates. RLS already stops a user from
-- touching other users' rows, but clients write straight to PostgREST
-- with the user's own token, so a tampered client could still insert
-- garbage VALUES into its own history. These CHECK constraints mirror
-- the shared domain ranges (tasador_core.schema) at the database edge.
--
-- Apply in the Supabase dashboard: SQL Editor > New query > paste > Run.

alter table public.saved_estimates
  add constraint saved_estimates_sector_known check (
    sector in (
      'Piantini','Naco','Serrallés','Bella Vista','Arroyo Hondo',
      'Los Prados','Gazcue','Santo Domingo Este','Villa Mella','Los Alcarrizos'
    )
  ),
  add constraint saved_estimates_area check (area_m2 between 20 and 1000),
  add constraint saved_estimates_bedrooms check (bedrooms between 0 and 10),
  add constraint saved_estimates_bathrooms check (bathrooms between 1 and 10),
  add constraint saved_estimates_parking check (parking_spots between 0 and 10),
  add constraint saved_estimates_age check (age_years between 0 and 80),
  add constraint saved_estimates_price check (predicted_price between 0 and 5000000),
  add constraint saved_estimates_label_len check (char_length(label) between 1 and 120);
