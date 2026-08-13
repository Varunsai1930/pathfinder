const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const config = {
  apiUrl: apiUrl.replace(/\/$/, ''),
  hasSupabaseAuth: Boolean(supabaseUrl && supabaseAnonKey),
  supabaseUrl,
  supabaseAnonKey,
}
