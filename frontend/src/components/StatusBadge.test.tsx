import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { StatusBadge } from "./StatusBadge"

describe("StatusBadge", () => {
  it.each([
    ["ok", "OK"],
    ["warning", "WARNING"],
    ["critical", "CRÍTICO"],
  ] as const)("muestra la etiqueta correcta para status=%s", (status, label) => {
    render(<StatusBadge status={status} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it("usa el color de crítico cuando el status es crítico", () => {
    render(<StatusBadge status="critical" />)
    expect(screen.getByText("CRÍTICO")).toHaveClass("text-red-700")
  })
})
