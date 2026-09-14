import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import MockAdapter from "axios-mock-adapter"
import { Route, Routes } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { api } from "../lib/api"
import { renderWithProviders } from "../test/test-utils"
import { LoginPage } from "./LoginPage"

let mock: MockAdapter

beforeEach(() => {
  mock = new MockAdapter(api)
  localStorage.clear()
})

afterEach(() => {
  mock.restore()
})

function renderLoginPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/assets" element={<div>lista de activos</div>} />
      <Route path="/register" element={<div>página de registro</div>} />
    </Routes>,
  )
}

describe("LoginPage", () => {
  it("navega a /assets tras un login exitoso", async () => {
    const user = userEvent.setup()
    mock.onPost("/auth/login").reply(200, { access_token: "un-token", token_type: "bearer" })
    renderLoginPage()

    await user.type(screen.getByLabelText("Email"), "admin@acme.com")
    await user.type(screen.getByLabelText("Password"), "supersecret123")
    await user.click(screen.getByRole("button", { name: "Ingresar" }))

    await waitFor(() => expect(screen.getByText("lista de activos")).toBeInTheDocument())
  })

  it("muestra el detail de error del backend cuando el login falla", async () => {
    const user = userEvent.setup()
    mock.onPost("/auth/login").reply(401, { detail: "Email o contraseña incorrectos" })
    renderLoginPage()

    await user.type(screen.getByLabelText("Email"), "admin@acme.com")
    await user.type(screen.getByLabelText("Password"), "wrong")
    await user.click(screen.getByRole("button", { name: "Ingresar" }))

    expect(await screen.findByText("Email o contraseña incorrectos")).toBeInTheDocument()
    // no navegó
    expect(screen.queryByText("lista de activos")).not.toBeInTheDocument()
  })

  it("muestra un mensaje genérico si la respuesta de error no trae 'detail'", async () => {
    const user = userEvent.setup()
    mock.onPost("/auth/login").networkError()
    renderLoginPage()

    await user.type(screen.getByLabelText("Email"), "admin@acme.com")
    await user.type(screen.getByLabelText("Password"), "supersecret123")
    await user.click(screen.getByRole("button", { name: "Ingresar" }))

    expect(await screen.findByText("No se pudo iniciar sesión")).toBeInTheDocument()
  })

  it("tiene un link a /register para crear un tenant nuevo (UC3)", () => {
    renderLoginPage()
    expect(screen.getByRole("link", { name: "Crear tenant" })).toHaveAttribute("href", "/register")
  })
})
