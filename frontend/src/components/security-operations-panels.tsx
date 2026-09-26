import { useState } from "react"
import { AlertTriangle, Check, Download, RefreshCw } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { OperationalAlert, WeeklyOperationsReport } from "@/lib/api"

function dateLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

const severityStyles: Record<OperationalAlert["severity"], string> = {
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  high: "border-orange-200 bg-orange-50 text-orange-900",
  critical: "border-rose-200 bg-rose-50 text-rose-900",
}

type AlertsPanelProps = {
  alerts: OperationalAlert[];
  loading: boolean;
  evaluating: boolean;
  canEvaluate: boolean;
  canManage: boolean;
  error: string;
  notice: string;
  onEvaluate: () => void;
  onAction: (alertId: string, action: "acknowledge" | "resolve") => void;
};

export function OperationalAlertsPanel({
  alerts,
  loading,
  evaluating,
  canEvaluate,
  canManage,
  error,
  notice,
  onEvaluate,
  onAction,
}: AlertsPanelProps) {
  const [view, setView] = useState<"active" | "resolved">("active")
  const activeAlerts = alerts.filter((alert) => alert.status !== "resolved")
  const resolvedAlerts = alerts.filter((alert) => alert.status === "resolved")
  const visibleAlerts = view === "active" ? activeAlerts : resolvedAlerts

  return (
    <Card className="border-border/80 shadow-sm">
      <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">Operational alerts</CardTitle>
            <Badge variant="secondary">{activeAlerts.length} active</Badge>
          </div>
          <CardDescription className="mt-1 max-w-2xl">
            Rule-based in-app alerts for repeated failures, high-risk agent blocks, and overdue approvals.
          </CardDescription>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border bg-background p-1" aria-label="Alert status filter">
            <Button type="button" size="sm" variant={view === "active" ? "secondary" : "ghost"} className="h-8 px-3 text-xs" aria-pressed={view === "active"} onClick={() => setView("active")}>
              Active ({activeAlerts.length})
            </Button>
            <Button type="button" size="sm" variant={view === "resolved" ? "secondary" : "ghost"} className="h-8 px-3 text-xs" aria-pressed={view === "resolved"} onClick={() => setView("resolved")}>
              Resolved ({resolvedAlerts.length})
            </Button>
          </div>
          {canEvaluate && <Button type="button" size="sm" variant="outline" onClick={onEvaluate} disabled={evaluating || loading}>
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${evaluating ? "animate-spin" : ""}`} />
            {evaluating ? "Checking rules…" : "Check for alerts"}
          </Button>}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">{canEvaluate ? "Checks run only when requested; this is not a background monitor or an external notification service." : "Rule checks are performed by users with alert-evaluation access; this is not a background monitor or an external notification service."}</p>
        {error && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}
        {notice && <p className="text-sm text-emerald-800" role="status">{notice}</p>}
        {loading ? (
          <p className="py-5 text-center text-sm text-muted-foreground" role="status">Loading alert register…</p>
        ) : visibleAlerts.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-muted/20 px-4 py-7 text-center">
            {view === "active" ? <Check className="mx-auto mb-2 h-5 w-5 text-emerald-700" aria-hidden="true" /> : <p className="text-xs text-muted-foreground">Alert history is empty.</p>}
            <p className="text-sm font-medium text-foreground">{view === "active" ? "No active alerts in this access scope" : "No resolved alerts to show"}</p>
            {view === "active" && <p className="mt-1 text-xs text-muted-foreground">Run a rule check to evaluate recent events and pending approvals.</p>}
          </div>
        ) : (
          <ul className="space-y-2" aria-label={`${view} operational alerts`}>
            {visibleAlerts.map((alert) => (
              <li key={alert.id} className="rounded-xl border border-border bg-background p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge className={severityStyles[alert.severity]}>{alert.severity}</Badge>
                  <Badge variant="outline">{alert.status}</Badge>
                  {alert.escalation_level > 0 && <Badge variant="destructive">Escalation {alert.escalation_level}</Badge>}
                  <span className="ml-auto text-xs text-muted-foreground">First seen {dateLabel(alert.first_seen_at)}</span>
                </div>
                <h3 className="mt-2 text-sm font-semibold text-foreground">{alert.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{alert.summary}</p>
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border/70 pt-3">
                  <span className="text-xs text-muted-foreground">
                    Rule <code className="rounded bg-muted px-1 py-0.5">{alert.rule_code}</code>
                    {alert.rule_code === "security.repeated_failures" && ` · ${alert.observed_count} events in the current rule window`}
                    {alert.last_seen_at !== alert.first_seen_at && ` · Last observed ${dateLabel(alert.last_seen_at)}`}
                  </span>
                  {canManage && alert.status !== "resolved" && <div className="flex gap-2">
                    {alert.status === "open" && <Button type="button" size="sm" variant="outline" aria-label={`Acknowledge alert: ${alert.title}`} onClick={() => onAction(alert.id, "acknowledge")}>Acknowledge</Button>}
                    <Button type="button" size="sm" variant="secondary" aria-label={`Resolve alert: ${alert.title}`} onClick={() => onAction(alert.id, "resolve")}>Resolve</Button>
                  </div>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

type WeeklyReportPanelProps = {
  report: WeeklyOperationsReport | null;
  loading: boolean;
  error: string;
};

const reportMetrics: Array<[string, keyof WeeklyOperationsReport["metrics"]]> = [
  ["Projects created", "projects_created_in_period"],
  ["Active projects now", "active_projects_at_generation"],
  ["Workflows created", "workflows_created_in_period"],
  ["Workflow actions created", "workflow_actions_created_in_period"],
  ["Workflow actions executed", "workflow_actions_executed_in_period"],
  ["Pending workflow actions now", "workflow_actions_pending_now"],
  ["Approvals requested", "approvals_requested_in_period"],
  ["Approvals decided", "approvals_decided_in_period"],
  ["Approvals pending now", "approvals_pending_now"],
  ["Approvals overdue now", "approvals_overdue_now"],
  ["Security events", "security_events_in_period"],
  ["Successful security events", "security_successes_in_period"],
  ["Failed security events", "security_failures_in_period"],
  ["Denied security events", "security_denials_in_period"],
  ["High-risk agent blocks", "high_risk_agent_blocks_in_period"],
  ["Handoffs started", "handoffs_started_in_period"],
  ["Handoffs completed", "handoffs_completed_in_period"],
  ["Handoffs failed", "handoffs_failed_in_period"],
  ["Handoffs blocked", "handoffs_blocked_in_period"],
  ["Alerts opened", "alerts_opened_in_period"],
  ["Open alerts now", "alerts_open_now"],
  ["Acknowledged alerts now", "alerts_acknowledged_now"],
  ["Escalated alerts now", "alerts_escalated_open_now"],
]

function formatMetric(value: number | Record<string, number> | null) {
  if (value === null) return "—"
  if (typeof value === "object") {
    return Object.entries(value).map(([state, count]) => `${state.replaceAll("_", " ")}: ${count}`).join(" · ")
  }
  return value
}

export function WeeklyOperationsReportPanel({ report, loading, error }: WeeklyReportPanelProps) {
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState("")

  const downloadCsv = async () => {
    setDownloading(true)
    setDownloadError("")
    try {
      const response = await fetch("/operations/weekly-report?format=csv", { credentials: "same-origin" })
      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        throw new Error(payload?.detail || `Report download failed (${response.status}).`)
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `weekly-operations-${report?.period_start ?? "report"}.csv`
      document.body.append(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    } catch (cause) {
      setDownloadError(cause instanceof Error ? cause.message : "Report download failed.")
    } finally {
      setDownloading(false)
    }
  }

  return (
    <Card className="border-border/80 shadow-sm">
      <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="text-base">Weekly operations report</CardTitle>
            {report && <Badge variant="secondary" className="capitalize">{report.scope}</Badge>}
          </div>
          <CardDescription className="mt-1">
            {report ? `${report.period_start} – ${report.period_end} · Monday–Sunday, UTC` : "Previous complete Monday–Sunday week, UTC"}
          </CardDescription>
        </div>
        <Button type="button" size="sm" variant="outline" onClick={() => void downloadCsv()} disabled={!report || downloading || loading}>
          <Download className="mr-1.5 h-3.5 w-3.5" />{downloading ? "Preparing…" : "Download CSV"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}
        {downloadError && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertDescription>{downloadError}</AlertDescription></Alert>}
        {loading && !report ? (
          <p className="py-5 text-center text-sm text-muted-foreground" role="status">Generating report from stored records…</p>
        ) : report ? (
          <>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {reportMetrics.slice(0, 4).map(([label, key]) => (
                <div key={key} className="rounded-xl border border-border bg-muted/20 p-3">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="mt-1 text-xl font-semibold tabular-nums text-foreground">{formatMetric(report.metrics[key] ?? null)}</p>
                </div>
              ))}
            </div>
            <details className="group">
              <summary className="cursor-pointer text-sm font-medium text-foreground">Show all report measures</summary>
              <dl className="mt-3 grid gap-x-6 gap-y-2 rounded-xl border border-border bg-background p-4 sm:grid-cols-2">
                {reportMetrics.map(([label, key]) => (
                  <div key={key} className="flex items-baseline justify-between gap-3 border-b border-border/60 py-1.5 last:border-0">
                    <dt className="text-sm text-muted-foreground">{label}</dt>
                    <dd className="text-sm font-semibold tabular-nums text-foreground">{formatMetric(report.metrics[key] ?? null)}</dd>
                  </div>
                ))}
                <div className="flex items-baseline justify-between gap-3 border-b border-border/60 py-1.5">
                  <dt className="text-sm text-muted-foreground">Workflow states now</dt>
                  <dd className="text-right text-xs font-medium text-foreground">
                    {Object.entries(report.metrics.workflows_by_state_now).map(([state, count]) => `${state.replaceAll("_", " ")}: ${count}`).join(" · ")}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 border-b border-border/60 py-1.5">
                  <dt className="text-sm text-muted-foreground">Workflow action states now</dt>
                  <dd className="text-right text-xs font-medium text-foreground">
                    {Object.entries(report.metrics.workflow_actions_by_status_now).map(([state, count]) => `${state.replaceAll("_", " ")}: ${count}`).join(" · ")}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 border-b border-border/60 py-1.5">
                  <dt className="text-sm text-muted-foreground">Mean handoff completion time</dt>
                  <dd className="text-sm font-semibold tabular-nums text-foreground">
                    {report.metrics.mean_handoff_completion_seconds == null ? "No completed handoffs" : `${Math.round(report.metrics.mean_handoff_completion_seconds)} sec`}
                  </dd>
                </div>
              </dl>
            </details>
            <p className="rounded-lg bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground">{report.note}</p>
            <p className="text-[0.7rem] text-muted-foreground">Generated {dateLabel(report.generated_at)}. This is a record-derived report; it does not estimate hours or generate an AI narrative.</p>
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}
