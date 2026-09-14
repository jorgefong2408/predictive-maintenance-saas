import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState, type FormEvent } from "react"
import { Link } from "react-router-dom"
import { Layout } from "../components/Layout"
import { StatusBadge } from "../components/StatusBadge"
import { api } from "../lib/api"
import type { Asset } from "../types"

const STATUS_ORDER: Record<Asset["status"], number> = { critical: 0, warning: 1, ok: 2 }

export function AssetListPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState("")
  const [assetType, setAssetType] = useState("cnc_milling_machine")

  const { data: assets = [], isLoading } = useQuery({
    queryKey: ["assets"],
    queryFn: async () => (await api.get<Asset[]>("/assets")).data,
  })

  const createAsset = useMutation({
    mutationFn: async () => api.post("/assets", { name, asset_type: assetType, metadata: {} }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] })
      setShowForm(false)
      setName("")
    },
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (name.trim()) createAsset.mutate()
  }

  const sorted = [...assets].sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status])

  return (
    <Layout>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-900">Activos</h1>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
        >
          + Nuevo activo
        </button>
      </div>

      {showForm && (
        <form onSubmit={onSubmit} className="mb-4 flex items-end gap-2 rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex-1">
            <label htmlFor="new-asset-name" className="mb-1 block text-xs font-medium text-slate-600">
              Nombre
            </label>
            <input
              id="new-asset-name"
              autoFocus
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Mill-07"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div className="flex-1">
            <label htmlFor="new-asset-type" className="mb-1 block text-xs font-medium text-slate-600">
              Tipo
            </label>
            <input
              id="new-asset-type"
              value={assetType}
              onChange={(e) => setAssetType(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={createAsset.isPending}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Crear
          </button>
        </form>
      )}

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        {isLoading && <p className="p-6 text-sm text-slate-400">Cargando...</p>}
        {!isLoading && sorted.length === 0 && (
          <p className="p-6 text-center text-sm text-slate-400">Sin activos todavía — crea el primero.</p>
        )}
        <ul className="divide-y divide-slate-100">
          {sorted.map((asset) => (
            <li key={asset.id}>
              <Link
                to={`/assets/${asset.id}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-slate-50"
              >
                <div className="flex items-center gap-3">
                  <StatusBadge status={asset.status} />
                  <span className="font-medium text-slate-800">{asset.name}</span>
                  <span className="text-xs text-slate-400">{asset.asset_type}</span>
                </div>
                <span className="text-slate-300">→</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </Layout>
  )
}
