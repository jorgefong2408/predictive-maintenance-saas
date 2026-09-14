import MockAdapter from "axios-mock-adapter"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { api } from "./api"

// Bug real encontrado probando el dashboard a mano (Semana 6): un token
// vencido dejaba la UI mostrando listas vacías en silencio, sin pedir login
// de nuevo. El fix (interceptor de 401 -> logout) solo se verificó ahí
// mismo, a mano, corrompiendo el token en la consola del navegador — esto
// lo deja protegido contra una regresión futura.

let mock: MockAdapter

beforeEach(() => {
  mock = new MockAdapter(api)
  localStorage.clear()
})

afterEach(() => {
  mock.restore()
  vi.unstubAllGlobals()
})

function stubLocation(pathname: string) {
  const location = { pathname, href: `http://localhost${pathname}` }
  vi.stubGlobal("location", location)
  return location
}

describe("api client — request interceptor", () => {
  it("agrega el header Authorization cuando hay un token en localStorage", async () => {
    localStorage.setItem("access_token", "el-token")
    mock.onGet("/assets").reply((config) => {
      expect(config.headers?.Authorization).toBe("Bearer el-token")
      return [200, []]
    })

    await api.get("/assets")
  })

  it("no agrega el header cuando no hay token", async () => {
    mock.onGet("/assets").reply((config) => {
      expect(config.headers?.Authorization).toBeUndefined()
      return [200, []]
    })

    await api.get("/assets")
  })
})

describe("api client — interceptor de 401", () => {
  it("limpia el token y redirige a /login cuando una petición autenticada recibe 401", async () => {
    localStorage.setItem("access_token", "token-vencido")
    const location = stubLocation("/assets")
    mock.onGet("/assets").reply(401)

    await expect(api.get("/assets")).rejects.toBeTruthy()

    expect(localStorage.getItem("access_token")).toBeNull()
    expect(location.href).toBe("/login")
  })

  it("NO redirige si el 401 viene de una petición sin token (ej. login con contraseña incorrecta)", async () => {
    const location = stubLocation("/login")
    mock.onPost("/auth/login").reply(401)

    await expect(api.post("/auth/login", {})).rejects.toBeTruthy()

    // seguía en /login (no forzó una redirección adicional)
    expect(location.href).toBe("http://localhost/login")
  })

  it("no redirige de nuevo si ya está en /login", async () => {
    localStorage.setItem("access_token", "token-vencido")
    const location = stubLocation("/login")
    mock.onGet("/assets").reply(401)

    await expect(api.get("/assets")).rejects.toBeTruthy()

    expect(location.href).toBe("http://localhost/login") // no se tocó
  })

  it("no toca nada ante otros códigos de error (ej. 404, 500)", async () => {
    localStorage.setItem("access_token", "un-token")
    const location = stubLocation("/assets")
    mock.onGet("/assets/no-existe").reply(404)

    await expect(api.get("/assets/no-existe")).rejects.toBeTruthy()

    expect(localStorage.getItem("access_token")).toBe("un-token")
    expect(location.href).toBe("http://localhost/assets")
  })
})
