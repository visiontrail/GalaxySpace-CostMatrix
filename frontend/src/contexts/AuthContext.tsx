import { createContext, useCallback, useContext, useEffect, useMemo, useState, ReactNode } from 'react'
import { login as loginApi, fetchCurrentUser } from '@/services/api'
import type { UserInfo } from '@/types'

interface AuthContextValue {
  user: UserInfo | null
  token: string | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const TOKEN_KEY = 'cm_auth_token'

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export const useAuth = (): AuthContextValue => {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [loading, setLoading] = useState<boolean>(true)

  const refreshUser = useCallback(async () => {
    if (!token) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const userInfo = await fetchCurrentUser()
      setUser(userInfo)
    } catch (error) {
      setUser(null)
      setToken(null)
      localStorage.removeItem(TOKEN_KEY)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    refreshUser()
  }, [refreshUser])

  const login = useCallback(async (username: string, password: string) => {
    const res = await loginApi({ username, password })
    localStorage.setItem(TOKEN_KEY, res.access_token)
    setToken(res.access_token)
    setUser(res.user)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      login,
      logout,
      refreshUser,
    }),
    [user, token, loading, login, logout, refreshUser]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
