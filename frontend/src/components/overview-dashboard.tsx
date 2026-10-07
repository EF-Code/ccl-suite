import { ArrowUpRight, BookOpen, Check, CircleAlert, Clock3, FileText, FolderOpen, GitBranch, ListChecks, Plus, ShieldCheck } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { Approval, FileRecord, KnowledgeSource, Project, ResearchClaim, ResearchReviewResponse, Workflow, WorkItem } from "@/lib/api"
import type { ReactNode } from "react"

type OverviewTarget = "workboard" | "operations" | "files" | "knowledge" | "research" | "workflows" | "recovery" | "setup"

type OverviewHealth = {
  ok: boolean
  text: string
  detail: string
}

type OverviewDashboardProps = {
  project: Project | null
  health: OverviewHealth
  files: FileRecord[]
  knowledgeSources: KnowledgeSource[]
  researchClaims: ResearchClaim[]
  researchReview: ResearchReviewResponse | null
  workflows: Workflow[]
  workItems: WorkItem[]
  workItemsLoading: boolean
  approvals: Record<string, Approval[]>
  onNavigate: (view: OverviewTarget) => void
}

const dateFormatter = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" })

function formatDate(value?: string | null): string {
  if (!value) return "Not recorded"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? "Date unavailable" : dateFormatter.format(date)
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function statusLabel(status: string): string {
  return status.replaceAll("_", " ")
}

function statusTone(status: string): string {
  if (status === "approved" || status === "active") return "overview-status overview-status--good"
  if (status === "pending" || status === "needs_review" || status === "changes_requested") return "overview-status overview-status--attention"
  if (status === "rejected" || status === "cancelled") return "overview-status overview-status--quiet"
  return "overview-status overview-status--neutral"
}

function fileIcon(extension: string) {
  return extension.toLowerCase() === ".pdf" ? <FileText className="h-4 w-4 text-rose-600" /> : <FileText className="h-4 w-4 text-teal-700" />
}

export function OverviewDashboard({
  project,
  health,
  files,
  knowledgeSources,
  researchClaims,
  researchReview,
  workflows,
  workItems,
  workItemsLoading,
  approvals,
  onNavigate,
}: OverviewDashboardProps) {
  const approvalList = workflows.flatMap((workflow) => approvals[workflow.id] || [])
  const pendingApprovals = approvalList.filter((approval) => approval.status === "pending")
  const activeWorkItems = workItems.filter((item) => !["done", "cancelled"].includes(item.status))
  const completedWorkItems = workItems.filter((item) => item.status === "done")
  const currentWorkflow = workflows[0]
  const projectReady = Boolean(project)
  const evidenceStatus = researchReview?.status || (researchClaims.length ? "needs_review" : "not_started")
  const evidenceLabel = researchReview ? statusLabel(researchReview.status) : researchClaims.length ? "Preview ready" : "Not started"
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`
  const overdueWorkItems = activeWorkItems.filter((item) => item.due_date && item.due_date < today)
  const blockedWorkItems = activeWorkItems.filter((item) => item.status === "blocked")
  const unassignedWorkItems = activeWorkItems.filter((item) => !item.assignee_id)
  const workStatusSummary = [
    { status: "todo", label: "To do", detail: "Ready to start", count: workItems.filter((item) => item.status === "todo").length },
    { status: "in_progress", label: "In progress", detail: "Being worked on", count: workItems.filter((item) => item.status === "in_progress").length },
    { status: "blocked", label: "Blocked", detail: "Needs an unblock", count: workItems.filter((item) => item.status === "blocked").length },
    { status: "done", label: "Done", detail: "Completed tasks", count: workItems.filter((item) => item.status === "done").length },
  ]

  const nextActions: Array<{ title: string; detail: string; label: string; target: OverviewTarget; tone: string }> = []
  if (!project) {
    nextActions.push({ title: "Create your first project", detail: "Set up a workspace before planning the team’s work.", label: "Open setup", target: "setup", tone: "attention" })
  } else if (!workItemsLoading) {
    if (workItems.length === 0) {
      nextActions.push({ title: "Plan the first deliverables", detail: "Turn the brief into clear tasks with owners and target dates.", label: "Open workboard", target: "workboard", tone: "good" })
    }
    if (activeWorkItems.length === 0 && completedWorkItems.length > 0) {
      nextActions.push({ title: "Review completed work", detail: `${completedWorkItems.length} task${completedWorkItems.length === 1 ? " is" : "s are"} marked done. Review the handoff or plan the next run.`, label: "Open workboard", target: "workboard", tone: "good" })
    }
    if (overdueWorkItems.length > 0) {
      nextActions.push({ title: "Review overdue work", detail: `${overdueWorkItems.length} open task${overdueWorkItems.length === 1 ? " is" : "s are"} past its target date.`, label: "Open workboard", target: "workboard", tone: "attention" })
    }
    if (blockedWorkItems.length > 0) {
      nextActions.push({ title: "Unblock team work", detail: `${blockedWorkItems.length} task${blockedWorkItems.length === 1 ? " needs" : "s need"} attention before it can move forward.`, label: "Open workboard", target: "workboard", tone: "attention" })
    }
    if (unassignedWorkItems.length > 0 && workItems.length > 0) {
      nextActions.push({ title: "Assign owners to open tasks", detail: `${unassignedWorkItems.length} open task${unassignedWorkItems.length === 1 ? " has" : "s have"} no account assigned yet.`, label: "Open workboard", target: "workboard", tone: "neutral" })
    }
    if (pendingApprovals.length > 0) {
      nextActions.push({ title: "Review pending approval", detail: `${pendingApprovals.length} decision${pendingApprovals.length === 1 ? " is" : "s are"} waiting for an authorized reviewer.`, label: "Open approvals", target: "workflows", tone: "attention" })
    }
    if (files.length === 0) {
      nextActions.push({ title: "Add project reference files", detail: "Keep the brief and working references in the project workspace.", label: "Open file operations", target: "operations", tone: "neutral" })
    }
  }

  const activity = [
    project && { icon: <FolderOpen className="h-4 w-4" />, title: "Active project selected", detail: project.title, date: formatDate(project.updated_at) },
    files.length > 0 && { icon: <FileText className="h-4 w-4" />, title: `${files.length} active file${files.length === 1 ? "" : "s"} indexed`, detail: files[0]?.name || "Project inventory", date: formatDate(files[0]?.updated_at) },
    knowledgeSources.length > 0 && { icon: <BookOpen className="h-4 w-4" />, title: `${knowledgeSources.length} knowledge source${knowledgeSources.length === 1 ? "" : "s"} registered`, detail: knowledgeSources[0]?.title || "Knowledge register", date: formatDate(knowledgeSources[0]?.created_at) },
    workflows.length > 0 && { icon: <GitBranch className="h-4 w-4" />, title: "Workflow control is available", detail: currentWorkflow?.name || "Project workflow", date: formatDate(currentWorkflow?.updated_at) },
  ].filter(Boolean) as Array<{ icon: ReactNode; title: string; detail: string; date: string }>

  return (
    <section id="overview-dashboard" className="overview-dashboard" aria-labelledby="overview-title">
      <div className="overview-heading">
        <div>
          <h1 id="overview-title">Keep every project moving.</h1>
          <p>Plan scripts, edits, reviews, and publishing work—and see what needs attention next.</p>
        </div>
        <div className="overview-heading-actions">
          <Button type="button" variant="outline" onClick={() => onNavigate("workboard")} disabled={!project}>
            <ListChecks className="mr-1.5 h-4 w-4" />Open workboard
          </Button>
          <Button type="button" onClick={() => onNavigate("setup")}>
            <Plus className="mr-1.5 h-4 w-4" />New project
          </Button>
        </div>
      </div>

      <div className="overview-top-grid">
        <Card className="overview-card overview-project-card">
          <CardHeader className="overview-card-header flex-row">
            <div>
              <p className="overview-label">Active project</p>
              <CardTitle>{project?.title || "No project selected"}</CardTitle>
              <CardDescription>{project?.description || "Select or create a project to see its operating picture here."}</CardDescription>
            </div>
            <Button type="button" variant="ghost" size="icon" className="overview-more" onClick={() => onNavigate(project ? "setup" : "setup")} aria-label="Open project setup">
              <ArrowUpRight className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent className="overview-project-meta">
            <span><FolderOpen className="h-4 w-4" />{project?.storage_slug || "Project workspace"}</span>
            <span><ListChecks className="h-4 w-4" />{activeWorkItems.length} open · {workItems.length} total task{workItems.length === 1 ? "" : "s"}</span>
            <span><ListChecks className="h-4 w-4" />{workflows.length} workflow{workflows.length === 1 ? "" : "s"}</span>
            <span><Clock3 className="h-4 w-4" />Updated {formatDate(project?.updated_at)}</span>
            <span className={projectReady ? "overview-status overview-status--good" : "overview-status overview-status--attention"}>{projectReady ? "Ready" : "Setup required"}</span>
          </CardContent>
        </Card>

        <Card className="overview-card overview-health-card">
          <CardHeader className="overview-card-header flex-row">
            <div><p className="overview-label">System health</p><CardTitle>{health.ok ? "Service ready" : "Service unavailable"}</CardTitle></div>
            <ShieldCheck className={`h-5 w-5 ${health.ok ? "text-teal-600" : "text-amber-600"}`} />
          </CardHeader>
          <CardContent className="overview-health-content">
            <div
              className={`overview-health-indicator ${health.ok ? "is-healthy" : "is-warning"}`}
              role="img"
              aria-label={health.ok ? "API is reachable" : "API is unavailable"}
            >
              {health.ok ? <Check className="h-7 w-7" aria-hidden="true" /> : <CircleAlert className="h-7 w-7" aria-hidden="true" />}
            </div>
            <div className="overview-health-legend">
              <span><i className={`overview-dot ${health.ok ? "overview-dot--good" : "overview-dot--attention"}`} />{health.ok ? "API reachable" : "API unavailable"}</span>
              {project ? (
                <>
                  <span><i className="overview-dot overview-dot--attention" />{pendingApprovals.length} pending approval{pendingApprovals.length === 1 ? "" : "s"}</span>
                  <span><i className="overview-dot overview-dot--neutral" />{activeWorkItems.length} open task{activeWorkItems.length === 1 ? "" : "s"}</span>
                  <span><i className="overview-dot overview-dot--neutral" />{files.length} active file{files.length === 1 ? "" : "s"}</span>
                </>
              ) : (
                <p className="overview-muted-copy">Select a project to see its approval and file metrics.</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="overview-card overview-actions-card">
          <CardHeader className="overview-card-header flex-row"><div><p className="overview-label">Next actions</p><CardTitle>Move the work forward</CardTitle></div><ArrowUpRight className="h-5 w-5 text-muted-foreground" /></CardHeader>
          <CardContent className="overview-actions-list">
            {nextActions.length === 0 ? <p className="overview-no-actions">No urgent action is flagged. Open the workboard to review the full task list.</p> : nextActions.slice(0, 4).map((action) => (
              <button key={action.title} type="button" className="overview-action" onClick={() => onNavigate(action.target)}>
                <span className={`overview-action-marker overview-action-marker--${action.tone}`} />
                <span><strong>{action.title}</strong><small>{action.detail}</small></span>
                <ArrowUpRight className="h-4 w-4" />
              </button>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="overview-focus-grid">
        <Card className="overview-card overview-workflow-card">
          <CardHeader className="overview-card-header flex-row">
            <div><p className="overview-label">Production work</p><CardTitle>Project delivery path</CardTitle><CardDescription>Current task status in {project?.title || "the selected project"}.</CardDescription></div>
            <Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("workboard")} disabled={!project}>Open workboard <ArrowUpRight className="ml-1 h-4 w-4" /></Button>
          </CardHeader>
          <CardContent>
            {workItemsLoading ? <p role="status" className="overview-muted-copy">Loading project tasks…</p> : !project ? <div className="overview-empty"><ListChecks className="h-5 w-5" /><span>Select a project to see its delivery tasks.</span></div> : workItems.length === 0 ? <div className="overview-empty"><ListChecks className="h-5 w-5" /><span>No tasks planned yet. Start by turning the brief into clear team handoffs.</span><Button type="button" variant="outline" size="sm" onClick={() => onNavigate("workboard")}>Plan the work</Button></div> : <div className="overview-task-status-grid" role="list" aria-label="Project tasks by status">
              {workStatusSummary.map((entry) => <div key={entry.status} className="overview-task-status" role="listitem">
                <span className={`overview-task-status-dot overview-task-status-dot--${entry.status}`} aria-hidden="true" />
                <span><strong>{entry.label}</strong><small>{entry.detail}</small></span>
                <b>{entry.count}</b>
              </div>)}
            </div>}
          </CardContent>
        </Card>

        <Card className="overview-card overview-approval-card">
          <CardHeader className="overview-card-header flex-row"><div><p className="overview-label">Approval queue</p><CardTitle>{pendingApprovals.length} waiting for review</CardTitle></div><Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("workflows")} disabled={!project}>View all <ArrowUpRight className="ml-1 h-4 w-4" /></Button></CardHeader>
          <CardContent className="overview-list">
            {pendingApprovals.length === 0 ? <div className="overview-empty"><ShieldCheck className="h-5 w-5" /><span>No approval decisions are waiting.</span></div> : pendingApprovals.slice(0, 3).map((approval) => {
              const workflow = workflows.find((item) => item.id === approval.workflow_id)
              return <button key={approval.id} type="button" className="overview-list-row" onClick={() => onNavigate("workflows")}><span className="overview-row-icon"><FileText className="h-4 w-4" /></span><span><strong>{workflow?.name || "Workflow approval"}</strong><small>Requested {formatDate(approval.requested_at)}</small></span><span className={statusTone(approval.status)}>{statusLabel(approval.status)}</span></button>
            })}
          </CardContent>
        </Card>
      </div>

      <div className="overview-bottom-grid">
        <Card className="overview-card overview-activity-card">
          <CardHeader className="overview-card-header flex-row"><div><p className="overview-label">Recent activity</p><CardTitle>What changed lately</CardTitle></div><Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("setup")}>View register <ArrowUpRight className="ml-1 h-4 w-4" /></Button></CardHeader>
          <CardContent className="overview-list">
            {activity.length === 0 ? <div className="overview-empty"><CircleAlert className="h-5 w-5" /><span>Select a project to populate activity.</span></div> : activity.slice(0, 4).map((item) => <div key={item.title} className="overview-list-row overview-list-row--static"><span className="overview-row-icon">{item.icon}</span><span><strong>{item.title}</strong><small>{item.detail}</small></span><time>{item.date}</time></div>)}
          </CardContent>
        </Card>

        <Card className="overview-card">
          <CardHeader className="overview-card-header flex-row"><div><p className="overview-label">Files</p><CardTitle>Project inventory</CardTitle></div><Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("files")}>View all <ArrowUpRight className="ml-1 h-4 w-4" /></Button></CardHeader>
          <CardContent className="overview-list">
            {files.length === 0 ? <div className="overview-empty"><FileText className="h-5 w-5" /><span>No active files indexed yet.</span></div> : files.slice(0, 4).map((file) => <button key={file.id} type="button" className="overview-list-row" onClick={() => onNavigate("files")}><span className="overview-row-icon">{fileIcon(file.extension)}</span><span><strong>{file.name}</strong><small>{formatBytes(file.size_bytes)} · {statusLabel(file.status)}</small></span><ArrowUpRight className="h-4 w-4" /></button>)}
          </CardContent>
        </Card>

        <Card className="overview-card">
          <CardHeader className="overview-card-header flex-row"><div><p className="overview-label">Research</p><CardTitle>Evidence readiness</CardTitle></div><Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("research")}>View all <ArrowUpRight className="ml-1 h-4 w-4" /></Button></CardHeader>
          <CardContent className="overview-list">
            <div className="overview-research-summary"><span className={statusTone(evidenceStatus)}>{evidenceLabel}</span><strong>{researchReview ? `${researchReview.verified_count}/${researchReview.claim_count}` : researchClaims.length} <small>claims ready</small></strong></div>
            {researchReview?.warnings.slice(0, 2).map((warning) => <div key={warning.code} className="overview-warning"><CircleAlert className="h-4 w-4" /><span>{warning.message}</span></div>)}
            {!researchReview?.warnings.length && <p className="overview-muted-copy">Claims, scope, and source passages stay together for review.</p>}
          </CardContent>
        </Card>

        <Card className="overview-card">
          <CardHeader className="overview-card-header flex-row"><div><p className="overview-label">Knowledge</p><CardTitle>Approved sources</CardTitle></div><Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("knowledge")}>View all <ArrowUpRight className="ml-1 h-4 w-4" /></Button></CardHeader>
          <CardContent className="overview-list">
            {knowledgeSources.length === 0 ? <div className="overview-empty"><BookOpen className="h-5 w-5" /><span>No sources registered for this project.</span></div> : knowledgeSources.slice(0, 4).map((source) => <button key={source.id} type="button" className="overview-list-row" onClick={() => onNavigate("knowledge")}><span className="overview-row-icon"><BookOpen className="h-4 w-4 text-indigo-600" /></span><span><strong>{source.title}</strong><small>{statusLabel(source.approval_status)} · {source.file_name}</small></span><span className={statusTone(source.approval_status)}>{statusLabel(source.approval_status)}</span></button>)}
          </CardContent>
        </Card>
      </div>
    </section>
  )
}
