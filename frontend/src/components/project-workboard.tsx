import { useState, type FormEvent } from "react"
import { CalendarDays, CircleAlert, ClipboardList, Pencil, Plus, RefreshCw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { Project, WorkItem, WorkItemCreate, WorkItemPriority, WorkItemStatus, WorkItemUpdate } from "@/lib/api"

type ProjectWorkboardProps = {
  project: Project | null;
  items: WorkItem[];
  loading: boolean;
  error: string;
  canManage: boolean;
  onCreate: (item: WorkItemCreate) => Promise<void>;
  onUpdate: (itemId: string, changes: WorkItemUpdate) => Promise<void>;
  onRefresh: () => void;
}

const columns: Array<{ status: WorkItemStatus; title: string; description: string }> = [
  { status: "todo", title: "To do", description: "Ready to begin" },
  { status: "in_progress", title: "In progress", description: "Actively being worked on" },
  { status: "blocked", title: "Blocked", description: "Needs an unblock" },
  { status: "done", title: "Done", description: "Completed work" },
]

const statusLabels: Record<WorkItemStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  blocked: "Blocked",
  done: "Done",
  cancelled: "Cancelled",
}

const priorityStyles: Record<WorkItemPriority, string> = {
  low: "border-slate-200 bg-slate-50 text-slate-700",
  normal: "border-blue-200 bg-blue-50 text-blue-800",
  high: "border-amber-200 bg-amber-50 text-amber-800",
  urgent: "border-rose-200 bg-rose-50 text-rose-800",
}

const transitions: Record<WorkItemStatus, WorkItemStatus[]> = {
  todo: ["in_progress", "blocked", "done", "cancelled"],
  in_progress: ["todo", "blocked", "done", "cancelled"],
  blocked: ["todo", "in_progress", "done", "cancelled"],
  done: ["in_progress"],
  cancelled: ["todo"],
}

const dateFormatter = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" })

function formatDueDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number)
  const date = new Date(year, month - 1, day)
  return Number.isNaN(date.getTime()) ? "Date unavailable" : dateFormatter.format(date)
}

function isOverdue(value: string): boolean {
  const [year, month, day] = value.split("-").map(Number)
  const dueDate = new Date(year, month - 1, day)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return dueDate < today
}

function WorkItemCard({ item, canManage, onUpdate, onEdit }: {
  item: WorkItem;
  canManage: boolean;
  onUpdate: (itemId: string, changes: WorkItemUpdate) => Promise<void>;
  onEdit: (item: WorkItem) => void;
}) {
  const allowedStatuses = [item.status, ...transitions[item.status]]

  return (
    <article className="rounded-xl border border-[#e4e9ee] bg-white p-4 shadow-[0_2px_8px_rgba(21,43,64,0.035)]">
      <div className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 break-words text-sm font-semibold leading-5 text-[#203448]">{item.title}</h3>
        <Badge variant="outline" className={`shrink-0 capitalize ${priorityStyles[item.priority]}`}>{item.priority}</Badge>
      </div>
      {item.description && <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-xs leading-5 text-muted-foreground">{item.description}</p>}
      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted-foreground">
        {item.assignee && <span className="max-w-full truncate">Responsible: {item.assignee}</span>}
        {item.due_date && <span className={`inline-flex items-center gap-1 ${item.status !== "done" && isOverdue(item.due_date) ? "font-medium text-rose-700" : ""}`}>
          {item.status !== "done" && isOverdue(item.due_date) ? <CircleAlert className="h-3.5 w-3.5" aria-hidden="true" /> : <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />}
          <time dateTime={item.due_date}>{formatDueDate(item.due_date)}</time>
        </span>}
      </div>
      {canManage && <div className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3">
        <Select value={item.status} onValueChange={(status) => { void onUpdate(item.id, { status: status as WorkItemStatus }).catch(() => undefined) }}>
          <SelectTrigger aria-label={`Change status for ${item.title}`} className="h-8 flex-1 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>{allowedStatuses.map((status) => <SelectItem key={status} value={status}>{statusLabels[status]}</SelectItem>)}</SelectContent>
        </Select>
        <Button type="button" variant="ghost" size="sm" aria-label={`Edit ${item.title}`} className="h-8 px-2" onClick={() => onEdit(item)}><Pencil className="h-3.5 w-3.5" /><span className="sr-only">Edit</span></Button>
      </div>}
    </article>
  )
}

export function ProjectWorkboard({ project, items, loading, error, canManage, onCreate, onUpdate, onRefresh }: ProjectWorkboardProps) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<WorkItem | null>(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState("")

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const formData = new FormData(form)
    setSaving(true)
    setFormError("")
    try {
      const payload = {
        title: String(formData.get("title") || "").trim(),
        description: String(formData.get("description") || "").trim(),
        assignee: String(formData.get("assignee") || "").trim() || null,
        priority: String(formData.get("priority") || "normal") as WorkItemPriority,
        due_date: String(formData.get("due_date") || "") || null,
      }
      if (editingItem) await onUpdate(editingItem.id, payload)
      else await onCreate(payload)
      form.reset()
      setDialogOpen(false)
      setEditingItem(null)
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "The work item could not be saved.")
    } finally {
      setSaving(false)
    }
  }

  const activeCount = items.filter((item) => !["done", "cancelled"].includes(item.status)).length
  const overdueCount = items.filter((item) => item.status !== "done" && item.status !== "cancelled" && item.due_date && isOverdue(item.due_date)).length

  return (
    <section className="space-y-5" aria-labelledby="workboard-title">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-teal-800">Project delivery</p>
          <h2 id="workboard-title" className="text-2xl font-semibold tracking-tight text-[#1b2c3b]">Workboard</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">Plan and track the work that moves this project from brief to delivery.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" onClick={onRefresh} disabled={!project || loading}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</Button>
          {canManage && <Button type="button" onClick={() => { setEditingItem(null); setFormError(""); setDialogOpen(true) }} disabled={!project}><Plus className="h-4 w-4" />New work item</Button>}
        </div>
      </div>

      {!project ? <Card className="border-dashed"><CardContent className="grid justify-items-center gap-2 py-12 text-center"><ClipboardList className="h-8 w-8 text-muted-foreground" /><p className="font-medium text-foreground">Choose a project to see its workboard</p><p className="max-w-md text-sm text-muted-foreground">Work items stay inside the active project and follow its access permissions.</p></CardContent></Card> : <>
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-[#e1e8eb] bg-[#f7faf9] px-4 py-3 text-sm">
          <strong className="mr-1 max-w-full truncate text-[#244050]">{project.title}</strong>
          <span className="text-muted-foreground">{activeCount} active item{activeCount === 1 ? "" : "s"}</span>
          {overdueCount > 0 && <Badge variant="outline" className="border-rose-200 bg-rose-50 text-rose-800">{overdueCount} overdue</Badge>}
          {!canManage && <Badge variant="secondary">Read only</Badge>}
        </div>
        {error && <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"><span>{error}</span><Button type="button" variant="outline" size="sm" onClick={onRefresh}>Try again</Button></div>}
        <div className="overflow-x-auto pb-2">
          <div className="grid min-w-[960px] grid-cols-4 gap-4">
            {columns.map((column) => {
              const columnItems = items.filter((item) => item.status === column.status)
              return <section key={column.status} aria-labelledby={`workboard-${column.status}`} className="min-w-0 rounded-2xl border border-[#e2e8ed] bg-[#f4f7f9] p-3">
                <div className="mb-3 flex items-start justify-between gap-2 px-1">
                  <div><h3 id={`workboard-${column.status}`} className="text-sm font-semibold text-[#294052]">{column.title}</h3><p className="mt-0.5 text-[0.68rem] text-muted-foreground">{column.description}</p></div>
                  <span aria-label={`${columnItems.length} work items`} className="grid h-6 min-w-6 shrink-0 place-items-center rounded-full bg-white px-1.5 text-xs font-semibold text-[#506476]">{columnItems.length}</span>
                </div>
                <div className="space-y-2.5">
                  {columnItems.map((item) => <WorkItemCard key={item.id} item={item} canManage={canManage} onUpdate={onUpdate} onEdit={(selected) => { setEditingItem(selected); setFormError(""); setDialogOpen(true) }} />)}
                  {!columnItems.length && <p className="rounded-xl border border-dashed border-[#d8e1e7] bg-white/60 px-3 py-5 text-center text-xs text-muted-foreground">{loading ? "Loading work…" : "No items here yet."}</p>}
                </div>
              </section>
            })}
          </div>
        </div>
        {items.some((item) => item.status === "cancelled") && <details className="rounded-xl border bg-white px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium text-[#41576a]">Cancelled items <span className="text-muted-foreground">({items.filter((item) => item.status === "cancelled").length})</span></summary>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{items.filter((item) => item.status === "cancelled").map((item) => <div key={item.id} className="rounded-lg border border-dashed px-3 py-2 text-sm text-muted-foreground">
            <div className="flex items-center justify-between gap-2"><span className="min-w-0 truncate">{item.title}</span>{canManage && <Button type="button" variant="ghost" size="sm" aria-label={`Edit ${item.title}`} className="h-7 px-2" onClick={() => { setEditingItem(item); setFormError(""); setDialogOpen(true) }}><Pencil className="h-3.5 w-3.5" /></Button>}</div>
            {canManage && <Select value={item.status} onValueChange={(status) => { void onUpdate(item.id, { status: status as WorkItemStatus }).catch(() => undefined) }}><SelectTrigger aria-label={`Change status for ${item.title}`} className="mt-2 h-8 text-xs"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="cancelled">Cancelled</SelectItem><SelectItem value="todo">Reopen to do</SelectItem></SelectContent></Select>}
          </div>)}</div>
        </details>}
        {loading && items.length > 0 && <p className="text-xs text-muted-foreground" role="status">Refreshing work items…</p>}
      </>}

      <Dialog open={dialogOpen} onOpenChange={(open) => { if (!saving) { setDialogOpen(open); if (!open) setEditingItem(null) } }}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader><DialogTitle>{editingItem ? "Edit work item" : "Create work item"}</DialogTitle><DialogDescription>{editingItem ? "Update the details and delivery target for this item." : `Add a clear deliverable, responsible-person label, priority, and target date to ${project?.title || "the active project"}.`}</DialogDescription></DialogHeader>
          <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4">
            <div className="grid gap-2"><Label htmlFor="work-item-title">Title</Label><Input id="work-item-title" name="title" required minLength={1} maxLength={160} defaultValue={editingItem?.title || ""} placeholder="Draft the first script" /></div>
            <div className="grid gap-2"><Label htmlFor="work-item-description">Description <span className="font-normal text-muted-foreground">(optional)</span></Label><Textarea id="work-item-description" name="description" maxLength={2000} defaultValue={editingItem?.description || ""} placeholder="Define the expected outcome and any useful context." /></div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="grid content-start gap-2"><Label htmlFor="work-item-assignee">Responsible person</Label><Input id="work-item-assignee" name="assignee" maxLength={120} defaultValue={editingItem?.assignee || ""} placeholder="e.g. Video editor" /><p className="text-[0.68rem] leading-4 text-muted-foreground sm:col-span-3">A display label only; it does not grant account or project access.</p></div>
              <div className="grid content-start gap-2"><Label htmlFor="work-item-priority">Priority</Label><Select name="priority" defaultValue={editingItem?.priority || "normal"}><SelectTrigger id="work-item-priority"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="low">Low</SelectItem><SelectItem value="normal">Normal</SelectItem><SelectItem value="high">High</SelectItem><SelectItem value="urgent">Urgent</SelectItem></SelectContent></Select></div>
              <div className="grid content-start gap-2"><Label htmlFor="work-item-due-date">Due date</Label><Input id="work-item-due-date" name="due_date" type="date" defaultValue={editingItem?.due_date || ""} /></div>
            </div>
            {formError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{formError}</p>}
            <DialogFooter><Button type="button" variant="outline" onClick={() => setDialogOpen(false)} disabled={saving}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? "Saving…" : editingItem ? "Save changes" : "Create work item"}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </section>
  )
}
