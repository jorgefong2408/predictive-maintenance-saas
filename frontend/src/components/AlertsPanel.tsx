import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { api } from "../lib/api"
import type { Alert } from "../types"

const SEVERITY_DOT: Record<Alert["severity"], string> = {
  info: "bg-slate-400",
  warning: "bg-amber-500",
  critical: "bg-red-500",
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso + (iso.endsWith("Z") ? "" : "Z")).getTime()
  const minutes = Math.max(0, Math.round(diffMs / 60000))
  if (minutes < 1) return "ahora"
  if (minutes < 60) return `hace ${minutes}m`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `hace ${hours}h`
  return `hace ${Math.round(hours / 24)}d`
}

export function AlertsPanel() {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()

  const { data: alerts = [] } = useQuery({
    queryKey: ["alerts"],
    queryFn: async () => (await api.get<Alert[]>("/alerts", { params: { active_only: true } })).data,
    refetchInterval: 30_000,
  })

  async function acknowledge(id: string) {
    await api.post(`/alerts/${id}/acknowledge`)
    queryClient.invalidateQueries({ queryKey: ["alerts"] })
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        Alertas 🔔
        {alerts.length > 0 && (
          <span className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-red-600 text-xs font-bold text-white">
            {alerts.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 w-96 rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
            <h3 className="text-sm font-semibold text-slate-900">Alertas activas ({alerts.length})</h3>
            <button onClick={() => setOpen(false)} className="text-xs text-slate-400 hover:text-slate-600">
              cerrar
            </button>
          </div>
          <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
            {alerts.length === 0 && <li className="px-4 py-6 text-center text-sm text-slate-400">Sin alertas activas</li>}
            {alerts.map((alert) => (
              <li key={alert.id} className="flex items-start gap-2 px-4 py-3 text-sm">
                <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${SEVERITY_DOT[alert.severity]}`} />
                <div className="flex-1">
                  <p className="text-slate-800">{alert.message}</p>
                  <p className="text-xs text-slate-400">{timeAgo(alert.triggered_at)}</p>
                </div>
                <button
                  onClick={() => acknowledge(alert.id)}
                  className="shrink-0 rounded border border-slate-200 px-2 py-0.5 text-xs text-slate-500 hover:bg-slate-50"
                >
                  Marcar ✓
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
