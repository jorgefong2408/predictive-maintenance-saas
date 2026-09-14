import { useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { WS_URL } from "./api"
import type { Alert } from "../types"

// El backend cierra con este código cuando el token es inválido/expiró (ver
// app/api/ws.py) — reintentar en ese caso solo repetiría el mismo rechazo.
const INVALID_TOKEN_CLOSE_CODE = 4401
const MAX_RECONNECT_DELAY_MS = 30_000

/** Mantiene la caché de React Query ('alerts', 'assets') sincronizada con
 * el WebSocket del backend (UC1: alerta en tiempo real sin recargar).
 * Reconecta con backoff exponencial ante caídas de red o reinicios del
 * backend (ej. redeploy) — antes, cualquier corte dejaba el panel de
 * alertas muerto en silencio hasta recargar la página a mano. */
export function useAlertsSocket(token: string | null) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!token) return

    let cancelled = false
    let socket: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let attempt = 0

    function connect() {
      socket = new WebSocket(`${WS_URL}/ws/alerts?token=${encodeURIComponent(token as string)}`)

      socket.onopen = () => {
        attempt = 0
      }

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data) as { type: string; alert: Alert }
        if (data.type !== "alert") return

        queryClient.setQueryData<Alert[]>(["alerts"], (prev) => (prev ? [data.alert, ...prev] : [data.alert]))
        queryClient.invalidateQueries({ queryKey: ["assets"] })
      }

      socket.onclose = (event) => {
        if (cancelled || event.code === INVALID_TOKEN_CLOSE_CODE) return
        const delay = Math.min(1000 * 2 ** attempt, MAX_RECONNECT_DELAY_MS)
        attempt += 1
        reconnectTimer = setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [token, queryClient])
}
