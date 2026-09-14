import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import MockAdapter from "axios-mock-adapter"
import { Route, Routes } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { api } from "../lib/api"
import { renderWithProviders } from "../test/test-utils"
import { RegisterPage } from "./RegisterPage"

let mock: MockAdapter

beforeEach(() => {
  mock = new MockAdapter(api)
  localStorage.clear()
})

afterEach(() => {
  mock.restore()
})

function renderRegisterPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/" element={<RegisterPage />} />
      <Route path="/assets" element={<div>lista de activos</div>} />
    </Routes>,
  )
}

describe("RegisterPage", () => {
  it("deriva el slug del nombre de la empresa en vivo", async () => {
    const user = userEvent.setup()
    renderRegisterPage()

    await user.type(screen.getByLabelText("Nombre de la empresa"), "Acme Manufacturing Co.")

    expect(screen.getByText("slug: acme-manufacturing-co")).toBeInTheDocument()
  })

  it("registra el tenant y navega a /assets, mandando el slug derivado", async () => {
    const user = userEvent.setup()
    mock.onPost("/auth/register").reply((config) => {
      const body = JSON.parse(config.data)
      expect(body).toMatchObject({
        tenant_name: "Acme Manufacturing",
        tenant_slug: "acme-manufacturing",
        admin_email: "admin@acme.com",
      })
      return [201, { access_token: "un-token", token_type: "bearer" }]
    })
    renderRegisterPage()

    await user.type(screen.getByLabelText("Nombre de la empresa"), "Acme Manufacturing")
    await user.type(screen.getByLabelText("Email del admin"), "admin@acme.com")
    await user.type(screen.getByLabelText("Password"), "supersecret123")
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }))

    await waitFor(() => expect(screen.getByText("lista de activos")).toBeInTheDocument())
  })

  it("muestra el error cuando el slug ya existe (409)", async () => {
    const user = userEvent.setup()
    mock.onPost("/auth/register").reply(409, { detail: "El slug de tenant ya existe" })
    renderRegisterPage()

    await user.type(screen.getByLabelText("Nombre de la empresa"), "Acme Manufacturing")
    await user.type(screen.getByLabelText("Email del admin"), "admin@acme.com")
    await user.type(screen.getByLabelText("Password"), "supersecret123")
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }))

    expect(await screen.findByText("El slug de tenant ya existe")).toBeInTheDocument()
  })
})
