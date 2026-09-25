import type { ReactNode } from "react"

import { Card, CardContent } from "@/components/ui/card"
import { formatNumber } from "@/components/security-dashboard-utils"

export function MetricCard({ label, value, description, icon, tone }: { label: string; value: string; description: string; icon: ReactNode; tone: "teal" | "rose" | "amber" | "slate" }) {
  const iconClass = {
    teal: "bg-teal-50 text-teal-700",
    rose: "bg-rose-50 text-rose-700",
    amber: "bg-amber-50 text-amber-700",
    slate: "bg-slate-100 text-slate-700",
  }[tone]
  return (
    <Card className="rounded-2xl border-[#e0e7ec] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.03),0_12px_32px_rgba(16,24,40,0.045)]">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-medium text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold tracking-tight text-[#172f49]">{value}</p></div><span className={`grid h-9 w-9 place-items-center rounded-xl ${iconClass}`}>{icon}</span></div>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  )
}

export function SnapshotValue({ label, value, detail }: { label: string; value: number; detail: string }) {
  return <div className="rounded-xl border bg-slate-50/70 p-3.5">
    <p className="text-[0.68rem] font-medium text-muted-foreground">{label}</p>
    <p className="mt-1 text-xl font-semibold tabular-nums tracking-tight text-[#172f49]">{formatNumber(value)}</p>
    <p className="mt-0.5 text-[0.65rem] text-muted-foreground">{detail}</p>
  </div>
}
