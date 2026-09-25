import { useMemo } from "react"

import type { SecurityDashboard } from "@/lib/api"
import { formatDate } from "@/components/security-dashboard-utils"

export function ActivityBars({ dashboard }: { dashboard: SecurityDashboard }) {
  const chart = useMemo(() => {
    const bucketCount = Math.min(14, dashboard.window_days)
    const start = new Date(dashboard.period_start).getTime()
    const end = new Date(dashboard.generated_at).getTime()
    const bucketWidth = (end - start) / bucketCount
    const buckets = Array.from({ length: bucketCount }, (_, index) => {
      const bucketStart = new Date(start + bucketWidth * index)
      const bucketEnd = new Date(Math.min(end, start + bucketWidth * (index + 1)))
      return {
        label: `${index + 1}`,
        total: 0,
        success: 0,
        failure: 0,
        denied: 0,
        dateRange: `${formatDate(bucketStart.toISOString())} – ${formatDate(bucketEnd.toISOString())}`,
        shortLabel: formatDate(bucketStart.toISOString()).split(" ").slice(0, 2).join(" "),
      }
    })
    for (const day of dashboard.activity_by_day) {
      const date = new Date(`${day.date}T12:00:00Z`)
      const index = Math.max(0, Math.min(bucketCount - 1, Math.floor((date.getTime() - start) / bucketWidth)))
      const bucket = buckets[index]
      bucket.total += day.total
      bucket.success += day.success
      bucket.failure += day.failure
      bucket.denied += day.denied
    }
    return buckets
  }, [dashboard])

  const max = Math.max(1, ...chart.map((bucket) => bucket.total))
  return (
    <div className="grid h-40 grid-cols-7 items-end gap-2 sm:grid-cols-[repeat(14,minmax(0,1fr))]" role="img" aria-label={`Security event volume across the last ${dashboard.window_days} days`}>
      {chart.map((bucket, index) => (
        <div key={`${bucket.label}-${index}`} className="flex h-full min-w-0 flex-col items-center justify-end gap-1.5" title={`${bucket.dateRange}: ${bucket.total} events`}>
          <span className="text-[0.62rem] tabular-nums text-muted-foreground">{bucket.total || ""}</span>
          <div className="flex h-28 w-full max-w-8 items-end overflow-hidden rounded-t-md bg-slate-100" aria-hidden="true">
            <div className="flex w-full flex-col justify-end" style={{ height: `${Math.max(bucket.total ? 4 : 0, (bucket.total / max) * 100)}%` }}>
              {bucket.denied > 0 && <span className="block w-full bg-rose-500" style={{ height: `${(bucket.denied / bucket.total) * 100}%` }} />}
              {bucket.failure > 0 && <span className="block w-full bg-amber-500" style={{ height: `${(bucket.failure / bucket.total) * 100}%` }} />}
              {bucket.success > 0 && <span className="block w-full bg-teal-600" style={{ height: `${(bucket.success / bucket.total) * 100}%` }} />}
            </div>
          </div>
          {(index === 0 || index === chart.length - 1 || index === Math.floor(chart.length / 2)) && (
            <span className="max-w-full truncate text-[0.58rem] text-muted-foreground">{bucket.shortLabel}</span>
          )}
        </div>
      ))}
    </div>
  )
}

export function LegendDot({ color, label }: { color: string; label: string }) {
  return <span className="inline-flex items-center gap-1.5"><i className={`h-2 w-2 rounded-full ${color}`} aria-hidden="true" />{label}</span>
}
