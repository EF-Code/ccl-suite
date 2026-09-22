import { useState, type FormEvent } from "react"
import { BookOpen, Bot, Check, Database, FileText, GitBranch, History, LockKeyhole, Plus, RefreshCw, Send, ShieldCheck, Wrench, X } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { AgentActorName, AgentDefinition, AgentHandoff, AgentName, Approval, ApprovalDecision, Project, Workflow, WorkflowAction, WorkflowToolName, WorkflowToolRun } from "@/lib/api"

type WorkflowApprovals = Record<string, Approval[]>

type WorkflowOrchestratorProps = {
  project: Project | null
  workflows: Workflow[]
  approvals: WorkflowApprovals
  toolRuns: Record<string, WorkflowToolRun[]>
  actions: Record<string, WorkflowAction[]>
  agentDefinitions: AgentDefinition[]
  agentHandoffs: Record<string, AgentHandoff[]>
  loading: boolean
  error: string
  decisionCodes: Record<string, string>
  onCreateWorkflow: (event: FormEvent<HTMLFormElement>) => void
  onRefresh: () => void
  onRequestApproval: (workflowId: string) => void
  onDecision: (approvalId: string, decision: ApprovalDecision) => void
  onTransition: (workflowId: string, state: Workflow["state"]) => void
  onRunTool: (workflowId: string, tool: WorkflowToolName, query?: string) => void
  onDelegate: (workflowId: string, targetAgent: AgentName) => void
  onRequestAction: (workflowId: string, actionCode: WorkflowAction["action_code"]) => void
  onExecuteAction: (actionId: string) => void
  onDecisionCodeChange: (approvalId: string, value: string) => void
}

function statusLabel(status: string): string {
  return status.replaceAll("_", " ")
}

function statusTone(status: string): string {
  if (status === "approved") return "bg-emerald-100 text-emerald-800"
  if (status === "executed") return "bg-emerald-100 text-emerald-800"
  if (status === "rejected") return "bg-rose-100 text-rose-800"
  if (status === "blocked" || status === "failed") return "bg-rose-100 text-rose-800"
  if (status === "cancelled") return "bg-slate-100 text-slate-700"
  if (status === "pending" || status === "pending_approval") return "bg-amber-100 text-amber-800"
  return "bg-teal-100 text-teal-800"
}

function toolLabel(tool: WorkflowToolName): string {
  if (tool === "files.summary") return "File inventory"
  if (tool === "knowledge.search") return "Knowledge search"
  return "Research summary"
}

function actionLabel(action: WorkflowAction["action_code"]): string {
  return `${action.charAt(0).toUpperCase()}${action.slice(1)}`
}

function agentLabel(agent: AgentActorName): string {
  return agent.replaceAll("_", " ")
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
  toolRuns,
  actions,
  agentDefinitions,
  agentHandoffs,
  loading,
  error,
  decisionCodes,
  onCreateWorkflow,
  onRefresh,
  onRequestApproval,
  onDecision,
  onTransition,
  onRunTool,
  onDelegate,
  onRequestAction,
  onExecuteAction,
  onDecisionCodeChange,
}: WorkflowOrchestratorProps) {
  const [toolQuery, setToolQuery] = useState("")
  const approvalList = workflows.flatMap((workflow) => approvals[workflow.id] || [])
  const pendingCount = approvalList.filter((approval) => approval.status === "pending").length
  const decidedCount = approvalList.filter((approval) => approval.status !== "pending").length
  const definitionComplete = workflows.length > 0
  const requestComplete = approvalList.length > 0
  const decisionComplete = decidedCount > 0
  const currentWorkflow = workflows[workflows.length - 1] || null
  const nextStates: Record<Workflow["state"], Workflow["state"][]> = {
    ready: ["in_progress", "review"],
    in_progress: ["review"],
    review: ["changes_required"],
    changes_required: ["in_progress", "review"],
    approved: ["archived"],
    archived: [],
  }
  const currentToolRuns = currentWorkflow ? toolRuns[currentWorkflow.id] || [] : []
  const currentActions = currentWorkflow ? actions[currentWorkflow.id] || [] : []
  const currentHandoffs = currentWorkflow ? agentHandoffs[currentWorkflow.id] || [] : []

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
              {currentWorkflow && <div id="workflow-state-controls" className="mt-4 flex flex-wrap items-center gap-2 border-t border-teal-900/10 pt-3">
                <span className="text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Current state</span>
                <Badge variant="outline" data-workflow-state={currentWorkflow.state} className="capitalize">{currentWorkflow.state.replaceAll("_", " ")}</Badge>
                {nextStates[currentWorkflow.state].map((state) => <Button key={state} type="button" size="sm" variant="outline" onClick={() => onTransition(currentWorkflow.id, state)} disabled={loading}>
                  Move to {state.replaceAll("_", " ")}
                </Button>)}
                <span className="text-[0.68rem] text-muted-foreground">Approved and archived states require the approval gate.</span>
              </div>}
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

            {currentWorkflow && <div className="grid gap-5 xl:grid-cols-2">
              <Card id="workflow-agents-card" className="border-border bg-card/70 xl:col-span-2">
                <CardHeader className="gap-2 pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="panel-label">Specialist network</p>
                      <CardTitle className="flex items-center gap-1.5 text-base"><Bot className="h-4 w-4 text-primary" />Guarded agent handoffs</CardTitle>
                    </div>
                    <Badge variant="outline" className="border-indigo-200 bg-indigo-50 text-indigo-800"><LockKeyhole className="mr-1 h-3 w-3" />Allow-listed</Badge>
                  </div>
                  <CardDescription className="text-xs">Delegate bounded project checks to one specialist at a time. Each role has a fixed responsibility, least-privilege tools, and a traceable handoff.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {agentDefinitions.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-indigo-200 bg-indigo-50/30 p-4 text-xs text-muted-foreground">Loading the responsibility matrix…</div>
                  ) : (
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      {agentDefinitions.map((definition) => (
                        <div key={definition.agent} data-agent-definition={definition.agent} className="flex flex-col rounded-xl border border-border bg-background/80 p-3">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <p className="text-sm font-semibold">{definition.label}</p>
                              <p className="mt-1 text-[0.68rem] leading-relaxed text-muted-foreground">{definition.responsibility}</p>
                            </div>
                            <span className="rounded-md bg-indigo-50 px-1.5 py-1 font-mono text-[0.58rem] text-indigo-800">{definition.agent}</span>
                          </div>
                          <div className="mt-3 flex-1 border-t border-border pt-3">
                            <p className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted-foreground">Permitted tools</p>
                            <p className="mt-1 min-h-8 text-[0.68rem] text-foreground">{definition.allowed_tools.length ? definition.allowed_tools.join(" · ") : "No direct tools"}</p>
                          </div>
                          <Button id={`workflow-agent-${definition.agent}`} type="button" size="sm" variant="outline" className="mt-3" onClick={() => onDelegate(currentWorkflow.id, definition.agent)} disabled={loading}>
                            <Bot className="mr-1.5 h-3.5 w-3.5" />Run specialist
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                  <div id="workflow-agent-handoffs" className="space-y-2" aria-live="polite">
                    <div className="flex items-center justify-between gap-2 border-t border-border pt-3">
                      <p className="text-[0.68rem] font-bold uppercase tracking-[0.16em] text-muted-foreground">Handoff traces</p>
                      <span className="text-[0.68rem] text-muted-foreground">{currentHandoffs.length} run{currentHandoffs.length === 1 ? "" : "s"}</span>
                    </div>
                    {currentHandoffs.length === 0 ? <div className="rounded-xl border border-dashed border-indigo-200 bg-indigo-50/30 p-3 text-xs text-muted-foreground">No specialist handoffs yet. Run a role above to attach a structured result to this workflow.</div> : currentHandoffs.slice(0, 6).map((handoff) => (
                      <div key={handoff.id} data-agent-handoff-id={handoff.id} data-agent-status={handoff.status} className="rounded-xl border border-border bg-background/80 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2"><Badge className={statusTone(handoff.status)}>{statusLabel(handoff.status)}</Badge><span className="text-xs font-semibold">{agentLabel(handoff.target_agent)} specialist</span></div>
                          <span className="font-mono text-[0.62rem] text-muted-foreground" title={handoff.trace_id}>trace:{handoff.trace_id.slice(0, 10)}</span>
                        </div>
                        <p data-agent-route className="mt-1 text-[0.65rem] font-medium capitalize text-indigo-700">{agentLabel(handoff.source_agent)} → {agentLabel(handoff.target_agent)}</p>
                        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{handoff.output_summary || "No summary returned."}</p>
                        {handoff.blocked_reason && <p className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-2 text-[0.68rem] text-rose-900">Guardrail: {handoff.blocked_reason}</p>}
                        <div className="mt-2 flex items-center gap-2 text-[0.65rem] text-muted-foreground"><History className="h-3 w-3" />{formatDate(handoff.created_at)} · input fingerprinted</div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card id="workflow-tools-card" className="border-border bg-card/70">
                <CardHeader className="gap-2 pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="panel-label">Connected services</p>
                      <CardTitle className="flex items-center gap-1.5 text-base"><Wrench className="h-4 w-4 text-primary" />Read-only workflow tools</CardTitle>
                    </div>
                    <Badge variant="outline" className="border-teal-200 bg-teal-50 text-teal-800">Max 3 attempts</Badge>
                  </div>
                  <CardDescription className="text-xs">Run project-scoped file, knowledge, and research lookups. Each request leaves a trace without performing a write.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-2 sm:grid-cols-3">
                    <Button id="workflow-tool-files" type="button" variant="outline" size="sm" onClick={() => onRunTool(currentWorkflow.id, "files.summary")} disabled={loading}>
                      <FileText className="mr-1.5 h-3.5 w-3.5" />Files
                    </Button>
                    <Button id="workflow-tool-research" type="button" variant="outline" size="sm" onClick={() => onRunTool(currentWorkflow.id, "research.summary")} disabled={loading}>
                      <Database className="mr-1.5 h-3.5 w-3.5" />Research
                    </Button>
                    <Button id="workflow-tool-knowledge" type="button" variant="outline" size="sm" onClick={() => { onRunTool(currentWorkflow.id, "knowledge.search", toolQuery.trim()); setToolQuery("") }} disabled={loading || !toolQuery.trim()}>
                      <BookOpen className="mr-1.5 h-3.5 w-3.5" />Search knowledge
                    </Button>
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="workflow-tool-query" className="text-xs">Knowledge query</Label>
                    <Textarea id="workflow-tool-query" value={toolQuery} onChange={(event) => setToolQuery(event.target.value)} rows={2} maxLength={500} placeholder="Ask only about approved project sources…" />
                    <p className="text-[0.68rem] text-muted-foreground">Knowledge search stays bounded to approved sources and records only a safe result summary.</p>
                  </div>
                  <div id="workflow-tool-runs" className="space-y-2" aria-live="polite">
                    <div className="flex items-center justify-between gap-2 border-t border-border pt-3">
                      <p className="text-[0.68rem] font-bold uppercase tracking-[0.16em] text-muted-foreground">Recent traces</p>
                      <span className="text-[0.68rem] text-muted-foreground">{currentToolRuns.length} run{currentToolRuns.length === 1 ? "" : "s"}</span>
                    </div>
                    {currentToolRuns.length === 0 ? <div className="rounded-xl border border-dashed border-teal-200 bg-teal-50/30 p-3 text-xs text-muted-foreground">No tool calls yet. Run a read-only lookup to attach its trace to this workflow.</div> : currentToolRuns.slice(0, 5).map((run) => (
                      <div key={run.id} data-tool-run-id={run.id} className="rounded-xl border border-border bg-background/80 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2"><Badge data-tool-status={run.status} className={statusTone(run.status)}>{statusLabel(run.status)}</Badge><span className="text-xs font-semibold">{toolLabel(run.tool_name)}</span></div>
                          <span className="font-mono text-[0.62rem] text-muted-foreground" title={run.trace_id}>trace:{run.trace_id.slice(0, 10)}</span>
                        </div>
                        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{run.output_summary || "No summary returned."}</p>
                        <div className="mt-2 flex items-center gap-2 text-[0.65rem] text-muted-foreground"><History className="h-3 w-3" />{run.attempt_count}/{run.max_attempts} attempts · {formatDate(run.created_at)}{run.error_code ? ` · ${run.error_code}` : ""}</div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card id="workflow-actions-card" className="border-border bg-card/70">
                <CardHeader className="gap-2 pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="panel-label">Safety boundary</p>
                      <CardTitle className="flex items-center gap-1.5 text-base"><ShieldCheck className="h-4 w-4 text-primary" />Human approval gate</CardTitle>
                    </div>
                    <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">No auto-execution</Badge>
                  </div>
                  <CardDescription className="text-xs">Sending, deleting, replacing, publishing, archiving, and approving always pause as an explicit action intent.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {(["send", "delete", "replace", "publish", "archive", "approve"] as WorkflowAction["action_code"][]).map((action) => <Button key={action} id={`workflow-action-${action}`} type="button" variant="outline" size="sm" onClick={() => onRequestAction(currentWorkflow.id, action)} disabled={loading}>
                      {actionLabel(action)}
                    </Button>)}
                  </div>
                  <div id="workflow-actions-list" className="space-y-2" aria-live="polite">
                    <div className="flex items-center justify-between gap-2 border-t border-border pt-3">
                      <p className="text-[0.68rem] font-bold uppercase tracking-[0.16em] text-muted-foreground">Action intents</p>
                      <span className="text-[0.68rem] text-muted-foreground">{currentActions.length} record{currentActions.length === 1 ? "" : "s"}</span>
                    </div>
                    {currentActions.length === 0 ? <div className="rounded-xl border border-dashed border-amber-200 bg-amber-50/30 p-3 text-xs text-muted-foreground">No protected action has been requested. The controls above create a reviewable intent instead of acting immediately.</div> : currentActions.slice(0, 5).map((action) => (
                      <div key={action.id} data-workflow-action-id={action.id} data-action-status={action.status} className="rounded-xl border border-border bg-background/80 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2"><Badge className={statusTone(action.status)}>{statusLabel(action.status)}</Badge><span className="text-xs font-semibold">{actionLabel(action.action_code)} action</span></div>
                          <span className="font-mono text-[0.62rem] text-muted-foreground">{action.target_ref}</span>
                        </div>
                        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{action.reason}</p>
                        {action.status === "pending_approval" && <p data-action-approval-id={action.approval_id || undefined} className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-2 text-[0.68rem] text-amber-900">Awaiting reviewer approval. The action cannot execute while it is pending.</p>}
                        {action.status === "approved" && <Button id={`workflow-action-execute-${action.id}`} type="button" size="sm" className="mt-3" onClick={() => onExecuteAction(action.id)} disabled={loading}><Check className="mr-1.5 h-3.5 w-3.5" />Record approved execution</Button>}
                        {action.result_summary && <p className="mt-2 text-[0.68rem] text-muted-foreground">{action.result_summary}</p>}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>}
          </>
        )}
      </CardContent>
    </Card>
  )
}
