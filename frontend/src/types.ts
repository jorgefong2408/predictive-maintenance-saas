export type AssetStatus = "ok" | "warning" | "critical"

export interface Asset {
  id: string
  name: string
  asset_type: string
  external_ref: string | null
  status: AssetStatus
  metadata: Record<string, unknown>
  created_at: string
}

export interface SensorReading {
  time: string
  asset_id: string
  sensor_name: string
  value: number
  unit: string | null
}

export type PredictionType = "rul_days" | "anomaly_score" | "failure_probability"

export interface Prediction {
  id: string
  asset_id: string
  predicted_at: string
  model_name: string
  model_version: string
  prediction_type: PredictionType
  value: number
  metadata: Record<string, unknown>
}

export type AlertSeverity = "info" | "warning" | "critical"

export interface Alert {
  id: string
  asset_id: string
  triggered_at: string
  severity: AlertSeverity
  alert_type: string
  message: string
  acknowledged_at: string | null
  resolved_at: string | null
}
