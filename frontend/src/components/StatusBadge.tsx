import clsx from "clsx"
import type { AssetStatus } from "../types"

const STYLES: Record<AssetStatus, string> = {
  ok: "bg-emerald-100 text-emerald-700 border-emerald-300",
  warning: "bg-amber-100 text-amber-700 border-amber-300",
  critical: "bg-red-100 text-red-700 border-red-300",
}

const LABELS: Record<AssetStatus, string> = {
  ok: "OK",
  warning: "WARNING",
  critical: "CRÍTICO",
}

export function StatusBadge({ status }: { status: AssetStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        STYLES[status],
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {LABELS[status]}
    </span>
  )
}
