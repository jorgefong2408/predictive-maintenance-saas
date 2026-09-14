import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import MockAdapter from "axios-mock-adapter"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { api } from "../lib/api"
import { renderWithProviders } from "../test/test-utils"
import type { Asset } from "../types"
import { AssetListPage } from "./AssetListPage"

let mock: MockAdapter

function makeAssets(names: string[]): Asset[] {
  return names.map((name, i) => ({
    id: `asset-${i}`,
    name,
    asset_type: "cnc_milling_machine",
    external_ref: null,
    status: "ok",
    metadata: {},
    created_at: new Date().toISOString(),
  }))
}

const threeAssets = makeAssets(["Mill-01", "Mill-02", "Mill-03"])

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

  it("pide limit=21 y offset=0 en la primera página (el backend ya ordena por severidad)", async () => {
    let capturedParams: unknown
    mock.onGet("/assets").reply((config) => {
      capturedParams = config.params
      return [200, threeAssets]
    })
    renderWithProviders(<AssetListPage />)

    await screen.findByText("Mill-01")
    expect(capturedParams).toEqual({ limit: 21, offset: 0 })
  })

  it("renderiza los activos en el orden que devuelve el backend", async () => {
    mock.onGet("/assets").reply(200, threeAssets)
    renderWithProviders(<AssetListPage />)

    await screen.findByText("Mill-01")
    const items = screen.getAllByRole("listitem")
    expect(within(items[0]).getByText("Mill-01")).toBeInTheDocument()
    expect(within(items[1]).getByText("Mill-02")).toBeInTheDocument()
    expect(within(items[2]).getByText("Mill-03")).toBeInTheDocument()
  })

  it("cada activo enlaza a /assets/:id", async () => {
    mock.onGet("/assets").reply(200, threeAssets)
    renderWithProviders(<AssetListPage />)

    await screen.findByText("Mill-01")
    expect(screen.getByRole("link", { name: /Mill-01/ })).toHaveAttribute("href", "/assets/asset-0")
  })

  it("crea un activo nuevo y refresca la lista (UC de alta de activos)", async () => {
    const user = userEvent.setup()
    mock.onGet("/assets").replyOnce(200, []).onGet("/assets").reply(200, [threeAssets[0]])
    mock.onPost("/assets").reply((config) => {
      const body = JSON.parse(config.data)
      expect(body).toMatchObject({ name: "Mill-01", asset_type: "cnc_milling_machine" })
      return [201, threeAssets[0]]
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

  it("no muestra controles de paginación cuando todo cabe en una sola página", async () => {
    mock.onGet("/assets").reply(200, threeAssets)
    renderWithProviders(<AssetListPage />)

    await screen.findByText("Mill-01")
    expect(screen.queryByRole("button", { name: /Siguiente/ })).not.toBeInTheDocument()
  })

  it("muestra 'Siguiente' habilitado cuando hay más de PAGE_SIZE activos y avanza de página", async () => {
    const user = userEvent.setup()
    const page0 = makeAssets(Array.from({ length: 21 }, (_, i) => `Mill-${i.toString().padStart(2, "0")}`))
    const page1 = makeAssets(["Mill-21"])

    mock.onGet("/assets").reply((config) => {
      if (config.params.offset === 0) return [200, page0]
      if (config.params.offset === 20) return [200, page1]
      return [200, []]
    })
    renderWithProviders(<AssetListPage />)

    await screen.findByText("Mill-00")
    // el elemento 21 (de más, para detectar hasNextPage) no se muestra en esta página
    expect(screen.queryByText("Mill-20")).not.toBeInTheDocument()
    expect(screen.getAllByRole("listitem")).toHaveLength(20)

    const next = screen.getByRole("button", { name: /Siguiente/ })
    expect(next).toBeEnabled()
    await user.click(next)

    await screen.findByText("Mill-21")
    expect(screen.getByText("Página 2")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Siguiente/ })).toBeDisabled()

    await user.click(screen.getByRole("button", { name: /Anterior/ }))
    await screen.findByText("Mill-00")
    expect(screen.getByText("Página 1")).toBeInTheDocument()
  })
})
