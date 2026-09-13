import { Navigate, Route, Routes } from "react-router-dom"
import { RequireAuth } from "./lib/auth"
import { AssetDetailPage } from "./pages/AssetDetailPage"
import { AssetListPage } from "./pages/AssetListPage"
import { LoginPage } from "./pages/LoginPage"
import { RegisterPage } from "./pages/RegisterPage"

export default function App() {
  return (
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
  )
}
