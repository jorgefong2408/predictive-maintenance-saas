import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import MockAdapter from "axios-mock-adapter"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { api } from "../lib/api"
import { renderWithProviders } from "../test/test-utils"
import type { Alert } from "../types"
import { AlertsPanel } from "./AlertsPanel"

let mock: MockAdapter

const alerts: Alert[] = [
  {
    id: "a1",
    asset_id: "asset-1",
    triggered_at: new Date().toISOString(),
    severity: "critical",
    alert_type: "temperature_high",
    message: "Temperatura fuera de rango",
    acknowledged_at: null,
    resolved_at: null,
  },
]

beforeEach(() => {
  mock = new MockAdapter(api)
})

afterEach(() => {
  mock.restore()
})

describe("AlertsPanel", () => {
  it("no muestra el badge de conteo cuando no hay alertas activas", async () => {
    mock.onGet("/alerts").reply(200, [])
    renderWithProviders(<AlertsPanel />)

    await waitFor(() => expect(mock.history.get.length).toBeGreaterThan(0))
    expect(screen.queryByText("0")).not.toBeInTheDocument()
  })

  it("muestra el conteo de alertas activas en el badge", async () => {
    mock.onGet("/alerts").reply(200, alerts)
    renderWithProviders(<AlertsPanel />)

    expect(await screen.findByText("1")).toBeInTheDocument()
  })

  it("abre el panel y muestra el mensaje de la alerta", async () => {
    const user = userEvent.setup()
    mock.onGet("/alerts").reply(200, alerts)
    renderWithProviders(<AlertsPanel />)

    await screen.findByText("1")
    await user.click(screen.getByRole("button", { name: /Alertas/ }))

    expect(screen.getByText("Temperatura fuera de rango")).toBeInTheDocument()
  })

  it("muestra 'Sin alertas activas' cuando la lista está vacía y el panel está abierto", async () => {
    const user = userEvent.setup()
    mock.onGet("/alerts").reply(200, [])
    renderWithProviders(<AlertsPanel />)

    await waitFor(() => expect(mock.history.get.length).toBeGreaterThan(0))
    await user.click(screen.getByRole("button", { name: /Alertas/ }))

    expect(screen.getByText("Sin alertas activas")).toBeInTheDocument()
  })

  it("marca la alerta como reconocida y la quita de la lista (UC1)", async () => {
    const user = userEvent.setup()
    mock.onGet("/alerts").replyOnce(200, alerts).onGet("/alerts").reply(200, [])
    mock.onPost("/alerts/a1/acknowledge").reply(200, { ...alerts[0], acknowledged_at: new Date().toISOString() })
    renderWithProviders(<AlertsPanel />)

    await screen.findByText("1")
    await user.click(screen.getByRole("button", { name: /Alertas/ }))
    await user.click(screen.getByRole("button", { name: "Marcar ✓" }))

    await waitFor(() => expect(screen.getByText("Sin alertas activas")).toBeInTheDocument())
    expect(mock.history.post).toHaveLength(1)
  })
})
