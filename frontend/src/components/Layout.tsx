import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { useAuth } from "../lib/auth"
import { useAlertsSocket } from "../lib/useAlertsSocket"
import { AlertsPanel } from "./AlertsPanel"

export function Layout({ children }: { children: ReactNode }) {
  const { token, claims, logout } = useAuth()
  useAlertsSocket(token)

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <Link to="/assets" className="font-semibold text-slate-900">
          PredictMaint
        </Link>
        <div className="flex items-center gap-3">
          <AlertsPanel />
          <span className="text-xs text-slate-400">{claims?.role}</span>
          <button onClick={logout} className="text-sm text-slate-500 hover:text-slate-800">
            Salir
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  )
}
