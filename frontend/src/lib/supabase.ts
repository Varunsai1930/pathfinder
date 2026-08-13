import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import { config } from './config'

export const supabase: SupabaseClient | null = config.hasSupabaseAuth
  ? createClient(config.supabaseUrl!, config.supabaseAnonKey!)
  : null
