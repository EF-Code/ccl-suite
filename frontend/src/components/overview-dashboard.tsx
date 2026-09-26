import { ArrowUpRight, BookOpen, Check, CircleAlert, Clock3, FileText, FolderOpen, GitBranch, ListChecks, Plus, ShieldCheck } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { Approval, FileRecord, KnowledgeSource, Project, ResearchClaim, ResearchReviewResponse, Workflow } from "@/lib/api"
import type { ReactNode } from "react"

type OverviewTarget = "operations" | "files" | "knowledge" | "research" | "workflows" | "recovery" | "setup"

type OverviewHealth = {
  ok: boolean
  text: string
  detail: string
}

type OverviewDashboardProps = {
  project: Project | null
  projects: Project[]
  health: OverviewHealth
  files: FileRecord[]
  knowledgeSources: KnowledgeSource[]
  researchClaims: ResearchClaim[]
  researchReview: ResearchReviewResponse | null
  workflows: Workflow[]
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
  projects,
  health,
  files,
  knowledgeSources,
  researchClaims,
  researchReview,
  workflows,
  approvals,
  onNavigate,
}: OverviewDashboardProps) {
  const approvalList = workflows.flatMap((workflow) => approvals[workflow.id] || [])
  const pendingApprovals = approvalList.filter((approval) => approval.status === "pending")
  const decidedApprovals = approvalList.filter((approval) => approval.status !== "pending")
  const currentWorkflow = workflows[0]
  const projectReady = Boolean(project)
  const evidenceStatus = researchReview?.status || (researchClaims.length ? "needs_review" : "not_started")
  const evidenceLabel = researchReview ? statusLabel(researchReview.status) : researchClaims.length ? "Preview ready" : "Not started"

  const stageData = [
    { label: "Define", detail: currentWorkflow ? `Version ${currentWorkflow.version} drafted` : "Create a workflow", complete: workflows.length > 0 },
    { label: "Request", detail: approvalList.length ? `${approvalList.length} approval record${approvalList.length === 1 ? "" : "s"}` : "Send for review", complete: approvalList.length > 0 },
    { label: "Decide", detail: decidedApprovals.length ? "Outcome recorded" : "Await reviewer action", complete: decidedApprovals.length > 0 },
  ]

  const nextActions = !project
    ? [{ title: "Create your first project", detail: "Set up the workspace before starting controlled work.", label: "Open setup", target: "setup" as const, tone: "attention" }]
    : [
        workflows.length === 0 ? { title: "Define a workflow", detail: "Give the project its first versioned control path.", label: "Open workflows", target: "workflows" as const, tone: "good" } : null,
        pendingApprovals.length > 0 ? { title: "Review pending approval", detail: `${pendingApprovals.length} decision${pendingApprovals.length === 1 ? "" : "s"} waiting for an operator.`, label: "Open approvals", target: "workflows" as const, tone: "attention" } : null,
        files.length === 0 ? { title: "Prepare project files", detail: "Generate storage and scan the active project folder.", label: "Open operations", target: "operations" as const, tone: "neutral" } : null,
        evidenceStatus !== "approved" ? { title: "Review evidence package", detail: "Check source-backed claims before publication.", label: "Open research", target: "research" as const, tone: "neutral" } : null,
        { title: "Inspect the project register", detail: `${projects.length} project${projects.length === 1 ? "" : "s"} available in this workspace.`, label: "View projects", target: "setup" as const, tone: "neutral" },
      ].filter(Boolean).slice(0, 4) as Array<{ title: string; detail: string; label: string; target: OverviewTarget; tone: string }>

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
          <p>One clear view of work, evidence, approvals, and the next decision.</p>
        </div>
        <div className="overview-heading-actions">
          <Button type="button" variant="outline" onClick={() => onNavigate("workflows")} disabled={!project}>
            <GitBranch className="mr-1.5 h-4 w-4" />View workflow
          </Button>
          <Button type="button" onClick={() => onNavigate("setup")}>
            <Plus className="mr-1.5 h-4 w-4" />New project
          </Button>
        </div>
      </div>

      <div className="overview-top-grid">
        <Card className="overview-card overview-project-card">
          <CardHeader className="overview-card-header">
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
            <span><ListChecks className="h-4 w-4" />{workflows.length} workflow{workflows.length === 1 ? "" : "s"}</span>
            <span><Clock3 className="h-4 w-4" />Updated {formatDate(project?.updated_at)}</span>
            <span className={projectReady ? "overview-status overview-status--good" : "overview-status overview-status--attention"}>{projectReady ? "Ready" : "Setup required"}</span>
          </CardContent>
        </Card>

        <Card className="overview-card overview-health-card">
          <CardHeader className="overview-card-header">
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
                  <span><i className="overview-dot overview-dot--neutral" />{files.length} active file{files.length === 1 ? "" : "s"}</span>
                </>
              ) : (
                <p className="overview-muted-copy">Select a project to see its approval and file metrics.</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="overview-card overview-actions-card">
          <CardHeader className="overview-card-header"><div><p className="overview-label">Next actions</p><CardTitle>Move the work forward</CardTitle></div><ArrowUpRight className="h-5 w-5 text-muted-foreground" /></CardHeader>
          <CardContent className="overview-actions-list">
            {nextActions.map((action) => (
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
          <CardHeader className="overview-card-header">
            <div><p className="overview-label">Workflow control</p><CardTitle>Project delivery path</CardTitle><CardDescription>{currentWorkflow?.name || "Create a workflow to give this project a visible path from definition to decision."}</CardDescription></div>
            <Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("workflows")} disabled={!project}>View workflow <ArrowUpRight className="ml-1 h-4 w-4" /></Button>
          </CardHeader>
          <CardContent>
            <ol className="overview-stage-rail" aria-label="Workflow progress">
              {stageData.map((stage, index) => (
                <li key={stage.label} className={`overview-stage ${stage.complete ? "is-complete" : index === stageData.findIndex((item) => !item.complete) ? "is-current" : ""}`}>
                  <span className="overview-stage-marker">{stage.complete ? <Check className="h-4 w-4" /> : index + 1}</span>
                  <span><strong>{stage.label}</strong><small>{stage.detail}</small></span>
                </li>
              ))}
            </ol>
            <div className="overview-progress-block">
              <div><span>Stage progress</span><strong>{decidedApprovals.length ? "3 of 3" : approvalList.length ? "2 of 3" : workflows.length ? "1 of 3" : "0 of 3"}</strong></div>
              <div className="overview-progress-track"><span style={{ width: `${decidedApprovals.length ? 100 : approvalList.length ? 66 : workflows.length ? 33 : 0}%` }} /></div>
            </div>
          </CardContent>
        </Card>

        <Card className="overview-card overview-approval-card">
          <CardHeader className="overview-card-header"><div><p className="overview-label">Approval queue</p><CardTitle>{pendingApprovals.length} waiting for review</CardTitle></div><Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("workflows")} disabled={!project}>View all <ArrowUpRight className="ml-1 h-4 w-4" /></Button></CardHeader>
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
          <CardHeader className="overview-card-header"><div><p className="overview-label">Recent activity</p><CardTitle>What changed lately</CardTitle></div><Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("setup")}>View register <ArrowUpRight className="ml-1 h-4 w-4" /></Button></CardHeader>
          <CardContent className="overview-list">
            {activity.length === 0 ? <div className="overview-empty"><CircleAlert className="h-5 w-5" /><span>Select a project to populate activity.</span></div> : activity.slice(0, 4).map((item) => <div key={item.title} className="overview-list-row overview-list-row--static"><span className="overview-row-icon">{item.icon}</span><span><strong>{item.title}</strong><small>{item.detail}</small></span><time>{item.date}</time></div>)}
          </CardContent>
        </Card>

        <Card className="overview-card">
          <CardHeader className="overview-card-header"><div><p className="overview-label">Files</p><CardTitle>Project inventory</CardTitle></div><Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("files")}>View all <ArrowUpRight className="ml-1 h-4 w-4" /></Button></CardHeader>
          <CardContent className="overview-list">
            {files.length === 0 ? <div className="overview-empty"><FileText className="h-5 w-5" /><span>No active files indexed yet.</span></div> : files.slice(0, 4).map((file) => <button key={file.id} type="button" className="overview-list-row" onClick={() => onNavigate("files")}><span className="overview-row-icon">{fileIcon(file.extension)}</span><span><strong>{file.name}</strong><small>{formatBytes(file.size_bytes)} · {statusLabel(file.status)}</small></span><ArrowUpRight className="h-4 w-4" /></button>)}
          </CardContent>
        </Card>

        <Card className="overview-card">
          <CardHeader className="overview-card-header"><div><p className="overview-label">Research</p><CardTitle>Evidence readiness</CardTitle></div><Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("research")}>View all <ArrowUpRight className="ml-1 h-4 w-4" /></Button></CardHeader>
          <CardContent className="overview-list">
            <div className="overview-research-summary"><span className={statusTone(evidenceStatus)}>{evidenceLabel}</span><strong>{researchReview ? `${researchReview.verified_count}/${researchReview.claim_count}` : researchClaims.length} <small>claims ready</small></strong></div>
            {researchReview?.warnings.slice(0, 2).map((warning) => <div key={warning.code} className="overview-warning"><CircleAlert className="h-4 w-4" /><span>{warning.message}</span></div>)}
            {!researchReview?.warnings.length && <p className="overview-muted-copy">Claims, scope, and source passages stay together for review.</p>}
          </CardContent>
        </Card>

        <Card className="overview-card">
          <CardHeader className="overview-card-header"><div><p className="overview-label">Knowledge</p><CardTitle>Approved sources</CardTitle></div><Button type="button" variant="link" className="overview-link" onClick={() => onNavigate("knowledge")}>View all <ArrowUpRight className="ml-1 h-4 w-4" /></Button></CardHeader>
          <CardContent className="overview-list">
            {knowledgeSources.length === 0 ? <div className="overview-empty"><BookOpen className="h-5 w-5" /><span>No sources registered for this project.</span></div> : knowledgeSources.slice(0, 4).map((source) => <button key={source.id} type="button" className="overview-list-row" onClick={() => onNavigate("knowledge")}><span className="overview-row-icon"><BookOpen className="h-4 w-4 text-indigo-600" /></span><span><strong>{source.title}</strong><small>{statusLabel(source.approval_status)} · {source.file_name}</small></span><span className={statusTone(source.approval_status)}>{statusLabel(source.approval_status)}</span></button>)}
          </CardContent>
        </Card>
      </div>
    </section>
  )
}
