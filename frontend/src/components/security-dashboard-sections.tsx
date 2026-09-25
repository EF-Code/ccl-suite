import { ActivityBars, LegendDot } from "@/components/security-dashboard-activity"
import { SecurityEventRow } from "@/components/security-dashboard-event-row"
import { SnapshotValue } from "@/components/security-dashboard-metrics"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { SecurityDashboard } from "@/lib/api"
import { formatDate, formatNumber } from "@/components/security-dashboard-utils"

export function SecurityActivityPanel({ dashboard, loading }: { dashboard: SecurityDashboard; loading: boolean }) {
  return (
    <Card className="overflow-hidden rounded-2xl border-[#e0e7ec] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.03),0_12px_32px_rgba(16,24,40,0.045)]">
      <CardHeader className="pb-2">
        <CardTitle className="text-base text-[#172f49]">Security activity</CardTitle>
        <CardDescription>Event volume over time; longer windows are grouped into intervals.</CardDescription>
      </CardHeader>
      <CardContent>
        <ActivityBars dashboard={dashboard} />
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 border-t pt-3 text-xs text-muted-foreground">
          <LegendDot color="bg-teal-600" label={`Succeeded · ${formatNumber(dashboard.event_counts.success)}`} />
          <LegendDot color="bg-amber-500" label={`Failed · ${formatNumber(dashboard.event_counts.failure)}`} />
          <LegendDot color="bg-rose-500" label={`Denied · ${formatNumber(dashboard.event_counts.denied)}`} />
          {loading && <span role="status">Updating…</span>}
          <span className="ml-auto">Generated {formatDate(dashboard.generated_at, true)}</span>
        </div>
      </CardContent>
    </Card>
  )
}

export function ProjectControlsPanel({ dashboard, windowDays }: { dashboard: SecurityDashboard; windowDays: number }) {
  const metrics = dashboard.project_metrics
  return (
    <Card className="overflow-hidden rounded-2xl border-[#e0e7ec] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.03),0_12px_32px_rgba(16,24,40,0.045)]">
      <CardHeader className="pb-2">
        <CardTitle className="text-base text-[#172f49]">Project controls</CardTitle>
        <CardDescription>Current snapshot for {dashboard.scope === "organization" ? "all projects" : "projects you own"}.</CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3">
        <SnapshotValue label="Projects" value={metrics.projects_total} detail={`${formatNumber(metrics.projects_active)} active`} />
        <SnapshotValue label="Workflows" value={metrics.workflows_total} detail={`${formatNumber(metrics.workflows_open)} in progress`} />
        <SnapshotValue label="Pending approvals" value={metrics.pending_approvals} detail="Awaiting a decision" />
        <SnapshotValue label="Agent handoffs" value={metrics.agent_handoffs} detail={`In the last ${windowDays} days`} />
      </CardContent>
    </Card>
  )
}

export function RecentEventsPanel({ dashboard }: { dashboard: SecurityDashboard }) {
  return (
    <Card className="overflow-hidden rounded-2xl border-[#e0e7ec] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.03),0_12px_32px_rgba(16,24,40,0.045)]">
      <CardHeader className="pb-2">
        <CardTitle className="text-base text-[#172f49]">Recent security events</CardTitle>
        <CardDescription>Latest 25 events in this view. Aggregate totals cover the complete selected period.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader><TableRow><TableHead>Event</TableHead><TableHead>Outcome</TableHead><TableHead>When</TableHead></TableRow></TableHeader>
            <TableBody>
              {dashboard.recent_events.length === 0
                ? <TableRow><TableCell colSpan={3} className="h-28 text-center text-sm text-muted-foreground">No security events in this period.</TableCell></TableRow>
                : dashboard.recent_events.map((event) => <SecurityEventRow key={event.id} event={event} />)}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}

export function EventCodesPanel({ dashboard }: { dashboard: SecurityDashboard }) {
  return (
    <Card className="overflow-hidden rounded-2xl border-[#e0e7ec] bg-white shadow-[0_1px_2px_rgba(16,24,40,0.03),0_12px_32px_rgba(16,24,40,0.045)]">
      <CardHeader className="pb-2">
        <CardTitle className="text-base text-[#172f49]">Most common event types</CardTitle>
        <CardDescription>Up to 20 event codes, ordered by frequency.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {dashboard.event_codes.length === 0
          ? <p className="py-8 text-center text-sm text-muted-foreground">No event types to report.</p>
          : dashboard.event_codes.map((item) => {
            const share = dashboard.event_counts.total ? (item.count / dashboard.event_counts.total) * 100 : 0
            return <div key={item.event_code} className="grid gap-1.5">
              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="truncate font-medium text-foreground" title={item.event_code}>{item.event_code.replaceAll(".", " · ")}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground">{formatNumber(item.count)}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-100" aria-hidden="true"><span className="block h-full rounded-full bg-[#138b88]" style={{ width: `${share}%` }} /></div>
            </div>
          })}
      </CardContent>
    </Card>
  )
}
