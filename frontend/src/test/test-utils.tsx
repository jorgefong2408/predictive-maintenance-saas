import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render } from "@testing-library/react"
import type { ReactElement } from "react"
import { MemoryRouter } from "react-router-dom"
import { AuthProvider } from "../lib/auth"

/** QueryClient nuevo por render: evita que la caché de React Query de un
 * test se filtre al siguiente (mismos query keys en varias páginas). */
export function renderWithProviders(ui: ReactElement, { initialPath = "/" } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** JWT con forma válida para decodeJwt (lib/auth.tsx) — no necesita firma
 * real, el frontend nunca la valida (eso lo hace el backend). */
export function fakeJwt(claims: Record<string, unknown>): string {
  const payload = btoa(JSON.stringify(claims)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")
  return `header.${payload}.signature`
}
