import { createClient, SupabaseClient } from '@supabase/supabase-js';

// Same Supabase project as the mobile app: one account, one appraisal
// history, shared across devices. Without credentials the estimator
// still works; only the history is disabled.
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const isCloudConfigured = Boolean(url && anonKey);

export const supabase: SupabaseClient | null = isCloudConfigured
  ? createClient(url!, anonKey!)
  : null;

export interface SavedEstimate {
  id: string;
  label: string;
  sector: string;
  area_m2: number;
  bedrooms: number;
  bathrooms: number;
  parking_spots: number;
  furnished: boolean;
  age_years: number;
  predicted_price: number;
  created_at: string;
}
