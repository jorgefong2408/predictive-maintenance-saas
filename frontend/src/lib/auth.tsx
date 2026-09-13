import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { api } from "./api"

interface JwtClaims {
  sub: string
  tenant_id: string
  role: string
  exp: number
}

function decodeJwt(token: string): JwtClaims | null {
  try {
    const payload = token.split(".")[1]
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"))
    return JSON.parse(json) as JwtClaims
  } catch {
    return null
  }
}

interface AuthState {
  token: string | null
  claims: JwtClaims | null
  login: (email: string, password: string) => Promise<void>
  register: (params: {
    tenantName: string
    tenantSlug: string
    adminEmail: string
    adminPassword: string
  }) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("access_token"))

  useEffect(() => {
    if (token) {
      localStorage.setItem("access_token", token)
    } else {
      localStorage.removeItem("access_token")
    }
  }, [token])

  const claims = useMemo(() => (token ? decodeJwt(token) : null), [token])

  async function login(email: string, password: string) {
    const form = new URLSearchParams()
    form.set("username", email)
    form.set("password", password)
    const resp = await api.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    })
    setToken(resp.data.access_token)
  }

  async function register(params: {
    tenantName: string
    tenantSlug: string
    adminEmail: string
    adminPassword: string
  }) {
    const resp = await api.post("/auth/register", {
      tenant_name: params.tenantName,
      tenant_slug: params.tenantSlug,
      admin_email: params.adminEmail,
      admin_password: params.adminPassword,
    })
    setToken(resp.data.access_token)
  }

  function logout() {
    setToken(null)
  }

  return (
    <AuthContext.Provider value={{ token, claims, login, register, logout }}>{children}</AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>")
  return ctx
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  return children
}
