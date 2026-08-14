const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const rawSupabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseUrl = rawSupabaseUrl
  ? rawSupabaseUrl.replace(/\/rest\/v1\/?$/, '').replace(/\/+$/, '')
  : undefined
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const config = {
  apiUrl: apiUrl.replace(/\/$/, ''),
  hasSupabaseAuth: Boolean(supabaseUrl && supabaseAnonKey),
  supabaseUrl,
  supabaseAnonKey,
}
