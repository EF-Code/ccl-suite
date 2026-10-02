import { useRef, useState, type FormEvent } from "react"
import { CalendarDays, CircleAlert, ClipboardList, MessageSquare, Pencil, Plus, RefreshCw, Send, UserPlus, Users, X } from "lucide-react"

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
          {project && <Button type="button" variant="outline" onClick={() => { setTeamError(""); setTeamDialogOpen(true) }}><Users className="h-4 w-4" />Team <span className="ml-1 text-xs text-muted-foreground">{members.length}</span></Button>}
          {canManage && <Button type="button" onClick={openCreateDialog} disabled={!project}><Plus className="h-4 w-4" />New work item</Button>}
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
              {columnItems.map((item) => <WorkItemCard key={item.id} item={item} canManage={canManage} onUpdate={onUpdate} onEdit={openEditDialog} onDiscuss={(selectedItem) => void openDiscussion(selectedItem)} />)}
                  {!columnItems.length && <p className="rounded-xl border border-dashed border-[#d8e1e7] bg-white/60 px-3 py-5 text-center text-xs text-muted-foreground">{loading ? "Loading work…" : "No items here yet."}</p>}
                </div>
              </section>
            })}
          </div>
        </div>
        {items.some((item) => item.status === "cancelled") && <details className="rounded-xl border bg-white px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium text-[#41576a]">Cancelled items <span className="text-muted-foreground">({items.filter((item) => item.status === "cancelled").length})</span></summary>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{items.filter((item) => item.status === "cancelled").map((item) => <div key={item.id} className="rounded-lg border border-dashed px-3 py-2 text-sm text-muted-foreground">
            <div className="flex items-center justify-between gap-2"><span className="min-w-0 truncate">{item.title}</span><div className="flex items-center"><Button type="button" variant="ghost" size="icon" aria-label={`Discuss ${item.title}`} className="h-7 w-7" onClick={() => void openDiscussion(item)}><MessageSquare className="h-3.5 w-3.5" /></Button>{canManage && <Button type="button" variant="ghost" size="icon" aria-label={`Edit ${item.title}`} className="h-7 w-7" onClick={() => openEditDialog(item)}><Pencil className="h-3.5 w-3.5" /></Button>}</div></div>
            {canManage && <Select value={item.status} onValueChange={(status) => { void onUpdate(item.id, { status: status as WorkItemStatus }).catch(() => undefined) }}><SelectTrigger aria-label={`Change status for ${item.title}`} className="mt-2 h-8 text-xs"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="cancelled">Cancelled</SelectItem><SelectItem value="todo">Reopen to do</SelectItem></SelectContent></Select>}
          </div>)}</div>
        </details>}
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
