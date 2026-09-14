import { render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ErrorBoundary } from "./ErrorBoundary"

function Bomb(): never {
  throw new Error("boom")
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // React (y jsdom) logean el error del boundary a console.error — es
    // ruido esperado en este test, no una señal de que algo falló.
    vi.spyOn(console, "error").mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("renderiza a los hijos normalmente cuando no hay error", () => {
    render(
      <ErrorBoundary>
        <p>contenido normal</p>
      </ErrorBoundary>,
    )
    expect(screen.getByText("contenido normal")).toBeInTheDocument()
  })

  it("muestra la UI de fallback cuando un hijo lanza durante el render", () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    )
    expect(screen.getByText("Algo salió mal")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Recargar" })).toBeInTheDocument()
  })
})
