import { useMemo, useState } from "react"
import { ArrowUpRight, CalendarDays, CircleAlert, ClipboardCheck, ListTodo, Search } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { MyWorkItem, WorkItemStatus, WorkItemUpdate } from "@/lib/api"

type MyWorkProps = {
  items: MyWorkItem[];
  total: number;
  loading: boolean;
  error: string;
  canManage: boolean;
  onRefresh: () => void;
  onLoadMore: () => void;
  onUpdate: (projectId: string, itemId: string, changes: WorkItemUpdate) => Promise<void>;
  onOpenProject: (projectId: string) => void;
};

type WorkFilter = "open" | "all" | WorkItemStatus;
type WorkGroup = "Overdue" | "Due today" | "Upcoming" | "No due date" | "Completed" | "Cancelled";

const statusLabels: Record<WorkItemStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  blocked: "Blocked",
  done: "Done",
  cancelled: "Cancelled",
};

const statuses: WorkItemStatus[] = ["todo", "in_progress", "blocked", "done", "cancelled"];
const statusTransitions: Record<WorkItemStatus, WorkItemStatus[]> = {
  todo: ["todo", "in_progress", "blocked", "done", "cancelled"],
  in_progress: ["in_progress", "todo", "blocked", "done", "cancelled"],
  blocked: ["blocked", "todo", "in_progress", "done", "cancelled"],
  done: ["done", "in_progress"],
  cancelled: ["cancelled", "todo"],
};

function localDateKey(date = new Date()): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`
}

function formatDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number)
  const date = new Date(year, month - 1, day)
  return Number.isNaN(date.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(date)
}

function groupFor(item: MyWorkItem, today: string): WorkGroup {
  if (item.status === "cancelled") return "Cancelled"
  if (item.status === "done") return "Completed"
  if (!item.due_date) return "No due date"
  if (item.due_date < today) return "Overdue"
  if (item.due_date === today) return "Due today"
  return "Upcoming"
}

const groupOrder: WorkGroup[] = ["Overdue", "Due today", "Upcoming", "No due date", "Completed", "Cancelled"]

export function MyWork({ items, total, loading, error, canManage, onRefresh, onLoadMore, onUpdate, onOpenProject }: MyWorkProps) {
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState<WorkFilter>("open")
  const today = localDateKey()
  const visibleItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return items.filter((item) => {
      const matchesStatus = filter === "all"
        || (filter === "open" ? !["done", "cancelled"].includes(item.status) : item.status === filter)
      const matchesText = !normalizedQuery || [item.title, item.description, item.project_title, item.assignee || ""].some((value) => value.toLowerCase().includes(normalizedQuery))
      return matchesStatus && matchesText
    })
  }, [filter, items, query])

  const groups = groupOrder
    .map((title) => ({ title, items: visibleItems.filter((item) => groupFor(item, today) === title) }))
    .filter((group) => group.items.length > 0)

  return (
    <section className="space-y-5" aria-labelledby="my-work-title">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-teal-800">Your workload</p>
          <h2 id="my-work-title" className="text-2xl font-semibold tracking-tight text-[#1b2c3b]">My Work</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">One clear list of work assigned to you across your projects.</p>
        </div>
        <Button type="button" variant="outline" onClick={onRefresh} disabled={loading}>
          <ListTodo className={`h-4 w-4 ${loading ? "animate-pulse" : ""}`} />Refresh
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem]">
        <label className="relative block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} className="pl-9" placeholder="Search tasks, projects, or details…" aria-label="Search your work" />
        </label>
        <Select value={filter} onValueChange={(value) => setFilter(value as WorkFilter)}>
          <SelectTrigger aria-label="Filter your work"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="open">Open work</SelectItem>
            <SelectItem value="all">All statuses</SelectItem>
            {statuses.map((status) => <SelectItem key={status} value={status}>{statusLabels[status]}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"><span>{error}</span><Button type="button" variant="outline" size="sm" onClick={onRefresh}>Try again</Button></div>}
      {loading && items.length === 0 && <p role="status" className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">Loading your assigned work…</p>}
      {items.length > 0 && <p className="text-xs text-muted-foreground">{visibleItems.length} shown · {items.length} loaded of {total} assigned task{total === 1 ? "" : "s"}.</p>}

      {!loading && !error && visibleItems.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="grid justify-items-center gap-2 py-12 text-center">
            <ClipboardCheck className="h-8 w-8 text-teal-800" aria-hidden="true" />
            <p className="font-medium text-foreground">{items.length === 0 ? "Nothing is assigned to you yet" : "No work matches this view"}</p>
            <p className="max-w-md text-sm text-muted-foreground">{items.length === 0 ? "When a project manager assigns you a task, it will appear here with its project and due date." : "Try a different status or search term."}</p>
          </CardContent>
        </Card>
      )}

      <div className="space-y-6">
        {groups.map(({ title, items: groupItems }) => (
          <section key={title} aria-labelledby={`my-work-${title.toLowerCase().replaceAll(" ", "-")}`}>
            <div className="mb-2 flex items-center gap-2">
              {title === "Overdue" ? <CircleAlert className="h-4 w-4 text-rose-700" aria-hidden="true" /> : <CalendarDays className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
              <h3 id={`my-work-${title.toLowerCase().replaceAll(" ", "-")}`} className={`text-sm font-semibold ${title === "Overdue" ? "text-rose-800" : "text-[#294052]"}`}>{title}</h3>
              <Badge variant="secondary" className="h-5 px-1.5 text-[0.68rem]">{groupItems.length}</Badge>
            </div>
            <div className="divide-y overflow-hidden rounded-xl border border-[#e2e8ed] bg-white">
              {groupItems.map((item) => (
                <article key={item.id} className="grid gap-3 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="min-w-0 break-words text-sm font-semibold text-[#203448]">{item.title}</h4>
                      {item.priority === "urgent" && <Badge variant="outline" className="border-rose-200 bg-rose-50 text-rose-800">Urgent</Badge>}
                      {item.status === "blocked" && <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">Blocked</Badge>}
                    </div>
                    {item.description && <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{item.description}</p>}
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                      <button type="button" className="inline-flex items-center gap-1 font-medium text-teal-800 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => onOpenProject(item.project_id)}>
                        {item.project_title}<ArrowUpRight className="h-3 w-3" aria-hidden="true" /><span className="sr-only">Open project</span>
                      </button>
                      {item.due_date && <><span aria-hidden="true">·</span><time dateTime={item.due_date}>{formatDate(item.due_date)}</time></>}
                    </div>
                  </div>
                  {canManage && <Select value={item.status} onValueChange={(status) => { void onUpdate(item.project_id, item.id, { status: status as WorkItemStatus }).catch(() => undefined) }}>
                    <SelectTrigger aria-label={`Change status for ${item.title}`} className="h-8 w-full text-xs sm:w-36"><SelectValue /></SelectTrigger>
                    <SelectContent>{statusTransitions[item.status].map((status) => <SelectItem key={status} value={status}>{statusLabels[status]}</SelectItem>)}</SelectContent>
                  </Select>}
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
      {items.length < total && <div className="flex justify-center"><Button type="button" variant="outline" onClick={onLoadMore} disabled={loading}>{loading ? "Loading more…" : "Load more work"}</Button></div>}
      {loading && items.length > 0 && <p role="status" className="text-xs text-muted-foreground">Refreshing your work…</p>}
    </section>
  )
}
