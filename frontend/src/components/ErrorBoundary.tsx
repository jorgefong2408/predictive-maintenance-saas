import { Component, type ErrorInfo, type ReactNode } from "react"

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/** Red de seguridad de último recurso: sin esto, un error de render en
 * cualquier página deja al usuario viendo una pantalla en blanco sin
 * ninguna pista de qué pasó (los error boundaries de React no tienen
 * equivalente en hooks, de ahí el class component). */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Error no capturado en la UI:", error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
          <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm">
            <h1 className="mb-2 text-lg font-bold text-slate-900">Algo salió mal</h1>
            <p className="mb-6 text-sm text-slate-500">
              Ocurrió un error inesperado en la aplicación. Recargar la página suele resolverlo.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="w-full rounded-md bg-slate-900 py-2 text-sm font-semibold text-white hover:bg-slate-800"
            >
              Recargar
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
