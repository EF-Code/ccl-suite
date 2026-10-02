import { useCallback, useEffect, useState, type FormEvent } from "react"
import { Copy, FolderPlus, RefreshCw, Sparkles, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiRequest, type Project, type ProjectTemplate as ProjectTemplateModel } from "@/lib/api"

type ProjectTemplatesProps = {
  project: Project | null;
  canSaveFromProject: boolean;
  onProjectCreated: (project: Project) => Promise<void> | void;
};

export function ProjectTemplates({ project, canSaveFromProject, onProjectCreated }: ProjectTemplatesProps) {
  const [templates, setTemplates] = useState<ProjectTemplateModel[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [templateName, setTemplateName] = useState("")
  const [saving, setSaving] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<ProjectTemplateModel | null>(null)
  const [projectTitle, setProjectTitle] = useState("")
  const [projectDeadline, setProjectDeadline] = useState("")
  const [creationError, setCreationError] = useState("")
  const [creating, setCreating] = useState(false)
  const [deleteCandidate, setDeleteCandidate] = useState<ProjectTemplateModel | null>(null)
  const [deleting, setDeleting] = useState(false)

  const refreshTemplates = useCallback(async (showLoading = false) => {
    if (showLoading) {
      setLoading(true)
      setError("")
    }
    try {
      setTemplates(await apiRequest<ProjectTemplateModel[]>("/project-templates"))
      setError("")
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Project templates could not be loaded.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    apiRequest<ProjectTemplateModel[]>("/project-templates")
      .then((loaded) => { if (active) setTemplates(loaded) })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Project templates could not be loaded.")
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  async function handleSaveTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!project || !templateName.trim() || saving) return
    setSaving(true)
    setError("")
    try {
      const template = await apiRequest<ProjectTemplateModel>(`/projects/${project.id}/templates`, {
        method: "POST",
        body: JSON.stringify({ name: templateName.trim() }),
      })
      setTemplates((current) => [template, ...current.filter((entry) => entry.id !== template.id)])
      setTemplateName("")
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The project template could not be saved.")
    } finally {
      setSaving(false)
    }
  }

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedTemplate || !projectTitle.trim() || creating) return
    setCreating(true)
    setCreationError("")
    try {
      const createdProject = await apiRequest<Project>(`/project-templates/${selectedTemplate.id}/projects`, {
        method: "POST",
        body: JSON.stringify({
          title: projectTitle.trim(),
          deadline: projectDeadline || null,
        }),
      })
      setSelectedTemplate(null)
      setProjectTitle("")
      setProjectDeadline("")
      await onProjectCreated(createdProject)
    } catch (reason) {
      setCreationError(reason instanceof Error ? reason.message : "The project could not be created from this template.")
    } finally {
      setCreating(false)
    }
  }

  async function handleDeleteTemplate() {
    if (!deleteCandidate || deleting) return
    setDeleting(true)
    setError("")
    try {
      await apiRequest<void>(`/project-templates/${deleteCandidate.id}`, { method: "DELETE" })
      setTemplates((current) => current.filter((entry) => entry.id !== deleteCandidate.id))
      setDeleteCandidate(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The project template could not be deleted.")
      setDeleteCandidate(null)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <section className="space-y-5" aria-labelledby="project-templates-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-teal-800">Repeatable delivery</p>
          <h2 id="project-templates-title" className="text-2xl font-semibold tracking-tight text-[#1b2c3b]">Project templates</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">Reuse a proven project brief and task checklist. New projects start with clean, unassigned work.</p>
        </div>
        <Button type="button" variant="outline" onClick={() => void refreshTemplates(true)} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />Refresh templates
        </Button>
      </div>

      <Card className="border-[#dce7e6] bg-[#f7faf9]">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base"><Copy className="h-4 w-4 text-teal-800" aria-hidden="true" />Save a reusable starting point</CardTitle>
          <CardDescription className="text-sm">
            {project ? `Capture ${project.title} and its non-cancelled tasks. Assignees, files, comments, and workflow history are not copied.` : "Choose a project first. Only project managers can save its brief and checklist as a template."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {project && canSaveFromProject ? <form onSubmit={(event) => void handleSaveTemplate(event)} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
            <div className="grid gap-2"><Label htmlFor="new-project-template-name">Template name</Label><Input id="new-project-template-name" value={templateName} onChange={(event) => setTemplateName(event.target.value)} required minLength={1} maxLength={100} placeholder="e.g. Weekly channel production" /></div>
            <Button type="submit" disabled={!templateName.trim() || saving}><Copy className="h-4 w-4" aria-hidden="true" />{saving ? "Saving…" : "Save current project"}</Button>
          </form> : <p className="rounded-lg border border-dashed bg-white px-3 py-3 text-sm text-muted-foreground">{project ? "You need project-manager access to save a template from this project." : "Select a project from the workspace bar, then return here to save its structure."}</p>}
        </CardContent>
      </Card>

      {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      {loading && templates.length === 0 && <p role="status" className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">Loading your templates…</p>}
      {!loading && templates.length === 0 && <Card className="border-dashed"><CardContent className="grid justify-items-center gap-2 py-12 text-center">
        <Sparkles className="h-7 w-7 text-teal-800" aria-hidden="true" />
        <p className="font-medium text-foreground">No reusable templates yet</p>
        <p className="max-w-md text-sm text-muted-foreground">Save a project you run regularly. Its brief and task checklist will be ready the next time you need it.</p>
      </CardContent></Card>}

      {templates.length > 0 && <div className="grid gap-3 xl:grid-cols-2" aria-label="Saved project templates">
        {templates.map((template) => <Card key={template.id} data-project-template-id={template.id} className="overflow-hidden border-[#e2e8ed]">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <CardTitle className="break-words text-base text-[#203448]">{template.name}</CardTitle>
                <CardDescription className="mt-1 line-clamp-2">{template.description || "No project description"}</CardDescription>
              </div>
              <Button type="button" variant="ghost" size="icon" className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive" aria-label={`Delete ${template.name}`} onClick={() => setDeleteCandidate(template)}>
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-2 pt-1"><Badge variant="secondary">{template.category}</Badge><Badge variant="outline">{template.work_items.length} starter task{template.work_items.length === 1 ? "" : "s"}</Badge></div>
          </CardHeader>
          <CardContent className="space-y-3">
            {template.scope && <p className="line-clamp-2 text-xs leading-5 text-muted-foreground">{template.scope}</p>}
            {template.outputs.length > 0 && <p className="text-xs text-muted-foreground"><strong className="font-medium text-[#41576a]">Outputs:</strong> {template.outputs.join(" · ")}</p>}
            {template.work_items.length > 0 && <ul className="grid gap-1.5 border-t pt-3 text-xs text-[#41576a] sm:grid-cols-2">
              {template.work_items.slice(0, 4).map((item, index) => <li key={`${item.title}-${index}`} className="flex min-w-0 items-center gap-2"><span className="h-1.5 w-1.5 shrink-0 rounded-full bg-teal-700" aria-hidden="true" /><span className="truncate">{item.title}</span></li>)}
              {template.work_items.length > 4 && <li className="text-muted-foreground">+{template.work_items.length - 4} more tasks</li>}
            </ul>}
            <Button type="button" onClick={() => { setCreationError(""); setProjectTitle(`${template.name} project`); setSelectedTemplate(template) }} className="w-full"><FolderPlus className="h-4 w-4" aria-hidden="true" />Create project from template</Button>
          </CardContent>
        </Card>)}
      </div>}

      <Dialog open={Boolean(selectedTemplate)} onOpenChange={(open) => { if (!creating && !open) { setSelectedTemplate(null); setCreationError("") } }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader><DialogTitle>Create from {selectedTemplate?.name}</DialogTitle><DialogDescription>The project brief and starter tasks will be copied. Task status resets to To do, dates use their saved offsets, and everyone starts unassigned.</DialogDescription></DialogHeader>
          <form onSubmit={(event) => void handleCreateProject(event)} className="grid gap-4">
            {creationError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{creationError}</p>}
            <div className="grid gap-2"><Label htmlFor="template-project-title">New project title</Label><Input id="template-project-title" value={projectTitle} onChange={(event) => setProjectTitle(event.target.value)} required minLength={1} maxLength={100} /></div>
            <div className="grid gap-2"><Label htmlFor="template-project-deadline">Project deadline <span className="font-normal text-muted-foreground">(optional)</span></Label><Input id="template-project-deadline" type="date" value={projectDeadline} onChange={(event) => setProjectDeadline(event.target.value)} /></div>
            <p className="text-xs leading-5 text-muted-foreground">The new project will belong to your account. You can assign its starter tasks after creating the project.</p>
            <DialogFooter><Button type="button" variant="outline" onClick={() => setSelectedTemplate(null)} disabled={creating}>Cancel</Button><Button type="submit" disabled={!projectTitle.trim() || creating}><FolderPlus className="h-4 w-4" aria-hidden="true" />{creating ? "Creating…" : "Create project"}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(deleteCandidate)} onOpenChange={(open) => { if (!deleting && !open) setDeleteCandidate(null) }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>Delete this template?</DialogTitle><DialogDescription>{deleteCandidate?.name} will be removed from your saved templates. Projects already created from it will not change.</DialogDescription></DialogHeader>
          <DialogFooter><Button type="button" variant="outline" onClick={() => setDeleteCandidate(null)} disabled={deleting}>Keep template</Button><Button type="button" variant="destructive" onClick={() => void handleDeleteTemplate()} disabled={deleting}><Trash2 className="h-4 w-4" aria-hidden="true" />{deleting ? "Deleting…" : "Delete template"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
