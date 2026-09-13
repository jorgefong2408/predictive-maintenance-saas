import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import axios from "axios"
import { useState } from "react"
import { Link, useParams } from "react-router-dom"
import { SensorChart } from "../components/SensorChart"
import { StatusBadge } from "../components/StatusBadge"
import { Layout } from "../components/Layout"
import { api } from "../lib/api"
import type { Alert, Asset, Prediction, SensorReading } from "../types"

const SENSORS: { name: string; unit: string }[] = [
  { name: "torque", unit: "Nm" },
  { name: "tool_wear", unit: "min" },
  { name: "process_temperature", unit: "K" },
  { name: "air_temperature", unit: "K" },
  { name: "rotational_speed", unit: "rpm" },
]

function formatDateTime(iso: string): string {
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z")
  return d.toLocaleString([], { dateStyle: "short", timeStyle: "short" })
}

export function AssetDetailPage() {
  const { assetId } = useParams<{ assetId: string }>()
  const queryClient = useQueryClient()
  const [predictError, setPredictError] = useState<string | null>(null)

  const { data: asset } = useQuery({
    queryKey: ["assets", assetId],
    queryFn: async () => (await api.get<Asset>(`/assets/${assetId}`)).data,
    enabled: !!assetId,
  })

  const { data: readings = [] } = useQuery({
    queryKey: ["readings", assetId],
    queryFn: async () => (await api.get<SensorReading[]>(`/assets/${assetId}/readings`, { params: { limit: 2000 } })).data,
    enabled: !!assetId,
    refetchInterval: 15_000,
  })

  const { data: predictions = [] } = useQuery({
    queryKey: ["predictions", assetId],
    queryFn: async () => (await api.get<Prediction[]>(`/assets/${assetId}/predictions`)).data,
    enabled: !!assetId,
  })

  const { data: allAlerts = [] } = useQuery({
    queryKey: ["alerts", "all"],
    queryFn: async () => (await api.get<Alert[]>("/alerts", { params: { active_only: false } })).data,
  })
  const assetAlerts = allAlerts.filter((a) => a.asset_id === assetId)

  const predict = useMutation({
    mutationFn: async () => api.post(`/assets/${assetId}/predictions`, { prediction_type: "failure_probability" }),
    onSuccess: () => {
      setPredictError(null)
      queryClient.invalidateQueries({ queryKey: ["predictions", assetId] })
      queryClient.invalidateQueries({ queryKey: ["assets"] })
      queryClient.invalidateQueries({ queryKey: ["alerts"] })
    },
    onError: (err) => {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null
      setPredictError(typeof detail === "string" ? detail : "No se pudo calcular la predicción")
    },
  })

  const latestPrediction = predictions[0]

  return (
    <Layout>
      <Link to="/assets" className="text-sm text-slate-400 hover:text-slate-700">
        ← Activos
      </Link>

      <div className="mt-2 mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-900">{asset?.name ?? "..."}</h1>
          {asset && <StatusBadge status={asset.status} />}
        </div>
        <button
          onClick={() => predict.mutate()}
          disabled={predict.isPending}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {predict.isPending ? "Calculando..." : "Predecir riesgo de falla"}
        </button>
      </div>

      {predictError && <p className="mb-4 text-sm text-red-600">{predictError}</p>}

      {latestPrediction && (
        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase tracking-wide text-slate-400">Última predicción</p>
          <p className="text-2xl font-bold text-slate-900">{(latestPrediction.value * 100).toFixed(1)}%</p>
          <p className="text-xs text-slate-400">
            probabilidad de falla — {latestPrediction.model_name} v{latestPrediction.model_version} ·{" "}
            {formatDateTime(latestPrediction.predicted_at)}
          </p>
        </div>
      )}

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {SENSORS.map((s) => (
          <SensorChart key={s.name} sensorName={s.name} unit={s.unit} readings={readings} />
        ))}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white">
        <h2 className="border-b border-slate-100 px-4 py-2 text-sm font-semibold text-slate-700">
          Historial de alertas
        </h2>
        <ul className="divide-y divide-slate-100">
          {assetAlerts.length === 0 && <li className="px-4 py-4 text-sm text-slate-400">Sin alertas para este activo</li>}
          {assetAlerts.map((a) => (
            <li key={a.id} className="px-4 py-3 text-sm">
              <span className="font-medium text-slate-700">{formatDateTime(a.triggered_at)}</span>{" "}
              <span className="uppercase text-xs text-slate-400">{a.severity}</span>
              <p className="text-slate-600">{a.message}</p>
            </li>
          ))}
        </ul>
      </div>
    </Layout>
  )
}
