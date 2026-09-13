import { lazy, Suspense } from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import { RequireAuth } from "./lib/auth"

// Code-splitting por ruta: AssetDetailPage carga recharts (la dependencia
// más pesada del bundle) — con esto solo se descarga cuando el usuario
// realmente entra al detalle de un activo, no en la carga inicial de /login.
const LoginPage = lazy(() => import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import("./pages/RegisterPage").then((m) => ({ default: m.RegisterPage })))
const AssetListPage = lazy(() => import("./pages/AssetListPage").then((m) => ({ default: m.AssetListPage })))
const AssetDetailPage = lazy(() => import("./pages/AssetDetailPage").then((m) => ({ default: m.AssetDetailPage })))

function PageFallback() {
  return <div className="flex min-h-screen items-center justify-center text-sm text-slate-400">Cargando...</div>
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/assets"
          element={
            <RequireAuth>
              <AssetListPage />
            </RequireAuth>
          }
        />
        <Route
          path="/assets/:assetId"
          element={
            <RequireAuth>
              <AssetDetailPage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/assets" replace />} />
      </Routes>
    </Suspense>
  )
}
