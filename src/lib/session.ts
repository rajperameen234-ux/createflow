import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import { useCallback, useEffect, useState } from 'react'

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

export const supabaseConfigured = Boolean(url && anonKey)

export function getSupabase(): SupabaseClient | null {
  if (!supabaseConfigured) return null
  return createClient(url as string, anonKey as string, {
    auth: { persistSession: true, autoRefreshToken: true },
  })
}

export interface SessionState {
  ready: boolean
  token: string | null
  email: string | null
  userId: string | null
  configured: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<{ needsConfirmation: boolean }>
  signOut: () => Promise<void>
}

export function useSession(): SessionState {
  const [token, setToken] = useState<string | null>(null)
  const [email, setEmail] = useState<string | null>(null)
  const [userId, setUserId] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const client = getSupabase()
    if (!client) {
      setReady(true)
      return
    }
    let active = true
    void client.auth.getSession().then(({ data }) => {
      if (!active) return
      setToken(data.session?.access_token ?? null)
      setEmail(data.session?.user.email ?? null)
      setUserId(data.session?.user.id ?? null)
      setReady(true)
    })
    const { data: sub } = client.auth.onAuthStateChange((_event, session) => {
      setToken(session?.access_token ?? null)
      setEmail(session?.user.email ?? null)
      setUserId(session?.user.id ?? null)
      setReady(true)
    })
    return () => {
      active = false
      sub.subscription.unsubscribe()
    }
  }, [])

  const signIn = useCallback(async (address: string, password: string) => {
    const client = getSupabase()
    if (!client) throw new Error('Supabase is not configured in this environment.')
    const { error } = await client.auth.signInWithPassword({ email: address, password })
    if (error) throw new Error(error.message)
  }, [])

  const signUp = useCallback(async (address: string, password: string) => {
    const client = getSupabase()
    if (!client) throw new Error('Supabase is not configured in this environment.')
    const { data, error } = await client.auth.signUp({ email: address, password })
    if (error) throw new Error(error.message)
    return { needsConfirmation: !data.session }
  }, [])

  const signOut = useCallback(async () => {
    const client = getSupabase()
    if (!client) return
    await client.auth.signOut()
  }, [])

  return { ready, token, email, userId, configured: supabaseConfigured, signIn, signUp, signOut }
}