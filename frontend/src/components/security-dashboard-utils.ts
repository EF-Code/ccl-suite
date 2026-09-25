import type { SecurityDashboard, SecurityEvent } from "@/lib/api"

export const SECURITY_DASHBOARD_WINDOWS = [7, 30, 90] as const

export function formatNumber(value: number): string {
  return new Intl.NumberFormat().format(value)
}

export function formatDate(value: string, includeTime = false): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Date unavailable"
  return new Intl.DateTimeFormat(undefined, includeTime
    ? { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }
    : { day: "numeric", month: "short", year: "numeric" }).format(date)
}

export function shortReference(value: string | null): string {
  if (!value) return "—"
  return value.length > 24 ? `${value.slice(0, 12)}…${value.slice(-6)}` : value
}

export function outcomeLabel(outcome: SecurityEvent["outcome"]): string {
  return outcome === "denied" ? "Denied" : outcome === "failure" ? "Failed" : "Succeeded"
}

function csvCell(value: string | number | null | undefined): string {
  const text = String(value ?? "")
  const safeText = /^[\t\r ]*[=+\-@]/.test(text) ? `'${text}` : text
  return `"${safeText.replaceAll('"', '""')}"`
}

export function downloadSecurityReport(dashboard: SecurityDashboard): void {
  const rows: Array<Array<string | number | null | undefined>> = [
    ["CCL Suite security activity report"],
    ["Scope", dashboard.scope === "organization" ? "Organization" : "Account"],
    ["Window (days)", dashboard.window_days],
    ["From", dashboard.period_start],
    ["Generated", dashboard.generated_at],
    [],
    ["Security event outcomes"],
    ["Outcome", "Count"],
    ["All events", dashboard.event_counts.total],
    ["Succeeded", dashboard.event_counts.success],
    ["Failed", dashboard.event_counts.failure],
    ["Denied", dashboard.event_counts.denied],
    [],
    ["Current project and workflow snapshot"],
    ["Metric", "Count"],
    ["Projects", dashboard.project_metrics.projects_total],
    ["Active projects", dashboard.project_metrics.projects_active],
    ["Workflows", dashboard.project_metrics.workflows_total],
    ["Open workflows", dashboard.project_metrics.workflows_open],
    ["Pending approvals", dashboard.project_metrics.pending_approvals],
    ["Agent handoffs in selected period", dashboard.project_metrics.agent_handoffs],
    ["Blocked or failed handoffs in selected period", dashboard.project_metrics.unsuccessful_agent_handoffs],
    [],
    ["Daily activity"],
    ["Date", "Total", "Succeeded", "Failed", "Denied"],
    ...dashboard.activity_by_day.map((day) => [day.date, day.total, day.success, day.failure, day.denied]),
    [],
    ["Event types (top 20)"],
    ["Event code", "Count"],
    ...dashboard.event_codes.map((item) => [item.event_code, item.count]),
    [],
    ["Recent events (up to 25; totals above cover the full period)"],
    ["Occurred at", "Event", "Outcome", "Resource type", "Resource reference", "Request reference"],
    ...dashboard.recent_events.map((event) => [
      event.occurred_at,
      event.event_code,
      event.outcome,
      event.resource_type,
      event.resource_ref,
      event.request_ref,
    ]),
  ]
  const csv = rows.map((row) => row.map(csvCell).join(",")).join("\r\n")
  const objectUrl = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" }))
  const link = document.createElement("a")
  link.href = objectUrl
  link.download = `security-report-last-${dashboard.window_days}-days.csv`
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
}
