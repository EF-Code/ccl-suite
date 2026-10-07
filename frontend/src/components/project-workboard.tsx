import { useMemo, useRef, useState, type FormEvent } from "react"
import { CalendarDays, ChevronLeft, ChevronRight, CircleAlert, ClipboardList, LayoutGrid, List, MessageSquare, Pencil, Plus, RefreshCw, RotateCcw, Search, Send, UserPlus, Users, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { Project, ProjectMember, ProjectMemberCandidate, WorkItem, WorkItemComment, WorkItemCommentsResponse, WorkItemCreate, WorkItemPriority, WorkItemStatus, WorkItemUpdate } from "@/lib/api"

type ProjectWorkboardProps = {
  project: Project | null;
  items: WorkItem[];
  loading: boolean;
  error: string;
  canManage: boolean;
  members: ProjectMember[];
  candidates: ProjectMemberCandidate[];
  membersLoading: boolean;
  membersError: string;
  canManageMembers: boolean;
  canPromoteMembers: boolean;
  onCreate: (item: WorkItemCreate) => Promise<void>;
  onUpdate: (itemId: string, changes: WorkItemUpdate) => Promise<void>;
  onListComments: (projectId: string, itemId: string, offset: number) => Promise<WorkItemCommentsResponse>;
  onAddComment: (projectId: string, itemId: string, body: string) => Promise<WorkItemComment>;
  onAddMember: (userId: string, role: "manager" | "member") => Promise<void>;
  onRemoveMember: (userId: string) => Promise<void>;
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
const monthFormatter = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" })
const weekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

type WorkboardView = "board" | "list" | "calendar"
type DueDateFilter = "all" | "overdue" | "this-week" | "no-date"

function dateKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`
}

function calendarDays(month: Date): Date[] {
  const firstDay = new Date(month.getFullYear(), month.getMonth(), 1)
  const mondayOffset = (firstDay.getDay() + 6) % 7
  const dayCount = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
  const cellCount = Math.ceil((mondayOffset + dayCount) / 7) * 7
  return Array.from({ length: cellCount }, (_, index) =>
    new Date(month.getFullYear(), month.getMonth(), index - mondayOffset + 1),
  )
}

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

function WorkItemCard({ item, canManage, onUpdate, onEdit, onDiscuss }: {
  item: WorkItem;
  canManage: boolean;
  onUpdate: (itemId: string, changes: WorkItemUpdate) => Promise<void>;
  onEdit: (item: WorkItem) => void;
  onDiscuss: (item: WorkItem) => void;
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
        <span className="max-w-full truncate">{item.assignee_id ? `Assigned: ${item.assignee || "Account"}` : item.assignee ? `Needs reassignment: ${item.assignee}` : "Unassigned"}</span>
        {item.due_date && <span className={`inline-flex items-center gap-1 ${item.status !== "done" && isOverdue(item.due_date) ? "font-medium text-rose-700" : ""}`}>
          {item.status !== "done" && isOverdue(item.due_date) ? <CircleAlert className="h-3.5 w-3.5" aria-hidden="true" /> : <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />}
          <time dateTime={item.due_date}>{formatDueDate(item.due_date)}</time>
        </span>}
      </div>
      <div className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3">
        <Button type="button" variant="ghost" size="sm" aria-label={`Discuss ${item.title}`} className="h-8 px-2 text-xs" onClick={() => onDiscuss(item)}><MessageSquare className="h-3.5 w-3.5" />Discuss</Button>
        {canManage && <>
          <Select value={item.status} onValueChange={(status) => { void onUpdate(item.id, { status: status as WorkItemStatus }).catch(() => undefined) }}>
            <SelectTrigger aria-label={`Change status for ${item.title}`} className="h-8 flex-1 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>{allowedStatuses.map((status) => <SelectItem key={status} value={status}>{statusLabels[status]}</SelectItem>)}</SelectContent>
          </Select>
          <Button type="button" variant="ghost" size="sm" aria-label={`Edit ${item.title}`} className="h-8 px-2" onClick={() => onEdit(item)}><Pencil className="h-3.5 w-3.5" /><span className="sr-only">Edit</span></Button>
        </>}
      </div>
    </article>
  )
}

export function ProjectWorkboard({ project, items, loading, error, canManage, members, candidates, membersLoading, membersError, canManageMembers, canPromoteMembers, onCreate, onUpdate, onListComments, onAddComment, onAddMember, onRemoveMember, onRefresh }: ProjectWorkboardProps) {
  const [view, setView] = useState<WorkboardView>("board")
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<WorkItemStatus | "all">("all")
  const [priorityFilter, setPriorityFilter] = useState<WorkItemPriority | "all">("all")
  const [assigneeFilter, setAssigneeFilter] = useState("all")
  const [dueDateFilter, setDueDateFilter] = useState<DueDateFilter>("all")
  const [calendarMonth, setCalendarMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1))
  const [dialogOpen, setDialogOpen] = useState(false)
  const [teamDialogOpen, setTeamDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<WorkItem | null>(null)
  const [assignmentChoice, setAssignmentChoice] = useState("unassigned")
  const [candidateUserId, setCandidateUserId] = useState("")
  const [newMemberRole, setNewMemberRole] = useState<"manager" | "member">("member")
  const [pendingRemoval, setPendingRemoval] = useState<ProjectMember | null>(null)
  const [memberActionId, setMemberActionId] = useState("")
  const [teamError, setTeamError] = useState("")
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState("")
  const [discussionItem, setDiscussionItem] = useState<WorkItem | null>(null)
  const [discussionComments, setDiscussionComments] = useState<WorkItemComment[]>([])
  const [discussionTotal, setDiscussionTotal] = useState(0)
  const [discussionOffset, setDiscussionOffset] = useState(0)
  const [discussionDraft, setDiscussionDraft] = useState("")
  const [discussionLoading, setDiscussionLoading] = useState(false)
  const [discussionSaving, setDiscussionSaving] = useState(false)
  const [discussionError, setDiscussionError] = useState("")
  const discussionRequestSequence = useRef(0)

  async function openDiscussion(item: WorkItem) {
    const requestSequence = ++discussionRequestSequence.current
    setDiscussionItem(item)
    setDiscussionComments([])
    setDiscussionTotal(0)
    setDiscussionOffset(0)
    setDiscussionDraft("")
    setDiscussionError("")
    setDiscussionLoading(true)
    try {
      const result = await onListComments(item.project_id, item.id, 0)
      if (requestSequence !== discussionRequestSequence.current) return
      setDiscussionComments([...result.comments].reverse())
      setDiscussionTotal(result.total)
      setDiscussionOffset(result.comments.length)
    } catch (reason) {
      if (requestSequence === discussionRequestSequence.current) {
        setDiscussionError(reason instanceof Error ? reason.message : "Comments could not be loaded.")
      }
    } finally {
      if (requestSequence === discussionRequestSequence.current) setDiscussionLoading(false)
    }
  }

  async function loadEarlierComments() {
    if (!discussionItem || discussionLoading) return
    const requestSequence = discussionRequestSequence.current
    setDiscussionLoading(true)
    setDiscussionError("")
    try {
      const result = await onListComments(discussionItem.project_id, discussionItem.id, discussionOffset)
      if (requestSequence !== discussionRequestSequence.current) return
      setDiscussionComments(current => [...result.comments].reverse().concat(current))
      setDiscussionTotal(result.total)
      setDiscussionOffset(current => current + result.comments.length)
    } catch (reason) {
      if (requestSequence === discussionRequestSequence.current) {
        setDiscussionError(reason instanceof Error ? reason.message : "Earlier comments could not be loaded.")
      }
    } finally {
      if (requestSequence === discussionRequestSequence.current) setDiscussionLoading(false)
    }
  }

  async function handleCommentSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!discussionItem || !discussionDraft.trim() || discussionSaving) return
    const requestSequence = discussionRequestSequence.current
    setDiscussionSaving(true)
    setDiscussionError("")
    try {
      const comment = await onAddComment(discussionItem.project_id, discussionItem.id, discussionDraft.trim())
      if (requestSequence !== discussionRequestSequence.current) return
      setDiscussionComments(current => [...current, comment])
      setDiscussionTotal(current => current + 1)
      setDiscussionOffset(current => current + 1)
      setDiscussionDraft("")
    } catch (reason) {
      if (requestSequence === discussionRequestSequence.current) {
        setDiscussionError(reason instanceof Error ? reason.message : "Comment could not be posted.")
      }
    } finally {
      setDiscussionSaving(false)
    }
  }

  function closeDiscussion() {
    discussionRequestSequence.current += 1
    setDiscussionItem(null)
    setDiscussionComments([])
    setDiscussionTotal(0)
    setDiscussionOffset(0)
    setDiscussionDraft("")
    setDiscussionLoading(false)
    setDiscussionSaving(false)
    setDiscussionError("")
  }

  function openCreateDialog() {
    setEditingItem(null)
    setAssignmentChoice("unassigned")
    setFormError("")
    setDialogOpen(true)
  }

  function openEditDialog(item: WorkItem) {
    setEditingItem(item)
    setAssignmentChoice(item.assignee_id || (item.assignee ? "legacy" : "unassigned"))
    setFormError("")
    setDialogOpen(true)
  }

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
        assignee_id: assignmentChoice === "unassigned" ? null : assignmentChoice,
        priority: String(formData.get("priority") || "normal") as WorkItemPriority,
        due_date: String(formData.get("due_date") || "") || null,
      }
      const originalAssignment = editingItem?.assignee_id || (editingItem?.assignee ? "legacy" : "unassigned")
      if (editingItem && (assignmentChoice === "legacy" || assignmentChoice === originalAssignment)) {
        const { assignee_id: _assigneeId, ...preservedPayload } = payload
        await onUpdate(editingItem.id, preservedPayload)
      } else if (editingItem) await onUpdate(editingItem.id, payload)
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

  async function handleAddMember() {
    if (!candidateUserId) return
    setMemberActionId(candidateUserId)
    setTeamError("")
    try {
      await onAddMember(candidateUserId, newMemberRole)
      setCandidateUserId("")
      setNewMemberRole("member")
    } catch (reason) {
      setTeamError(reason instanceof Error ? reason.message : "The account could not be added to this project.")
    } finally {
      setMemberActionId("")
    }
  }

  async function handleRemoveMember(member: ProjectMember) {
    setMemberActionId(member.user_id)
    setTeamError("")
    try {
      await onRemoveMember(member.user_id)
      setPendingRemoval(null)
    } catch (reason) {
      setTeamError(reason instanceof Error ? reason.message : "The project member could not be removed.")
      setPendingRemoval(null)
    } finally {
      setMemberActionId("")
    }
  }

  const activeCount = items.filter((item) => !["done", "cancelled"].includes(item.status)).length
  const overdueCount = items.filter((item) => item.status !== "done" && item.status !== "cancelled" && item.due_date && isOverdue(item.due_date)).length
  const today = dateKey(new Date())
  const weekStart = new Date()
  weekStart.setHours(0, 0, 0, 0)
  weekStart.setDate(weekStart.getDate() - ((weekStart.getDay() + 6) % 7))
  const weekEnd = new Date(weekStart)
  weekEnd.setDate(weekEnd.getDate() + 6)
  const weekStartKey = dateKey(weekStart)
  const weekEndKey = dateKey(weekEnd)
  const filteredItems = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase()
    return items.filter((item) => {
      if (statusFilter !== "all" && item.status !== statusFilter) return false
      if (priorityFilter !== "all" && item.priority !== priorityFilter) return false
      if (assigneeFilter === "unassigned" && item.assignee_id !== null) return false
      if (assigneeFilter !== "all" && assigneeFilter !== "unassigned" && item.assignee_id !== assigneeFilter) return false
      if (dueDateFilter === "no-date" && item.due_date !== null) return false
      if (dueDateFilter === "overdue" && (!item.due_date || item.due_date >= today || ["done", "cancelled"].includes(item.status))) return false
      if (dueDateFilter === "this-week" && (!item.due_date || item.due_date < weekStartKey || item.due_date > weekEndKey)) return false
      if (normalizedSearch && ![item.title, item.description, item.assignee || ""].some((value) => value.toLocaleLowerCase().includes(normalizedSearch))) return false
      return true
    })
  }, [assigneeFilter, dueDateFilter, items, priorityFilter, search, statusFilter, today, weekEndKey, weekStartKey])
  const visibleCalendarDays = useMemo(() => calendarDays(calendarMonth), [calendarMonth])
  const hasFilters = Boolean(search.trim()) || statusFilter !== "all" || priorityFilter !== "all" || assigneeFilter !== "all" || dueDateFilter !== "all"

  function clearFilters() {
    setSearch("")
    setStatusFilter("all")
    setPriorityFilter("all")
    setAssigneeFilter("all")
    setDueDateFilter("all")
  }

  return (
    <section className="workboard-page space-y-5" aria-labelledby="workboard-title">
      <div className="workboard-page-header flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-teal-800">Project delivery</p>
          <h1 id="workboard-title" className="text-2xl font-semibold tracking-tight text-[#1b2c3b]">Workboard</h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">Plan and track the work that moves this project from brief to delivery.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" onClick={onRefresh} disabled={!project || loading}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</Button>
          {project && <Button type="button" variant="outline" onClick={() => { setTeamError(""); setTeamDialogOpen(true) }}><Users className="h-4 w-4" />Team <span className="ml-1 text-xs text-muted-foreground">{members.length}</span></Button>}
          {canManage && <Button type="button" onClick={openCreateDialog} disabled={!project}><Plus className="h-4 w-4" />New work item</Button>}
        </div>
      </div>

      {!project ? <Card className="border-dashed"><CardContent className="grid justify-items-center gap-2 py-12 text-center"><ClipboardList className="h-8 w-8 text-muted-foreground" /><p className="font-medium text-foreground">Choose a project to see its workboard</p><p className="max-w-md text-sm text-muted-foreground">Work items stay inside the active project and follow its access permissions.</p></CardContent></Card> : <>
        <div className="workboard-project-context flex flex-wrap items-center gap-3 rounded-xl border border-[#e1e8eb] bg-[#f7faf9] px-4 py-3 text-sm">
          <strong className="mr-1 max-w-full truncate text-[#244050]">{project.title}</strong>
          <span className="text-muted-foreground">{activeCount} open · {items.length} total task{items.length === 1 ? "" : "s"}</span>
          {overdueCount > 0 && <Badge variant="outline" className="border-rose-200 bg-rose-50 text-rose-800">{overdueCount} overdue</Badge>}
          {!canManage && <Badge variant="secondary">Read only</Badge>}
        </div>
        {error && <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"><span>{error}</span><Button type="button" variant="outline" size="sm" onClick={onRefresh}>Try again</Button></div>}
        <div className="grid gap-3 rounded-2xl border border-[#e2e8ed] bg-white p-3 sm:p-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(12rem,1.5fr)_repeat(4,minmax(8rem,1fr))_auto]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input value={search} onChange={(event) => setSearch(event.target.value)} className="pl-9" placeholder="Search tasks or assignees" aria-label="Search project tasks" />
            </label>
            <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as WorkItemStatus | "all")}>
              <SelectTrigger aria-label="Filter by status"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="all">All statuses</SelectItem>{Object.entries(statusLabels).map(([key, label]) => <SelectItem key={key} value={key}>{label}</SelectItem>)}</SelectContent>
            </Select>
            <Select value={priorityFilter} onValueChange={(value) => setPriorityFilter(value as WorkItemPriority | "all")}>
              <SelectTrigger aria-label="Filter by priority"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="all">All priorities</SelectItem><SelectItem value="urgent">Urgent</SelectItem><SelectItem value="high">High</SelectItem><SelectItem value="normal">Normal</SelectItem><SelectItem value="low">Low</SelectItem></SelectContent>
            </Select>
            <Select value={assigneeFilter} onValueChange={setAssigneeFilter}>
              <SelectTrigger aria-label="Filter by assignee"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="all">All assignees</SelectItem><SelectItem value="unassigned">Unassigned</SelectItem>{members.filter((member) => member.is_active).map((member) => <SelectItem key={member.user_id} value={member.user_id}>{member.email || "Account without email"}</SelectItem>)}</SelectContent>
            </Select>
            <Select value={dueDateFilter} onValueChange={(value) => setDueDateFilter(value as DueDateFilter)}>
              <SelectTrigger aria-label="Filter by due date"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="all">Any due date</SelectItem><SelectItem value="overdue">Overdue</SelectItem><SelectItem value="this-week">Due this week</SelectItem><SelectItem value="no-date">No due date</SelectItem></SelectContent>
            </Select>
            <Button type="button" variant="ghost" onClick={clearFilters} disabled={!hasFilters} className="justify-self-start"><RotateCcw className="h-4 w-4" />Clear</Button>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#edf1f3] pt-3">
            <p className="text-xs text-muted-foreground" aria-live="polite">Showing <strong className="font-semibold text-foreground">{filteredItems.length}</strong> of {items.length} tasks</p>
            <div role="group" aria-label="Task view" className="inline-flex rounded-xl border bg-[#f7faf9] p-1">
              {([
                ["board", "Board", LayoutGrid],
                ["list", "List", List],
                ["calendar", "Calendar", CalendarDays],
              ] as const).map(([key, label, Icon]) => <button key={key} type="button" aria-pressed={view === key} className={`inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${view === key ? "bg-white text-[#173b48] shadow-sm" : "text-muted-foreground hover:text-foreground"}`} onClick={() => setView(key)}><Icon className="h-4 w-4" aria-hidden="true" />{label}</button>)}
            </div>
          </div>
        </div>
        {filteredItems.length === 0 && <Card className="border-dashed"><CardContent className="grid justify-items-center gap-2 py-10 text-center"><Search className="h-7 w-7 text-muted-foreground" aria-hidden="true" /><p className="font-medium text-foreground">No tasks match these filters</p><p className="text-sm text-muted-foreground">Try changing a filter or clearing the search.</p>{hasFilters && <Button type="button" variant="outline" size="sm" onClick={clearFilters}>Clear filters</Button>}</CardContent></Card>}
        {view === "board" && filteredItems.length > 0 && <div className="overflow-x-auto pb-2">
          <div className="grid min-w-[960px] grid-cols-4 gap-4">
            {columns.map((column) => {
              const columnItems = filteredItems.filter((item) => item.status === column.status)
              return <section key={column.status} aria-labelledby={`workboard-${column.status}`} className="min-w-0 rounded-2xl border border-[#e2e8ed] bg-[#f4f7f9] p-3">
                <div className="mb-3 flex items-start justify-between gap-2 px-1">
                  <div><h3 id={`workboard-${column.status}`} className="text-sm font-semibold text-[#294052]">{column.title}</h3><p className="mt-0.5 text-[0.68rem] text-muted-foreground">{column.description}</p></div>
                  <span aria-label={`${columnItems.length} work items`} className="grid h-6 min-w-6 shrink-0 place-items-center rounded-full bg-white px-1.5 text-xs font-semibold text-[#506476]">{columnItems.length}</span>
                </div>
                <div className="space-y-2.5">
              {columnItems.map((item) => <WorkItemCard key={item.id} item={item} canManage={canManage} onUpdate={onUpdate} onEdit={openEditDialog} onDiscuss={(selectedItem) => void openDiscussion(selectedItem)} />)}
                  {!columnItems.length && <p className="rounded-xl border border-dashed border-[#d8e1e7] bg-white/60 px-3 py-5 text-center text-xs text-muted-foreground">{loading ? "Loading work…" : "No items here yet."}</p>}
                </div>
              </section>
            })}
          </div>
        </div>}
        {view === "board" && filteredItems.some((item) => item.status === "cancelled") && <details className="rounded-xl border bg-white px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium text-[#41576a]">Cancelled items <span className="text-muted-foreground">({filteredItems.filter((item) => item.status === "cancelled").length})</span></summary>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{filteredItems.filter((item) => item.status === "cancelled").map((item) => <div key={item.id} className="rounded-lg border border-dashed px-3 py-2 text-sm text-muted-foreground">
            <div className="flex items-center justify-between gap-2"><span className="min-w-0 truncate">{item.title}</span><div className="flex items-center"><Button type="button" variant="ghost" size="icon" aria-label={`Discuss ${item.title}`} className="h-7 w-7" onClick={() => void openDiscussion(item)}><MessageSquare className="h-3.5 w-3.5" /></Button>{canManage && <Button type="button" variant="ghost" size="icon" aria-label={`Edit ${item.title}`} className="h-7 w-7" onClick={() => openEditDialog(item)}><Pencil className="h-3.5 w-3.5" /></Button>}</div></div>
            {canManage && <Select value={item.status} onValueChange={(status) => { void onUpdate(item.id, { status: status as WorkItemStatus }).catch(() => undefined) }}><SelectTrigger aria-label={`Change status for ${item.title}`} className="mt-2 h-8 text-xs"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="cancelled">Cancelled</SelectItem><SelectItem value="todo">Reopen to do</SelectItem></SelectContent></Select>}
          </div>)}</div>
        </details>}
        {view === "list" && filteredItems.length > 0 && <div className="overflow-x-auto rounded-2xl border border-[#e2e8ed] bg-white">
          <table className="w-full min-w-[760px] border-collapse text-left text-sm">
            <thead className="bg-[#f7faf9] text-xs text-muted-foreground"><tr><th className="px-4 py-3 font-medium">Task</th><th className="px-4 py-3 font-medium">Assignee</th><th className="px-4 py-3 font-medium">Due date</th><th className="px-4 py-3 font-medium">Priority</th><th className="px-4 py-3 font-medium">Status</th><th className="px-4 py-3 font-medium"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody className="divide-y">
              {filteredItems.map((item) => <tr key={item.id} className="align-top hover:bg-[#fbfcfc]">
                <td className="max-w-[24rem] px-4 py-3"><p className="font-semibold text-[#203448]">{item.title}</p>{item.description && <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{item.description}</p>}</td>
                <td className="px-4 py-3 text-xs text-[#41576a]">{item.assignee_id ? item.assignee || "Account" : item.assignee ? `Needs reassignment: ${item.assignee}` : "Unassigned"}</td>
                <td className="whitespace-nowrap px-4 py-3 text-xs text-[#41576a]">{item.due_date ? formatDueDate(item.due_date) : "No due date"}</td>
                <td className="px-4 py-3"><Badge variant="outline" className={`capitalize ${priorityStyles[item.priority]}`}>{item.priority}</Badge></td>
                <td className="min-w-36 px-4 py-3">{canManage ? <Select value={item.status} onValueChange={(status) => { void onUpdate(item.id, { status: status as WorkItemStatus }).catch(() => undefined) }}><SelectTrigger aria-label={`Change status for ${item.title}`} className="h-8 text-xs"><SelectValue /></SelectTrigger><SelectContent>{[item.status, ...transitions[item.status]].map((status) => <SelectItem key={status} value={status}>{statusLabels[status]}</SelectItem>)}</SelectContent></Select> : <span className="text-xs">{statusLabels[item.status]}</span>}</td>
                <td className="whitespace-nowrap px-3 py-2"><div className="flex items-center"><Button type="button" variant="ghost" size="icon" className="h-8 w-8" aria-label={`Discuss ${item.title}`} onClick={() => void openDiscussion(item)}><MessageSquare className="h-4 w-4" /></Button>{canManage && <Button type="button" variant="ghost" size="icon" className="h-8 w-8" aria-label={`Edit ${item.title}`} onClick={() => openEditDialog(item)}><Pencil className="h-4 w-4" /></Button>}</div></td>
              </tr>)}
            </tbody>
          </table>
        </div>}
        {view === "calendar" && filteredItems.length > 0 && <section className="space-y-4" aria-label="Task calendar">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#e2e8ed] bg-white px-4 py-3">
            <h3 className="text-lg font-semibold text-[#203448]">{monthFormatter.format(calendarMonth)}</h3>
            <div className="flex items-center gap-2"><Button type="button" variant="outline" size="sm" onClick={() => setCalendarMonth(new Date())}>Today</Button><Button type="button" variant="outline" size="icon" aria-label="Previous month" onClick={() => setCalendarMonth((month) => new Date(month.getFullYear(), month.getMonth() - 1, 1))}><ChevronLeft className="h-4 w-4" /></Button><Button type="button" variant="outline" size="icon" aria-label="Next month" onClick={() => setCalendarMonth((month) => new Date(month.getFullYear(), month.getMonth() + 1, 1))}><ChevronRight className="h-4 w-4" /></Button></div>
          </div>
          <div className="overflow-x-auto rounded-2xl border border-[#e2e8ed] bg-white">
            <div className="min-w-[700px]">
              <div className="grid grid-cols-7 border-b bg-[#f7faf9]">{weekdayLabels.map((label) => <div key={label} className="px-2 py-2.5 text-center text-xs font-semibold text-muted-foreground">{label}</div>)}</div>
              <div className="grid grid-cols-7">
                {visibleCalendarDays.map((day) => {
                  const key = dateKey(day)
                  const dayItems = filteredItems.filter((item) => item.due_date === key)
                  const inMonth = day.getMonth() === calendarMonth.getMonth()
                  return <div key={key} className={`min-h-28 border-b border-r border-[#edf1f3] p-1.5 ${inMonth ? "bg-white" : "bg-[#fafbfb]"}`}>
                    <div className={`mb-1 grid h-7 w-7 place-items-center rounded-full text-xs ${key === today ? "bg-[#173b48] font-semibold text-white" : inMonth ? "text-[#41576a]" : "text-slate-400"}`}>{day.getDate()}</div>
                    <div className="space-y-1">
                      {dayItems.slice(0, 3).map((item) => <button key={item.id} type="button" title={`${item.title} · ${statusLabels[item.status]} · ${item.priority} priority`} className={`block w-full truncate rounded-md border px-1.5 py-1 text-left text-[0.68rem] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${item.status === "done" ? "border-emerald-200 bg-emerald-50 text-emerald-900" : item.status === "blocked" ? "border-amber-200 bg-amber-50 text-amber-900" : "border-[#dce7e6] bg-[#eef6f4] text-[#174b4b]"}`} onClick={() => canManage ? openEditDialog(item) : void openDiscussion(item)}>{item.title}</button>)}
                      {dayItems.length > 3 && <p className="px-1 text-[0.65rem] text-muted-foreground">+{dayItems.length - 3} more</p>}
                    </div>
                  </div>
                })}
              </div>
            </div>
          </div>
          {filteredItems.some((item) => !item.due_date) && <section aria-labelledby="workboard-unscheduled-title" className="space-y-2">
            <h4 id="workboard-unscheduled-title" className="text-sm font-semibold text-[#294052]">Unscheduled work <span className="font-normal text-muted-foreground">({filteredItems.filter((item) => !item.due_date).length})</span></h4>
            <div className="divide-y overflow-hidden rounded-xl border border-[#e2e8ed] bg-white">{filteredItems.filter((item) => !item.due_date).map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"><div className="min-w-0"><p className="truncate text-sm font-medium text-[#203448]">{item.title}</p><p className="text-xs text-muted-foreground">{statusLabels[item.status]} · {item.assignee || "Unassigned"}</p></div><div className="flex items-center gap-1"><Badge variant="outline" className={`capitalize ${priorityStyles[item.priority]}`}>{item.priority}</Badge>{canManage && <Button type="button" variant="ghost" size="icon" aria-label={`Edit ${item.title}`} onClick={() => openEditDialog(item)}><Pencil className="h-4 w-4" /></Button>}</div></div>)}</div>
          </section>}
        </section>}
        {loading && items.length > 0 && <p className="text-xs text-muted-foreground" role="status">Refreshing work items…</p>}
      </>}

      <Dialog open={dialogOpen} onOpenChange={(open) => { if (!saving) { setDialogOpen(open); if (!open) setEditingItem(null) } }}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader><DialogTitle>{editingItem ? "Edit work item" : "Create work item"}</DialogTitle><DialogDescription>{editingItem ? "Update the details and delivery target for this item." : `Add a clear deliverable, a project member, a priority, and a target date to ${project?.title || "the active project"}.`}</DialogDescription></DialogHeader>
          <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4">
            <div className="grid gap-2"><Label htmlFor="work-item-title">Title</Label><Input id="work-item-title" name="title" required minLength={1} maxLength={160} defaultValue={editingItem?.title || ""} placeholder="Draft the first script" /></div>
            <div className="grid gap-2"><Label htmlFor="work-item-description">Description <span className="font-normal text-muted-foreground">(optional)</span></Label><Textarea id="work-item-description" name="description" maxLength={2000} defaultValue={editingItem?.description || ""} placeholder="Define the expected outcome and any useful context." /></div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="grid content-start gap-2"><Label htmlFor="work-item-assignee">Assigned to</Label><Select value={assignmentChoice} onValueChange={setAssignmentChoice}><SelectTrigger id="work-item-assignee"><SelectValue /></SelectTrigger><SelectContent>
                <SelectItem value="unassigned">Unassigned</SelectItem>
                {editingItem && !editingItem.assignee_id && editingItem.assignee && <SelectItem value="legacy">Legacy label · {editingItem.assignee}</SelectItem>}
                {editingItem?.assignee_id && !members.some((member) => member.user_id === editingItem.assignee_id && member.is_active && member.account_role !== "intern") && <SelectItem value={editingItem.assignee_id}>Current assignment · {editingItem.assignee || "unavailable account"}</SelectItem>}
                {members.filter((member) => member.is_active && member.account_role !== "intern").map((member) => <SelectItem key={member.user_id} value={member.user_id}>{member.email || "Account without email"}{member.user_id === project?.owner_id ? " · Owner" : ""}</SelectItem>)}
              </SelectContent></Select>
                <p className="text-[0.68rem] leading-4 text-muted-foreground">Only active project members can be assigned. Legacy labels stay unchanged until you choose a member.</p>
              </div>
              <div className="grid content-start gap-2"><Label htmlFor="work-item-priority">Priority</Label><Select name="priority" defaultValue={editingItem?.priority || "normal"}><SelectTrigger id="work-item-priority"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="low">Low</SelectItem><SelectItem value="normal">Normal</SelectItem><SelectItem value="high">High</SelectItem><SelectItem value="urgent">Urgent</SelectItem></SelectContent></Select></div>
              <div className="grid content-start gap-2"><Label htmlFor="work-item-due-date">Due date</Label><Input id="work-item-due-date" name="due_date" type="date" defaultValue={editingItem?.due_date || ""} /></div>
            </div>
            {formError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{formError}</p>}
            <DialogFooter><Button type="button" variant="outline" onClick={() => setDialogOpen(false)} disabled={saving}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? "Saving…" : editingItem ? "Save changes" : "Create work item"}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(discussionItem)} onOpenChange={(open) => !open && closeDiscussion()}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Task discussion</DialogTitle>
            <DialogDescription>{discussionItem?.title} · {project?.title || "Project"}. Comments are visible to project members and retained as project history.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-medium text-muted-foreground">{discussionTotal} {discussionTotal === 1 ? "comment" : "comments"}</p>
              {discussionLoading && <span role="status" className="text-xs text-muted-foreground">Loading…</span>}
            </div>
            {discussionError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{discussionError}</p>}
            <div aria-label="Task comments" className="max-h-[min(42vh,24rem)] space-y-2 overflow-y-auto rounded-xl border bg-slate-50/70 p-3">
              {discussionComments.length < discussionTotal && <Button type="button" variant="outline" size="sm" className="w-full" onClick={() => void loadEarlierComments()} disabled={discussionLoading}>Load earlier comments</Button>}
              {discussionComments.length === 0 && !discussionLoading && !discussionError && <p className="px-3 py-8 text-center text-sm text-muted-foreground">No comments yet. Add the context your teammates need to move this task forward.</p>}
              {discussionComments.map(comment => <article key={comment.id} className="rounded-lg border bg-white px-3 py-2.5">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <p className="max-w-full truncate text-xs font-semibold text-[#294052]">{comment.author_label}</p>
                  <time dateTime={comment.created_at} className="text-[0.68rem] text-muted-foreground">{new Date(comment.created_at).toLocaleString()}</time>
                </div>
                <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-[#34495a]">{comment.body}</p>
              </article>)}
            </div>
            {canManage ? <form onSubmit={(event) => void handleCommentSubmit(event)} className="grid gap-2">
              <Label htmlFor="work-item-comment-draft">Add an update</Label>
              <Textarea id="work-item-comment-draft" value={discussionDraft} onChange={event => setDiscussionDraft(event.target.value)} maxLength={4000} rows={3} placeholder="Share a decision, question, or handoff note…" disabled={discussionSaving} />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-muted-foreground">Comments cannot be edited or deleted after posting.</p>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" onClick={closeDiscussion} disabled={discussionSaving}>Close</Button>
                  <Button type="submit" disabled={!discussionDraft.trim() || discussionSaving}><Send className="h-4 w-4" />{discussionSaving ? "Posting…" : "Post comment"}</Button>
                </div>
              </div>
            </form> : <DialogFooter><Button type="button" variant="outline" onClick={closeDiscussion}>Close</Button></DialogFooter>}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={teamDialogOpen} onOpenChange={(open) => { setTeamDialogOpen(open); if (!open) setTeamError("") }}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader><DialogTitle>Project team</DialogTitle><DialogDescription>Membership grants access to this project. Task assignment is managed separately.</DialogDescription></DialogHeader>
          {(teamError || membersError) && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{teamError || membersError}</p>}
          {membersLoading && <p className="text-sm text-muted-foreground" role="status">Loading project team…</p>}
          <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
            {members.length === 0 && !membersLoading && !membersError && <p className="rounded-lg border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">No team membership records were returned.</p>}
            {members.map((member) => {
              const isOwner = member.user_id === project?.owner_id
              const canRemove = member.role !== "manager" || canPromoteMembers
              return <div key={member.user_id} className="flex items-center gap-3 rounded-xl border px-3 py-2.5">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[#e8f2ef] text-xs font-semibold text-teal-900">{(member.email || "?").slice(0, 1).toUpperCase()}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-[#203448]">{member.email || "Account email unavailable"}</p>
                  <p className="truncate text-xs text-muted-foreground">{member.account_role} account · {isOwner ? "Project owner" : member.role}{!member.is_active ? " · Disabled" : ""}</p>
                </div>
                {isOwner ? <Badge variant="secondary">Owner</Badge> : canManageMembers && (canRemove ? <Button type="button" variant="ghost" size="icon" aria-label={`Remove ${member.email || "member"} from project team`} disabled={Boolean(memberActionId)} onClick={() => setPendingRemoval(member)}>
                  {memberActionId === member.user_id ? <RefreshCw className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
                </Button> : <Badge variant="outline">Manager</Badge>)}
              </div>
            })}
          </div>
          {canManageMembers && <div className="border-t pt-4">
            <h3 className="mb-3 text-sm font-semibold text-[#294052]">Add an invited account</h3>
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_9rem_auto] sm:items-end">
              <div className="grid gap-2"><Label htmlFor="project-team-candidate">Account</Label><Select value={candidateUserId || "choose-account"} onValueChange={(value) => setCandidateUserId(value === "choose-account" ? "" : value)}><SelectTrigger id="project-team-candidate"><SelectValue placeholder="Choose an account" /></SelectTrigger><SelectContent>
                <SelectItem value="choose-account">Choose an account</SelectItem>
                {candidates.filter((candidate) => !candidate.is_member).map((candidate) => <SelectItem key={candidate.user_id} value={candidate.user_id}>{candidate.email} · {candidate.account_role}</SelectItem>)}
              </SelectContent></Select>
                {candidates.length > 0 && candidates.every((candidate) => candidate.is_member) && <p className="text-xs text-muted-foreground">All active invited accounts are already on this project.</p>}
                {candidates.length === 0 && !membersLoading && !membersError && <p className="text-xs text-muted-foreground">No active invited accounts are available to add.</p>}
              </div>
              <div className="grid gap-2"><Label htmlFor="project-team-role">Project role</Label><Select value={newMemberRole} onValueChange={(value) => setNewMemberRole(value as "manager" | "member")}><SelectTrigger id="project-team-role"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="member">Member</SelectItem>{canPromoteMembers && <SelectItem value="manager">Manager</SelectItem>}</SelectContent></Select></div>
              <Button type="button" onClick={() => void handleAddMember()} disabled={!candidateUserId || Boolean(memberActionId)}>{memberActionId && memberActionId === candidateUserId ? <RefreshCw className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}Add</Button>
            </div>
          </div>}
          <DialogFooter><Button type="button" variant="outline" onClick={() => setTeamDialogOpen(false)}>Close</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(pendingRemoval)} onOpenChange={(open) => { if (!open && !memberActionId) setPendingRemoval(null) }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Remove team membership?</DialogTitle>
            <DialogDescription>{pendingRemoval?.email || "This account"} will no longer be a member of {project?.title || "this project"}. Administrator and supervisor accounts retain their global access. Any open tasks must be reassigned first; membership can be restored later.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setPendingRemoval(null)} disabled={Boolean(memberActionId)}>Keep member</Button>
            <Button type="button" variant="destructive" onClick={() => pendingRemoval && void handleRemoveMember(pendingRemoval)} disabled={!pendingRemoval || Boolean(memberActionId)}>{memberActionId ? <RefreshCw className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}Remove access</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
