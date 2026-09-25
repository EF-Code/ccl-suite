import { Badge } from "@/components/ui/badge"
import { TableCell, TableRow } from "@/components/ui/table"
import type { SecurityEvent } from "@/lib/api"
import { formatDate, outcomeLabel, shortReference } from "@/components/security-dashboard-utils"

export function SecurityEventRow({ event }: { event: SecurityEvent }) {
  const tone = event.outcome === "success" ? "border-teal-200 bg-teal-50 text-teal-800" : event.outcome === "denied" ? "border-rose-200 bg-rose-50 text-rose-800" : "border-amber-200 bg-amber-50 text-amber-800"
  return (
    <TableRow>
      <TableCell>
        <span className="block max-w-[15rem] truncate font-medium text-foreground" title={event.event_code}>{event.event_code.replaceAll(".", " · ")}</span>
        <span className="mt-0.5 block text-xs text-muted-foreground">{event.resource_type || "System event"} · {shortReference(event.resource_ref)}</span>
      </TableCell>
      <TableCell><Badge variant="outline" className={tone}>{outcomeLabel(event.outcome)}</Badge></TableCell>
      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(event.occurred_at, true)}</TableCell>
    </TableRow>
  )
}
