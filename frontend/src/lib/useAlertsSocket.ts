import { useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { WS_URL } from "./api"
import type { Alert } from "../types"

/** Mantiene la caché de React Query ('alerts', 'assets') sincronizada con
 * el WebSocket del backend (UC1: alerta en tiempo real sin recargar). */
export function useAlertsSocket(token: string | null) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!token) return

    const socket = new WebSocket(`${WS_URL}/ws/alerts?token=${encodeURIComponent(token)}`)

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data) as { type: string; alert: Alert }
      if (data.type !== "alert") return

      queryClient.setQueryData<Alert[]>(["alerts"], (prev) => (prev ? [data.alert, ...prev] : [data.alert]))
      queryClient.invalidateQueries({ queryKey: ["assets"] })
    }

    return () => socket.close()
  }, [token, queryClient])
}
