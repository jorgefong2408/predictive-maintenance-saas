import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { useAlertsSocket } from "./useAlertsSocket"

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  url: string
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  closed = false

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  close() {
    this.closed = true
  }
}

let originalWebSocket: typeof WebSocket

beforeEach(() => {
  FakeWebSocket.instances = []
  originalWebSocket = window.WebSocket
  // @ts-expect-error -- stub mínimo, no implementa toda la interfaz WebSocket
  window.WebSocket = FakeWebSocket
  vi.useFakeTimers()
})

afterEach(() => {
  window.WebSocket = originalWebSocket
  vi.useRealTimers()
})

function renderSocket(token: string | null) {
  const queryClient = new QueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return renderHook(({ token }) => useAlertsSocket(token), { initialProps: { token }, wrapper })
}

describe("useAlertsSocket (reconexión)", () => {
  it("abre un WebSocket con el token en la URL", () => {
    renderSocket("un-token")
    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(FakeWebSocket.instances[0].url).toContain("/ws/alerts?token=un-token")
  })

  it("NO reconecta cuando el cierre es por token inválido (4401)", () => {
    renderSocket("un-token")
    FakeWebSocket.instances[0].onclose?.({ code: 4401 })

    vi.advanceTimersByTime(60_000)

    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it("reconecta con backoff tras un cierre inesperado (ej. backend reiniciado)", () => {
    renderSocket("un-token")
    FakeWebSocket.instances[0].onclose?.({ code: 1006 })

    // primer intento: 1s de espera
    vi.advanceTimersByTime(999)
    expect(FakeWebSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(FakeWebSocket.instances).toHaveLength(2)
  })

  it("el backoff crece si el reintento también falla antes de abrir", () => {
    renderSocket("un-token")
    FakeWebSocket.instances[0].onclose?.({ code: 1006 })
    vi.advanceTimersByTime(1000)
    expect(FakeWebSocket.instances).toHaveLength(2)

    // segundo fallo consecutivo (sin onopen de por medio) -> backoff x2 = 2s
    FakeWebSocket.instances[1].onclose?.({ code: 1006 })
    vi.advanceTimersByTime(1999)
    expect(FakeWebSocket.instances).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(FakeWebSocket.instances).toHaveLength(3)
  })

  it("resetea el backoff a 1s tras una reconexión exitosa (onopen)", () => {
    renderSocket("un-token")
    FakeWebSocket.instances[0].onclose?.({ code: 1006 })
    vi.advanceTimersByTime(1000)
    expect(FakeWebSocket.instances).toHaveLength(2)

    FakeWebSocket.instances[1].onopen?.()
    FakeWebSocket.instances[1].onclose?.({ code: 1006 })

    vi.advanceTimersByTime(999)
    expect(FakeWebSocket.instances).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(FakeWebSocket.instances).toHaveLength(3)
  })

  it("cierra el socket y cancela el reintento pendiente al desmontar", () => {
    const { unmount } = renderSocket("un-token")
    const first = FakeWebSocket.instances[0]
    first.onclose?.({ code: 1006 })

    unmount()
    expect(first.closed).toBe(true)

    vi.advanceTimersByTime(60_000)
    expect(FakeWebSocket.instances).toHaveLength(1)
  })
})
