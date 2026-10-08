import { useMemo, useState, type FormEvent } from "react"
import { ArrowUpRight, CalendarDays, Check, CircleAlert, FileText, Film, Link2, MessageSquareText, Plus, RefreshCw, Send, ShieldCheck, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { type ContentAssetRole, type ContentPlatform, type ContentReviewDecision, type ContentReviewRequest, type FileRecord, type Project, type ProjectMember, type WorkItem, type WorkItemCreate, type WorkItemUpdate } from "@/lib/api"

type ContentProductionProps = {
  project: Project | null;
  items: WorkItem[];
  files: FileRecord[];
  members: ProjectMember[];
  loading: boolean;
  error: string;
  canManage: boolean;
  canReview: boolean;
  onCreate: (item: WorkItemCreate) => Promise<void>;
  onUpdate: (itemId: string, changes: WorkItemUpdate) => Promise<void>;
  onRequestReview: (projectId: string, itemId: string, details: ContentReviewRequest) => Promise<WorkItem>;
  onDecideReview: (projectId: string, itemId: string, reviewId: string, decision: ContentReviewDecision) => Promise<WorkItem>;
  onAttachAsset: (projectId: string, itemId: string, asset: { file_id: string; role: ContentAssetRole }) => Promise<void>;
  onDetachAsset: (projectId: string, itemId: string, fileId: string) => Promise<void>;
  onOpenFile: (fileId: string) => void;
  onRefresh: () => void;
};

type ContentFormItem = WorkItem | null;

const platformLabels: Record<ContentPlatform, string> = {
  youtube: "YouTube",
  tiktok: "TikTok",
  cross_platform: "Cross-platform",
  other: "Other",
};

const formatLabels = {
  long_video: "Long-form video",
  short_video: "Short-form video",
  community_post: "Community post",
  live: "Live stream",
  other: "Other format",
} as const;

const stageLabels = {
  brief: "Brief",
  scripting: "Scripting",
  editing: "Editing",
  in_review: "In review",
  changes_requested: "Changes requested",
  approved: "Approved",
  scheduled: "Scheduled",
  published: "Published",
} as const;

type ContentStage = keyof typeof stageLabels;

const stageMoves: Partial<Record<ContentStage, ContentStage[]>> = {
  brief: ["scripting"],
  scripting: ["brief", "editing"],
  editing: ["scripting"],
  changes_requested: ["scripting", "editing"],
  approved: ["scheduled"],
  scheduled: ["published"],
};

const lanes: Array<{ title: string; detail: string; stages: ContentStage[] }> = [
  { title: "Developing", detail: "Shape the brief, script, and edit.", stages: ["brief", "scripting", "editing", "changes_requested"] },
  { title: "Review", detail: "A project lead makes the decision.", stages: ["in_review"] },
  { title: "Release queue", detail: "Approved items move toward publication.", stages: ["approved", "scheduled"] },
  { title: "Published", detail: "Live work stays visible for reference.", stages: ["published"] },
];

const assetRoles: Array<{ value: ContentAssetRole; label: string }> = [
  { value: "brief", label: "Brief" },
  { value: "script", label: "Script" },
  { value: "caption", label: "Caption" },
  { value: "thumbnail", label: "Thumbnail" },
  { value: "reference", label: "Reference" },
];

function dateLabel(value: string | null): string {
  if (!value) return "Publish date not set"
  const [year, month, day] = value.split("-").map(Number)
  const date = new Date(year, month - 1, day)
  return Number.isNaN(date.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(date)
}

function sortedItems(items: WorkItem[]): WorkItem[] {
  return [...items].sort((left, right) => {
    if (left.publish_date && right.publish_date) return left.publish_date.localeCompare(right.publish_date) || left.title.localeCompare(right.title)
    if (left.publish_date) return -1
    if (right.publish_date) return 1
    return left.title.localeCompare(right.title)
  })
}

function ContentCard({ item, files, canManage, canReview, projectId, onUpdate, onRequestReview, onOpenReview, onAttachAsset, onDetachAsset, onOpenFile, onEdit }: {
  item: WorkItem;
  files: FileRecord[];
  canManage: boolean;
  canReview: boolean;
  projectId: string;
  onUpdate: (itemId: string, changes: WorkItemUpdate) => Promise<void>;
  onRequestReview: (projectId: string, itemId: string, details: ContentReviewRequest) => Promise<WorkItem>;
  onOpenReview: (item: WorkItem) => void;
  onAttachAsset: ContentProductionProps["onAttachAsset"];
  onDetachAsset: ContentProductionProps["onDetachAsset"];
  onOpenFile: (fileId: string) => void;
  onEdit: (item: WorkItem) => void;
}) {
  const [assetFileId, setAssetFileId] = useState("")
  const [assetRole, setAssetRole] = useState<ContentAssetRole>("script")
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState("")
  const latestReview = item.content_reviews[item.content_reviews.length - 1] || null
  const linkedIds = new Set(item.content_assets.map((asset) => asset.file_id))
  const availableFiles = files.filter((file) => file.status === "active" && !linkedIds.has(file.id))
  const allowedMoves = stageMoves[item.content_stage || "brief"] || []
  async function runAction(action: () => Promise<void>) {
    setBusy(true)
    setActionError("")
    try {
      await action()
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "The change could not be saved.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="overflow-hidden rounded-xl border border-[#dfe7e9] bg-white shadow-[0_2px_8px_rgba(21,43,64,0.035)]" data-content-item={item.id}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="secondary" className="bg-[#e7f2ef] text-[#155b55]">{platformLabels[item.content_platform || "other"]}</Badge>
              <Badge variant="outline">{formatLabels[item.content_format || "other"]}</Badge>
              {item.status === "cancelled" && <Badge variant="destructive">Cancelled</Badge>}
            </div>
            <h3 className="mt-2 break-words text-sm font-semibold leading-5 text-[#203448]">{item.title}</h3>
            <p className="mt-1 truncate text-xs font-medium text-[#496170]">{item.content_channel}</p>
          </div>
          {canManage && <Button type="button" variant="ghost" size="sm" className="h-8 shrink-0 px-2 text-xs" onClick={() => onEdit(item)}>Edit details</Button>}
        </div>

        {item.description && <p className="mt-3 line-clamp-3 whitespace-pre-wrap text-xs leading-5 text-muted-foreground">{item.description}</p>}

        {actionError && <p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-800">{actionError}</p>}

        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />{dateLabel(item.publish_date)}</span>
          <span>{item.assignee_id ? item.assignee || "Assigned teammate" : "Unassigned"}</span>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
          <Badge variant="outline" className={item.content_stage === "in_review" ? "border-violet-200 bg-violet-50 text-violet-800" : item.content_stage === "published" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : ""}>
            {stageLabels[item.content_stage || "brief"]}
          </Badge>
          {canManage && item.status !== "cancelled" && allowedMoves.length > 0 && <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="sr-only">Move {item.title} to stage</span>
            <select
              aria-label={`Move ${item.title} to next stage`}
              className="h-8 max-w-40 rounded-md border border-input bg-white px-2 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value=""
              disabled={busy}
              onChange={(event) => {
                const next = event.currentTarget.value as ContentStage
                if (next) void runAction(() => onUpdate(item.id, { content_stage: next }))
              }}
            >
              <option value="">Move to…</option>
              {allowedMoves.map((stage) => <option key={stage} value={stage}>{stageLabels[stage]}</option>)}
            </select>
          </label>}
        </div>

        {item.status === "cancelled" && <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-800">This item is cancelled. Reopen it from My Work before moving it through the production stages.</p>}

        {item.content_stage === "in_review" && latestReview && <div className="mt-3 rounded-lg border border-violet-200 bg-violet-50/70 p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-violet-950"><ShieldCheck className="h-4 w-4" aria-hidden="true" />Review requested</div>
          {latestReview.request_note && <p className="mt-1 text-xs leading-5 text-violet-900">{latestReview.request_note}</p>}
          {canReview && <Button type="button" size="sm" variant="outline" className="mt-2 border-violet-300 bg-white" onClick={() => onOpenReview(item)}>Review content</Button>}
        </div>}
        {item.content_stage === "changes_requested" && latestReview?.decision_note && <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-950"><CircleAlert className="h-4 w-4" aria-hidden="true" />Reviewer notes</div>
          <p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-amber-900">{latestReview.decision_note}</p>
        </div>}
        {item.content_stage === "approved" && latestReview?.decision_note && <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs leading-5 text-emerald-900">Lead approved this item: {latestReview.decision_note}</p>}

        {canManage && ["scripting", "editing"].includes(item.content_stage || "") && <Button type="button" variant="secondary" size="sm" className="mt-3" disabled={busy} onClick={() => void runAction(() => onRequestReview(projectId, item.id, { request_note: "" }).then(() => undefined))}>
          <Send className="h-3.5 w-3.5" aria-hidden="true" />Request review
        </Button>}

        <div className="mt-4 border-t border-slate-100 pt-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="flex items-center gap-1.5 text-xs font-semibold text-[#294052]"><Link2 className="h-3.5 w-3.5" aria-hidden="true" />Working files <span className="text-muted-foreground">({item.content_assets.length})</span></h4>
          </div>
          {item.content_assets.length > 0 ? <ul className="space-y-1.5">
            {item.content_assets.map((asset) => <li key={asset.file_id} className="flex min-w-0 items-center gap-2 rounded-lg bg-[#f7faf9] px-2.5 py-2">
              <FileText className="h-3.5 w-3.5 shrink-0 text-teal-800" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate text-xs font-medium text-[#334b5a]">{asset.file.name}</span>
              <Badge variant="outline" className="shrink-0 text-[0.65rem]">{asset.role}</Badge>
              <Button type="button" variant="ghost" size="icon" className="h-7 w-7 shrink-0" aria-label={`Open ${asset.file.name} in project files`} onClick={() => onOpenFile(asset.file_id)}><ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" /></Button>
              {canManage && <Button type="button" variant="ghost" size="icon" className="h-7 w-7 shrink-0 text-muted-foreground hover:text-rose-700" aria-label={`Unlink ${asset.file.name}`} disabled={busy} onClick={() => void runAction(() => onDetachAsset(projectId, item.id, asset.file_id))}><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></Button>}
            </li>)}
          </ul> : <p className="rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">No working files linked yet.</p>}

          {canManage && <form className="mt-2 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]" onSubmit={(event) => {
            event.preventDefault()
            if (!assetFileId) return
            void runAction(async () => {
              await onAttachAsset(projectId, item.id, { file_id: assetFileId, role: assetRole })
              setAssetFileId("")
            })
          }}>
            <select aria-label={`Choose a project file to link to ${item.title}`} className="h-9 min-w-0 rounded-md border border-input bg-white px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={assetFileId} onChange={(event) => setAssetFileId(event.currentTarget.value)} disabled={!availableFiles.length || busy}>
              <option value="">{availableFiles.length ? "Choose a project file…" : "No unlinked active files"}</option>
              {availableFiles.map((file) => <option key={file.id} value={file.id}>{file.name}</option>)}
            </select>
            <select aria-label={`File purpose for ${item.title}`} className="h-9 rounded-md border border-input bg-white px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={assetRole} onChange={(event) => setAssetRole(event.currentTarget.value as ContentAssetRole)} disabled={busy}>
              {assetRoles.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}
            </select>
            <Button type="submit" size="sm" variant="outline" disabled={!assetFileId || busy}><Link2 className="h-3.5 w-3.5" aria-hidden="true" />Link file</Button>
          </form>}
        </div>
      </div>
    </article>
  )
}

export function ContentProduction({ project, items, files, members, loading, error, canManage, canReview, onCreate, onUpdate, onRequestReview, onDecideReview, onAttachAsset, onDetachAsset, onOpenFile, onRefresh }: ContentProductionProps) {
  const [query, setQuery] = useState("")
  const [platformFilter, setPlatformFilter] = useState("all")
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<ContentFormItem>(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState("")
  const [reviewItem, setReviewItem] = useState<WorkItem | null>(null)
  const [reviewDecision, setReviewDecision] = useState<"approved" | "changes_requested">("approved")
  const [reviewNote, setReviewNote] = useState("")
  const [reviewError, setReviewError] = useState("")
  const [reviewSaving, setReviewSaving] = useState(false)

  const visibleItems = useMemo(() => sortedItems(items.filter((item) => {
    const normalized = query.trim().toLowerCase()
    const matchesText = !normalized || [item.title, item.description, item.content_channel || "", item.assignee || ""].some((value) => value.toLowerCase().includes(normalized))
    return matchesText && (platformFilter === "all" || item.content_platform === platformFilter)
  })), [items, platformFilter, query])
  const pendingReviews = items.filter((item) => item.content_stage === "in_review").length
  const upcoming = items.filter((item) => item.publish_date && item.content_stage !== "published").length

  function openCreate() {
    setEditingItem(null)
    setFormError("")
    setEditorOpen(true)
  }

  function openEdit(item: WorkItem) {
    setEditingItem(item)
    setFormError("")
    setEditorOpen(true)
  }

  async function saveContent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!project || saving) return
    const form = new FormData(event.currentTarget)
    const title = String(form.get("title") || "").trim()
    const description = String(form.get("description") || "").trim()
    const platform = String(form.get("platform") || "youtube") as ContentPlatform
    const channel = String(form.get("channel") || "").trim()
    const contentFormat = String(form.get("content_format") || "short_video") as WorkItemCreate["content_format"]
    const assigneeId = String(form.get("assignee_id") || "") || null
    const priority = String(form.get("priority") || "normal") as WorkItemCreate["priority"]
    const publishDate = String(form.get("publish_date") || "") || null
    if (!title || !channel) {
      setFormError("Add a title and channel or account name.")
      return
    }
    setSaving(true)
    setFormError("")
    try {
      if (editingItem) {
        await onUpdate(editingItem.id, {
          title,
          description,
          assignee_id: assigneeId,
          priority,
          content_platform: platform,
          content_channel: channel,
          content_format: contentFormat,
          publish_date: publishDate,
        })
      } else {
        await onCreate({
          title,
          description,
          assignee_id: assigneeId,
          priority,
          due_date: null,
          work_type: "content",
          content_platform: platform,
          content_channel: channel,
          content_format: contentFormat,
          publish_date: publishDate,
        })
      }
      setEditorOpen(false)
      setEditingItem(null)
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "The content item could not be saved.")
    } finally {
      setSaving(false)
    }
  }

  async function submitReviewDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!project || !reviewItem || reviewSaving) return
    if (reviewDecision === "changes_requested" && !reviewNote.trim()) {
      setReviewError("Add a note so the creator knows what to revise.")
      return
    }
    const review = reviewItem.content_reviews[reviewItem.content_reviews.length - 1]
    if (!review) {
      setReviewError("This item no longer has a pending review. Refresh the content desk.")
      return
    }
    setReviewSaving(true)
    setReviewError("")
    try {
      await onDecideReview(project.id, reviewItem.id, review.id, {
        decision: reviewDecision,
        decision_note: reviewNote.trim() || null,
      })
      setReviewItem(null)
      setReviewNote("")
    } catch (reason) {
      setReviewError(reason instanceof Error ? reason.message : "The review decision could not be recorded.")
    } finally {
      setReviewSaving(false)
    }
  }

  return (
    <section className="space-y-5" aria-labelledby="content-production-title">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-teal-800">Editorial desk</p>
          <h1 id="content-production-title" className="text-2xl font-semibold tracking-tight text-[#1b2c3b]">Content production</h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">Keep the brief, assigned teammate, review decision, and publish date together from first draft to release.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" onClick={onRefresh} disabled={!project || loading}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />Refresh</Button>
          {canManage && <Button type="button" onClick={openCreate} disabled={!project}><Plus className="h-4 w-4" aria-hidden="true" />New content item</Button>}
        </div>
      </div>

      {!project ? <Card className="border-dashed"><CardContent className="grid justify-items-center gap-2 py-12 text-center"><Film className="h-8 w-8 text-teal-800" aria-hidden="true" /><p className="font-medium text-foreground">Choose a project to open its content desk</p><p className="max-w-md text-sm text-muted-foreground">Editorial items and working files stay inside the selected project's access boundary.</p></CardContent></Card> : <>
        <div className="grid gap-3 sm:grid-cols-3" aria-label="Content production summary">
          <div className="rounded-xl border border-[#dce7e6] bg-[#f7faf9] px-4 py-3"><p className="text-xs font-medium text-muted-foreground">In production</p><p className="mt-1 text-xl font-semibold tabular-nums text-[#203448]">{items.filter((item) => item.status !== "cancelled" && !["published", "in_review", "approved", "scheduled"].includes(item.content_stage || "")).length}</p></div>
          <div className="rounded-xl border border-violet-200 bg-violet-50/60 px-4 py-3"><p className="text-xs font-medium text-violet-800">Waiting for review</p><p className="mt-1 text-xl font-semibold tabular-nums text-violet-950">{pendingReviews}</p></div>
          <div className="rounded-xl border border-[#dce7e6] bg-white px-4 py-3"><p className="text-xs font-medium text-muted-foreground">Publish dates set</p><p className="mt-1 text-xl font-semibold tabular-nums text-[#203448]">{upcoming}</p></div>
        </div>

        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-[#dce7e6] bg-white p-3">
          <div className="relative min-w-[12rem] flex-1">
            <Input aria-label="Search content items" placeholder="Search titles, channels, or teammates" value={query} onChange={(event) => setQuery(event.target.value)} />
          </div>
          <select aria-label="Filter content by platform" className="h-10 rounded-md border border-input bg-white px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={platformFilter} onChange={(event) => setPlatformFilter(event.currentTarget.value)}>
            <option value="all">All platforms</option>
            <option value="youtube">YouTube</option>
            <option value="tiktok">TikTok</option>
            <option value="cross_platform">Cross-platform</option>
            <option value="other">Other</option>
          </select>
          <span className="text-xs text-muted-foreground" aria-live="polite">{visibleItems.length} of {items.length} items</span>
        </div>

        <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-xs leading-5 text-amber-950"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><p>Link briefs, scripts, captions, thumbnails, and references from project Files. The current upload policy is for small documents and images (up to 1 MB); raw video stays on your local media storage and is not uploaded here.</p></div>

        {error && <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"><span>{error}</span><Button type="button" variant="outline" size="sm" onClick={onRefresh}>Try again</Button></div>}
        {loading && items.length === 0 && <p role="status" className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">Loading content items…</p>}
        {!loading && !error && items.length === 0 && <Card className="border-dashed"><CardContent className="grid justify-items-center gap-2 py-12 text-center"><Film className="h-8 w-8 text-teal-800" aria-hidden="true" /><p className="font-medium text-foreground">No content in this project yet</p><p className="max-w-md text-sm text-muted-foreground">Start with a channel brief. Add a teammate and target date now; link the script, caption, and thumbnail as they are created.</p>{canManage && <Button type="button" onClick={openCreate}><Plus className="h-4 w-4" aria-hidden="true" />Create the first content item</Button>}</CardContent></Card>}
        {items.length > 0 && visibleItems.length === 0 && <Card className="border-dashed"><CardContent className="py-8 text-center text-sm text-muted-foreground">No items match this search and platform filter.</CardContent></Card>}

        {visibleItems.length > 0 && <>
          <p className="text-xs text-muted-foreground xl:hidden">Scroll across the editorial lanes to follow each handoff.</p>
          <div className="overflow-x-auto pb-2">
            <div className="grid min-w-[68rem] grid-cols-4 gap-3 xl:gap-4">
              {lanes.map((lane) => {
                const laneItems = visibleItems.filter((item) => lane.stages.includes(item.content_stage || "brief"))
                return <section key={lane.title} aria-label={`${lane.title}, ${laneItems.length} items`} className="min-w-0 rounded-2xl border border-[#e2e8ed] bg-[#f4f7f9] p-3">
                  <header className="mb-3 flex items-start justify-between gap-2 px-1">
                    <div><h2 className="text-sm font-semibold text-[#294052]">{lane.title}</h2><p className="mt-0.5 text-[0.68rem] leading-4 text-muted-foreground">{lane.detail}</p></div>
                    <span className="grid h-6 min-w-6 shrink-0 place-items-center rounded-full bg-white px-1.5 text-xs font-semibold text-[#506476]">{laneItems.length}</span>
                  </header>
                  <div className="space-y-3">
                    {laneItems.map((item) => <ContentCard
                      key={item.id}
                      item={item}
                      files={files}
                      canManage={canManage}
                      canReview={canReview}
                      projectId={project.id}
                      onUpdate={onUpdate}
                      onRequestReview={onRequestReview}
                      onOpenReview={(selected) => { setReviewItem(selected); setReviewDecision("approved"); setReviewNote(""); setReviewError("") }}
                      onAttachAsset={onAttachAsset}
                      onDetachAsset={onDetachAsset}
                      onOpenFile={onOpenFile}
                      onEdit={openEdit}
                    />)}
                    {!laneItems.length && <p className="rounded-xl border border-dashed border-[#d8e1e7] bg-white/60 px-3 py-5 text-center text-xs text-muted-foreground">Nothing in this lane yet.</p>}
                  </div>
                </section>
              })}
            </div>
          </div>
        </>}
      </>}

      <Dialog open={editorOpen} onOpenChange={(open) => { if (!saving) setEditorOpen(open) }}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader><DialogTitle>{editingItem ? "Edit content details" : "Plan a content item"}</DialogTitle><DialogDescription>Capture the channel, format, owner, and target date. Upload small working documents in Operations, then link them here.</DialogDescription></DialogHeader>
          <form key={editingItem?.id || "new-content"} id="content-item-form" onSubmit={(event) => void saveContent(event)} className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5 sm:col-span-2"><Label htmlFor="content-item-title">Working title</Label><Input id="content-item-title" name="title" required maxLength={160} defaultValue={editingItem?.title || ""} placeholder="e.g. Three ways to improve the first 10 seconds" /></div>
            <div className="grid gap-1.5"><Label htmlFor="content-platform">Platform</Label><select id="content-platform" name="platform" defaultValue={editingItem?.content_platform || "youtube"} className="h-10 rounded-md border border-input bg-white px-3 text-sm"><option value="youtube">YouTube</option><option value="tiktok">TikTok</option><option value="cross_platform">Cross-platform</option><option value="other">Other</option></select></div>
            <div className="grid gap-1.5"><Label htmlFor="content-channel">Channel or account</Label><Input id="content-channel" name="channel" required maxLength={120} defaultValue={editingItem?.content_channel || ""} placeholder="Internal channel name" /></div>
            <div className="grid gap-1.5"><Label htmlFor="content-format">Format</Label><select id="content-format" name="content_format" defaultValue={editingItem?.content_format || "short_video"} className="h-10 rounded-md border border-input bg-white px-3 text-sm"><option value="long_video">Long-form video</option><option value="short_video">Short-form video</option><option value="community_post">Community post</option><option value="live">Live stream</option><option value="other">Other</option></select></div>
            <div className="grid gap-1.5"><Label htmlFor="content-assignee">Owner</Label><select id="content-assignee" name="assignee_id" defaultValue={editingItem?.assignee_id || ""} className="h-10 rounded-md border border-input bg-white px-3 text-sm"><option value="">Unassigned</option>{members.filter((member) => member.is_active).map((member) => <option key={member.user_id} value={member.user_id}>{member.email || "Project teammate"}</option>)}</select></div>
            <div className="grid gap-1.5"><Label htmlFor="content-priority">Priority</Label><select id="content-priority" name="priority" defaultValue={editingItem?.priority || "normal"} className="h-10 rounded-md border border-input bg-white px-3 text-sm"><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></div>
            <div className="grid gap-1.5"><Label htmlFor="content-publish-date">Target publish date</Label><Input id="content-publish-date" name="publish_date" type="date" defaultValue={editingItem?.publish_date || ""} /></div>
            <div className="grid gap-1.5 sm:col-span-2"><Label htmlFor="content-description">Brief and handoff notes</Label><Textarea id="content-description" name="description" rows={4} maxLength={2000} defaultValue={editingItem?.description || ""} placeholder="Audience, angle, key points, or what the next teammate needs to know." /></div>
          </form>
          {formError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{formError}</p>}
          <DialogFooter><Button type="button" variant="outline" onClick={() => setEditorOpen(false)} disabled={saving}>Cancel</Button><Button type="submit" form="content-item-form" disabled={saving || !project}>{saving ? "Saving…" : editingItem ? "Save details" : "Create content item"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(reviewItem)} onOpenChange={(open) => { if (!open && !reviewSaving) setReviewItem(null) }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Review content</DialogTitle><DialogDescription>{reviewItem?.title}. Approve it for scheduling or return it with clear revision guidance.</DialogDescription></DialogHeader>
          <form id="content-review-form" onSubmit={(event) => void submitReviewDecision(event)} className="grid gap-3">
            <div className="grid gap-2 sm:grid-cols-2" role="group" aria-label="Review decision">
              <button type="button" aria-pressed={reviewDecision === "approved"} className={`rounded-lg border p-3 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${reviewDecision === "approved" ? "border-emerald-400 bg-emerald-50 text-emerald-950" : "bg-white text-foreground"}`} onClick={() => setReviewDecision("approved")}><span className="flex items-center gap-2 font-semibold"><Check className="h-4 w-4" aria-hidden="true" />Approve</span><span className="mt-1 block text-xs opacity-80">The team can schedule the item.</span></button>
              <button type="button" aria-pressed={reviewDecision === "changes_requested"} className={`rounded-lg border p-3 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${reviewDecision === "changes_requested" ? "border-amber-400 bg-amber-50 text-amber-950" : "bg-white text-foreground"}`} onClick={() => setReviewDecision("changes_requested")}><span className="flex items-center gap-2 font-semibold"><MessageSquareText className="h-4 w-4" aria-hidden="true" />Request changes</span><span className="mt-1 block text-xs opacity-80">A note is required for the creator.</span></button>
            </div>
            <div className="grid gap-1.5"><Label htmlFor="content-review-note">{reviewDecision === "changes_requested" ? "What should change?" : "Reviewer note (optional)"}</Label><Textarea id="content-review-note" value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} rows={4} maxLength={2000} required={reviewDecision === "changes_requested"} placeholder={reviewDecision === "changes_requested" ? "Be specific about the edit or script changes needed." : "Add context for the team, if useful."} /></div>
          </form>
          {reviewError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{reviewError}</p>}
          <DialogFooter><Button type="button" variant="outline" onClick={() => setReviewItem(null)} disabled={reviewSaving}>Cancel</Button><Button type="submit" form="content-review-form" disabled={reviewSaving}>{reviewSaving ? "Saving decision…" : reviewDecision === "approved" ? "Approve for scheduling" : "Request changes"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
