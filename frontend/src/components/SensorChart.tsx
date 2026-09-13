import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import type { SensorReading } from "../types"

function formatTime(iso: string): string {
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z")
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

export function SensorChart({
  sensorName,
  unit,
  readings,
}: {
  sensorName: string
  unit: string | null
  readings: SensorReading[]
}) {
  const data = readings
    .filter((r) => r.sensor_name === sensorName)
    .sort((a, b) => a.time.localeCompare(b.time))
    .map((r) => ({ time: formatTime(r.time), value: r.value }))

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-medium text-slate-600">
        {sensorName} {unit && <span className="text-slate-400">({unit})</span>}
      </h3>
      {data.length === 0 ? (
        <p className="py-8 text-center text-xs text-slate-400">Sin lecturas todavía</p>
      ) : (
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} stroke="#94a3b8" />
            <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" domain={["auto", "auto"]} />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#0f172a" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
