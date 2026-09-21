import type { FormEvent } from "react"
import { Check, GitBranch, Plus, RefreshCw, Send, X } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { Approval, ApprovalDecision, Project, Workflow } from "@/lib/api"

type WorkflowApprovals = Record<string, Approval[]>

type WorkflowOrchestratorProps = {
  project: Project | null
  workflows: Workflow[]
  approvals: WorkflowApprovals
  loading: boolean
  error: string
  decisionCodes: Record<string, string>
  onCreateWorkflow: (event: FormEvent<HTMLFormElement>) => void
  onRefresh: () => void
  onRequestApproval: (workflowId: string) => void
  onDecision: (approvalId: string, decision: ApprovalDecision) => void
  onDecisionCodeChange: (approvalId: string, value: string) => void
}

function statusLabel(status: string): string {
  return status.replaceAll("_", " ")
}

function statusTone(status: string): string {
  if (status === "approved") return "bg-emerald-100 text-emerald-800"
  if (status === "rejected") return "bg-rose-100 text-rose-800"
  if (status === "cancelled") return "bg-slate-100 text-slate-700"
  if (status === "pending") return "bg-amber-100 text-amber-800"
  return "bg-teal-100 text-teal-800"
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Date unavailable"
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date)
}

export function WorkflowOrchestrator({
  project,
  workflows,
  approvals,
  loading,
  error,
  decisionCodes,
  onCreateWorkflow,
  onRefresh,
  onRequestApproval,
  onDecision,
  onDecisionCodeChange,
}: WorkflowOrchestratorProps) {
  const approvalList = workflows.flatMap((workflow) => approvals[workflow.id] || [])
  const pendingCount = approvalList.filter((approval) => approval.status === "pending").length
  const decidedCount = approvalList.filter((approval) => approval.status !== "pending").length
  const definitionComplete = workflows.length > 0
  const requestComplete = approvalList.length > 0
  const decisionComplete = decidedCount > 0

  return (
    <Card id="workflow-orchestrator" className="workspace-card major-panel">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <p className="panel-label">Control plane</p>
          <CardTitle className="flex items-center gap-1.5">
            <GitBranch className="h-4 w-4 text-primary" />Workflow orchestrator
          </CardTitle>
          <CardDescription className="text-xs">
            Define a project workflow, request a decision, and keep the approval trail attached to the active project.
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="hidden border-teal-200 bg-teal-50 text-teal-800 sm:inline-flex">Project scoped</Badge>
          <Button id="workflow-refresh" type="button" variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {!project ? (
          <Alert id="workflow-empty-project">
            <GitBranch className="h-4 w-4" />
            <AlertDescription className="text-xs">Select a project before defining a workflow or requesting an approval.</AlertDescription>
          </Alert>
        ) : (
          <>
            <section id="workflow-state-rail" className="rounded-2xl border border-teal-200 bg-[linear-gradient(120deg,#effaf7_0%,#f8fbfa_55%,#fff8ee_100%)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-teal-800">Active project</p>
                  <p className="mt-1 text-base font-semibold tracking-tight">{project.title}</p>
                  <p className="mt-1 font-mono text-[0.68rem] text-muted-foreground">{project.id}</p>
                </div>
                <span className="rounded-full border border-white/80 bg-white/75 px-2.5 py-1 text-[0.68rem] font-semibold text-slate-700">{project.storage_slug}</span>
              </div>
              <ol className="mt-5 grid gap-2 sm:grid-cols-3" aria-label="Workflow lifecycle">
                {[
                  { label: "Define", detail: "Draft a version", complete: definitionComplete },
                  { label: "Request", detail: pendingCount ? `${pendingCount} awaiting decision` : "Send for approval", complete: requestComplete },
                  { label: "Decide", detail: decidedCount ? "Outcome recorded" : "Await reviewer action", complete: decisionComplete },
                ].map((stage, index) => (
                  <li key={stage.label} data-workflow-stage={stage.label.toLowerCase()} className="relative rounded-xl border border-white/80 bg-white/70 p-3">
                    <div className="flex items-center gap-2">
                      <span className={`grid h-6 w-6 place-items-center rounded-full text-xs font-bold ${stage.complete ? "bg-teal-700 text-white" : "bg-slate-200 text-slate-600"}`}>
                        {stage.complete ? <Check className="h-3.5 w-3.5" /> : index + 1}
                      </span>
                      <span className="text-sm font-semibold">{stage.label}</span>
                    </div>
                    <p className="mt-2 text-[0.68rem] text-muted-foreground">{stage.detail}</p>
                  </li>
                ))}
              </ol>
              <div className="mt-4 grid grid-cols-3 gap-2 border-t border-teal-900/10 pt-3 text-center">
                <div><strong className="block text-lg tracking-tight">{workflows.length}</strong><span className="text-[0.65rem] text-muted-foreground">workflow{workflows.length === 1 ? "" : "s"}</span></div>
                <div><strong className="block text-lg tracking-tight">{pendingCount}</strong><span className="text-[0.65rem] text-muted-foreground">pending</span></div>
                <div><strong className="block text-lg tracking-tight">{decidedCount}</strong><span className="text-[0.65rem] text-muted-foreground">decided</span></div>
              </div>
            </section>

            {error && <Alert id="workflow-error" className="border-rose-200 bg-rose-50 text-rose-900"><X className="h-4 w-4" /><AlertDescription className="text-xs">{error}</AlertDescription></Alert>}

            <div className="grid gap-5 xl:grid-cols-[minmax(0,0.78fr)_minmax(0,1.22fr)]">
              <Card id="workflow-create-card" className="border-border bg-card/70">
                <CardHeader className="pb-3">
                  <p className="panel-label">New definition</p>
                  <CardTitle className="text-base">Create a workflow</CardTitle>
                  <CardDescription className="text-xs">Start with a named, versioned definition. Approval requests are created separately so the draft stays editable.</CardDescription>
                </CardHeader>
                <CardContent>
                  <form id="workflow-create-form" onSubmit={onCreateWorkflow} className="grid gap-3">
                    <div className="grid gap-1.5">
                      <Label htmlFor="workflow-name" className="text-xs">Workflow name</Label>
                      <Input id="workflow-name" name="name" placeholder="e.g. Publish campaign package" maxLength={100} required />
                    </div>
                    <div className="grid gap-1.5">
                      <Label htmlFor="workflow-version" className="text-xs">Version</Label>
                      <Input id="workflow-version" name="version" type="number" min="1" defaultValue="1" required />
                      <p className="text-[0.68rem] text-muted-foreground">Use a new version when the definition changes materially.</p>
                    </div>
                    <Button id="workflow-submit" type="submit" disabled={loading}>
                      <Plus className="mr-1.5 h-4 w-4" />{loading ? "Saving workflow…" : "Create workflow"}
                    </Button>
                  </form>
                </CardContent>
              </Card>

              <section id="workflow-list" aria-live="polite" className="space-y-3">
                <div className="flex items-end justify-between gap-3">
                  <div>
                    <p className="panel-label">Project register</p>
                    <h3 className="text-base font-semibold tracking-tight">Workflow definitions and approvals</h3>
                  </div>
                  <span className="text-[0.68rem] text-muted-foreground">{approvalList.length} approval record{approvalList.length === 1 ? "" : "s"}</span>
                </div>
                {loading && workflows.length === 0 ? <div className="rounded-xl border border-dashed p-5 text-sm text-muted-foreground">Loading project workflows…</div> : workflows.length === 0 ? (
                  <div id="workflow-list-empty" className="rounded-xl border border-dashed border-teal-200 bg-teal-50/40 p-5">
                    <p className="text-sm font-semibold">No workflow definitions yet</p>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">Create the first definition on the left. The approval trail will appear here without leaving this project.</p>
                  </div>
                ) : workflows.map((workflow) => {
                  const workflowApprovals = approvals[workflow.id] || []
                  const hasPendingApproval = workflowApprovals.some((approval) => approval.status === "pending")
                  return (
                    <Card key={workflow.id} data-workflow-id={workflow.id} className="border-border bg-card/70 shadow-sm">
                      <CardHeader className="gap-2 pb-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="panel-label">Version {workflow.version}</p>
                            <CardTitle className="text-base">{workflow.name}</CardTitle>
                          </div>
                          <Badge data-workflow-status={workflow.status} className={statusTone(workflow.status)}>{statusLabel(workflow.status)}</Badge>
                        </div>
                        <CardDescription className="text-xs">Created {formatDate(workflow.created_at)} · Definition ID <span className="font-mono">{workflow.id.slice(0, 12)}…</span></CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-3 pt-0">
                        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-muted/30 p-3">
                          <div>
                            <p className="text-xs font-semibold">Approval gate</p>
                            <p className="mt-1 text-[0.68rem] text-muted-foreground">{hasPendingApproval ? "A reviewer decision is pending." : workflowApprovals.length ? "The latest decision is recorded." : "No decision has been requested."}</p>
                          </div>
                          <Button id={`workflow-request-approval-${workflow.id}`} type="button" size="sm" variant={hasPendingApproval ? "outline" : "secondary"} onClick={() => onRequestApproval(workflow.id)} disabled={loading || hasPendingApproval}>
                            <Send className="mr-1.5 h-3.5 w-3.5" />{hasPendingApproval ? "Awaiting decision" : "Request approval"}
                          </Button>
                        </div>

                        {workflowApprovals.length > 0 && <div className="space-y-2" data-approval-list={workflow.id}>
                          <p className="text-[0.68rem] font-bold uppercase tracking-[0.16em] text-muted-foreground">Approval trail</p>
                          {workflowApprovals.map((approval) => (
                            <div key={approval.id} data-approval-id={approval.id} className="rounded-xl border border-border bg-background/80 p-3">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                  <Badge data-approval-status={approval.status} className={statusTone(approval.status)}>{statusLabel(approval.status)}</Badge>
                                  <span className="text-[0.68rem] text-muted-foreground">Requested {formatDate(approval.requested_at)}</span>
                                </div>
                                {approval.decision_code && <span className="rounded-md bg-muted px-2 py-1 font-mono text-[0.62rem] text-muted-foreground">{approval.decision_code}</span>}
                              </div>
                              {approval.status === "pending" && <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto_auto_auto] sm:items-end">
                                <div className="grid gap-1.5">
                                  <Label htmlFor={`approval-code-${approval.id}`} className="text-[0.68rem]">Decision code <span className="font-normal text-muted-foreground">(optional)</span></Label>
                                  <Input id={`approval-code-${approval.id}`} value={decisionCodes[approval.id] || ""} onChange={(event) => onDecisionCodeChange(approval.id, event.target.value)} placeholder="e.g. checked" maxLength={64} />
                                </div>
                                <Button id={`approval-approve-${approval.id}`} type="button" size="sm" onClick={() => onDecision(approval.id, "approved")} disabled={loading}><Check className="mr-1.5 h-3.5 w-3.5" />Approve</Button>
                                <Button id={`approval-reject-${approval.id}`} type="button" size="sm" variant="outline" onClick={() => onDecision(approval.id, "rejected")} disabled={loading}><X className="mr-1.5 h-3.5 w-3.5" />Reject</Button>
                                <Button id={`approval-cancel-${approval.id}`} type="button" size="sm" variant="ghost" onClick={() => onDecision(approval.id, "cancelled")} disabled={loading}>Cancel</Button>
                              </div>}
                            </div>
                          ))}
                        </div>}
                      </CardContent>
                    </Card>
                  )
                })}
              </section>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

