import axios from "axios"

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"
export const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000"

export const api = axios.create({ baseURL: API_URL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Un 401 en una petición que SÍ llevaba token significa que expiró o quedó
// inválido (ej. el backend se reinició con otro JWT_SECRET_KEY) — sin esto,
// la UI se queda mostrando listas vacías en silencio en vez de pedir login
// de nuevo (encontrado probando el dashboard manualmente, Semana 6).
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const hadToken = Boolean(error.config?.headers?.Authorization)
    if (error.response?.status === 401 && hadToken) {
      localStorage.removeItem("access_token")
      if (window.location.pathname !== "/login") {
        window.location.href = "/login"
      }
    }
    return Promise.reject(error)
  },
)
