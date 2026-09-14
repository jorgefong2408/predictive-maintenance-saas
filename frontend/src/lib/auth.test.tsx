import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import MockAdapter from "axios-mock-adapter"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { api } from "./api"
import { AuthProvider, RequireAuth, useAuth } from "./auth"

let mock: MockAdapter

beforeEach(() => {
  mock = new MockAdapter(api)
  localStorage.clear()
})

afterEach(() => {
  mock.restore()
})

/** JWT válido para decodeJwt: header.payload.signature, payload en base64url. */
function fakeJwt(claims: Record<string, unknown>): string {
  const payload = btoa(JSON.stringify(claims)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")
  return `header.${payload}.signature`
}

function AuthProbe() {
  const { token, claims, login, register, logout } = useAuth()
  return (
    <div>
      <span data-testid="token">{token ?? "sin-token"}</span>
      <span data-testid="role">{claims?.role ?? "sin-claims"}</span>
      <button onClick={() => login("a@b.com", "pw")}>login</button>
      <button
        onClick={() =>
          register({ tenantName: "Acme", tenantSlug: "acme", adminEmail: "a@b.com", adminPassword: "pw" })
        }
      >
        register
      </button>
      <button onClick={logout}>logout</button>
    </div>
  )
}

describe("AuthProvider", () => {
  it("arranca sin token si localStorage está vacío", () => {
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    )
    expect(screen.getByTestId("token")).toHaveTextContent("sin-token")
  })

  it("arranca con el token de localStorage si ya había uno (sesión persistida)", () => {
    localStorage.setItem("access_token", fakeJwt({ role: "admin" }))
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    )
    expect(screen.getByTestId("role")).toHaveTextContent("admin")
  })

  it("login() guarda el token que devuelve la API y lo persiste en localStorage", async () => {
    const user = userEvent.setup()
    const token = fakeJwt({ role: "operator" })
    mock.onPost("/auth/login").reply(200, { access_token: token, token_type: "bearer" })

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    )
    await user.click(screen.getByText("login"))

    await waitFor(() => expect(screen.getByTestId("role")).toHaveTextContent("operator"))
    expect(localStorage.getItem("access_token")).toBe(token)
  })

  it("register() guarda el token del tenant recién creado", async () => {
    const user = userEvent.setup()
    const token = fakeJwt({ role: "admin" })
    mock.onPost("/auth/register").reply(201, { access_token: token, token_type: "bearer" })

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    )
    await user.click(screen.getByText("register"))

    await waitFor(() => expect(screen.getByTestId("token")).toHaveTextContent(token))
  })

  it("logout() limpia el token del estado y de localStorage", async () => {
    localStorage.setItem("access_token", fakeJwt({ role: "admin" }))
    const user = userEvent.setup()

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    )
    await user.click(screen.getByText("logout"))

    expect(screen.getByTestId("token")).toHaveTextContent("sin-token")
    expect(localStorage.getItem("access_token")).toBeNull()
  })

  it("useAuth() fuera de un AuthProvider tira un error explícito, no un crash silencioso", () => {
    const consoleError = console.error
    console.error = () => {} // React logea el error de boundary igual; no ensuciar la salida del test
    expect(() => render(<AuthProbe />)).toThrow("useAuth debe usarse dentro de <AuthProvider>")
    console.error = consoleError
  })
})

describe("RequireAuth", () => {
  function renderWithRouter(initialPath: string) {
    return render(
      <MemoryRouter initialEntries={[initialPath]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>página de login</div>} />
            <Route
              path="/assets"
              element={
                <RequireAuth>
                  <div>dashboard protegido</div>
                </RequireAuth>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    )
  }

  it("redirige a /login cuando no hay token", () => {
    renderWithRouter("/assets")
    expect(screen.getByText("página de login")).toBeInTheDocument()
  })

  it("muestra el contenido protegido cuando sí hay token", () => {
    localStorage.setItem("access_token", fakeJwt({ role: "admin" }))
    renderWithRouter("/assets")
    expect(screen.getByText("dashboard protegido")).toBeInTheDocument()
  })
})
