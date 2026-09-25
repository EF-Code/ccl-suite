import { useEffect, useState } from "react"
import { AlertCircle, Download, RefreshCw, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { MetricCard } from "@/components/security-dashboard-metrics"
import { EventCodesPanel, ProjectControlsPanel, RecentEventsPanel, SecurityActivityPanel } from "@/components/security-dashboard-sections"
import { downloadSecurityReport, formatDate, formatNumber, SECURITY_DASHBOARD_WINDOWS } from "@/components/security-dashboard-utils"
import { apiRequest, type SecurityDashboard } from "@/lib/api"

export function SecurityDashboard() {
  const [windowDays, setWindowDays] = useState<7 | 30 | 90>(7)
  const [refreshSequence, setRefreshSequence] = useState(0)
  const [dashboard, setDashboard] = useState<SecurityDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    let active = true
    void apiRequest<SecurityDashboard>(`/security-dashboard?window_days=${windowDays}`)
      .then((result) => {
        if (active) {
          setDashboard(result)
          setError("")
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setError((cause as Error).message || "The security overview could not be loaded.")
          setDashboard(null)
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [windowDays, refreshSequence])

  const refresh = () => {
    setLoading(true)
    setError("")
    setRefreshSequence((value) => value + 1)
  }

  if (loading && !dashboard) {
    return <div className="mx-auto grid min-h-64 max-w-[1280px] place-items-center text-sm text-muted-foreground" role="status">Loading security activity…</div>
  }

  if (error && !dashboard) {
    return (
      <div className="mx-auto max-w-[1280px] space-y-4">
        <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>
        <Button variant="outline" onClick={refresh}><RefreshCw className="mr-2 h-4 w-4" />Try again</Button>
      </div>
    )
  }

  if (!dashboard) return null

  const metrics = dashboard.project_metrics
  const scopeLabel = dashboard.scope === "organization" ? "Organization-wide" : "Your account"
  return (
    <section className="mx-auto max-w-[1280px] space-y-5" aria-labelledby="security-dashboard-title">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="security-dashboard-title" className="text-xl font-semibold tracking-tight text-[#172f49]">Security overview</h2>
            <Badge variant="secondary" className="capitalize">{scopeLabel}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Audit activity and review project controls. Metrics use only records visible to your role.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border bg-white p-1" aria-label="Report period">
            {SECURITY_DASHBOARD_WINDOWS.map((days) => (
              <Button key={days} type="button" size="sm" variant={windowDays === days ? "secondary" : "ghost"} className="h-8 px-3 text-xs" aria-pressed={windowDays === days} onClick={() => { if (windowDays !== days) { setLoading(true); setError(""); setWindowDays(days) } }}>
                {days} days
              </Button>
            ))}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={refresh} disabled={loading} aria-label="Refresh security overview">
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />Refresh
          </Button>
          <Button type="button" size="sm" onClick={() => downloadSecurityReport(dashboard)}>
            <Download className="mr-1.5 h-3.5 w-3.5" />Download report
          </Button>
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error} Showing the last successfully loaded results.</AlertDescription></Alert>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-live="polite">
        <MetricCard label="Security events" value={formatNumber(dashboard.event_counts.total)} description={`Across the selected ${windowDays}-day period`} icon={<ShieldCheck className="h-4 w-4" />} tone="teal" />
        <MetricCard label="Denied activity" value={formatNumber(dashboard.event_counts.denied)} description={`${formatNumber(dashboard.event_counts.failure)} failed events also recorded`} icon={<ShieldX className="h-4 w-4" />} tone="rose" />
        <MetricCard label="Open approvals" value={formatNumber(metrics.pending_approvals)} description={`${formatNumber(metrics.workflows_open)} workflows currently in progress`} icon={<ShieldAlert className="h-4 w-4" />} tone="amber" />
        <MetricCard label="Unsuccessful agent handoffs" value={formatNumber(metrics.unsuccessful_agent_handoffs)} description={`${formatNumber(metrics.agent_handoffs)} handoffs in the selected period`} icon={<AlertCircle className="h-4 w-4" />} tone="slate" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(18rem,0.8fr)]">
        <SecurityActivityPanel dashboard={dashboard} loading={loading} />
        <ProjectControlsPanel dashboard={dashboard} windowDays={windowDays} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(17rem,0.65fr)]">
        <RecentEventsPanel dashboard={dashboard} />
        <EventCodesPanel dashboard={dashboard} />
      </div>

      <p className="sr-only" aria-live="polite">Report generated {formatDate(dashboard.generated_at)}.</p>
    </section>
  )
}
