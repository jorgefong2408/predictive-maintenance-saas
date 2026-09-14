import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import MockAdapter from "axios-mock-adapter"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { api } from "../lib/api"
import { renderWithProviders } from "../test/test-utils"
import type { Asset } from "../types"
import { AssetListPage } from "./AssetListPage"

let mock: MockAdapter

const assets: Asset[] = [
  {
    id: "asset-ok",
    name: "Mill-01",
    asset_type: "cnc_milling_machine",
    external_ref: null,
    status: "ok",
    metadata: {},
    created_at: new Date().toISOString(),
  },
  {
    id: "asset-critical",
    name: "Mill-02",
    asset_type: "cnc_milling_machine",
    external_ref: null,
    status: "critical",
    metadata: {},
    created_at: new Date().toISOString(),
  },
  {
    id: "asset-warning",
    name: "Mill-03",
    asset_type: "cnc_milling_machine",
    external_ref: null,
    status: "warning",
    metadata: {},
    created_at: new Date().toISOString(),
  },
]

beforeEach(() => {
  mock = new MockAdapter(api)
})

afterEach(() => {
  mock.restore()
})

describe("AssetListPage", () => {
  it("muestra 'Sin activos todavía' cuando la lista está vacía", async () => {
    mock.onGet("/assets").reply(200, [])
    renderWithProviders(<AssetListPage />)

    expect(await screen.findByText("Sin activos todavía — crea el primero.")).toBeInTheDocument()
  })

  it("ordena los activos por severidad: critical, warning, ok", async () => {
    mock.onGet("/assets").reply(200, assets)
    renderWithProviders(<AssetListPage />)

    await screen.findByText("Mill-02")
    const items = screen.getAllByRole("listitem")
    expect(within(items[0]).getByText("Mill-02")).toBeInTheDocument()
    expect(within(items[1]).getByText("Mill-03")).toBeInTheDocument()
    expect(within(items[2]).getByText("Mill-01")).toBeInTheDocument()
  })

  it("cada activo enlaza a /assets/:id", async () => {
    mock.onGet("/assets").reply(200, assets)
    renderWithProviders(<AssetListPage />)

    await screen.findByText("Mill-01")
    expect(screen.getByRole("link", { name: /Mill-01/ })).toHaveAttribute("href", "/assets/asset-ok")
  })

  it("crea un activo nuevo y refresca la lista (UC de alta de activos)", async () => {
    const user = userEvent.setup()
    mock.onGet("/assets").replyOnce(200, []).onGet("/assets").reply(200, [assets[0]])
    mock.onPost("/assets").reply((config) => {
      const body = JSON.parse(config.data)
      expect(body).toMatchObject({ name: "Mill-01", asset_type: "cnc_milling_machine" })
      return [201, assets[0]]
    })
    renderWithProviders(<AssetListPage />)

    await screen.findByText("Sin activos todavía — crea el primero.")
    await user.click(screen.getByRole("button", { name: "+ Nuevo activo" }))
    await user.type(screen.getByLabelText("Nombre"), "Mill-01")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(screen.getByText("Mill-01")).toBeInTheDocument())
    expect(mock.history.post).toHaveLength(1)
    // el formulario se cierra tras crear
    expect(screen.queryByLabelText("Nombre")).not.toBeInTheDocument()
  })
})
