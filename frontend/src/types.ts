// Alias sobre los tipos generados desde el OpenAPI del backend (ver
// src/lib/api-schema.ts, "npm run codegen") -- una sola fuente de verdad
// (los schemas de Pydantic) en vez de mantener estas formas a mano en
// paralelo, que era como estaba antes y podía irse desalineando en
// silencio. Este archivo existe solo para no tener que tocar cada import
// `from "../types"` que ya existe en el resto del frontend.
import type { components } from "./lib/api-schema"

export type Asset = components["schemas"]["AssetOut"]
export type AssetStatus = Asset["status"]

export type SensorReading = components["schemas"]["SensorReadingOut"]

export type Prediction = components["schemas"]["PredictionOut"]
export type PredictionType = Prediction["prediction_type"]

export type Alert = components["schemas"]["AlertOut"]
export type AlertSeverity = Alert["severity"]
