import { useEffect, useState, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Separator } from "@/components/ui/separator"
import { apiRequest, getOwnerId, setOwnerId, type Project, type FileRecord, type KnowledgeSource, type KnowledgeAnswerResponse, type SearchResult } from "@/lib/api"
import {
  Activity, ArchiveRestore, FolderCog, FolderKanban, FolderPlus, Gauge, HardDriveUpload,
  HeartPulse, Users, Files, Search, RefreshCw, ShieldCheck,
  Database, FileText, ArrowLeftRight, Library,
  AlertCircle, ExternalLink, CheckCircle2, ScanLine, Menu, CircleHelp
} from "lucide-react"

// Helpers
function escapeForTest(v: string) { return v }
function compactId(v?: string) { return v ? `${v.slice(0, 13)}…` : "—" }
type WorkspaceView = "operations" | "files" | "knowledge" | "recovery" | "setup"

export default function App() {
  // Global
  const [health, setHealth] = useState<{ ok: boolean; text: string; detail: string }>({ ok: false, text: "Checking connection…", detail: "Waiting for /health" })
  const [healthBadge, setHealthBadge] = useState("Checking API…")
  const [flash, setFlash] = useState<{ msg: string; kind: "success" | "error" | null }>({ msg: "", kind: null })
  const [showFlash, setShowFlash] = useState(false)

  const [projects, setProjects] = useState<Project[]>([])
  const [selectedId, setSelectedId] = useState("")
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [activeView, setActiveView] = useState<WorkspaceView>("operations")
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  // Forms + results
  const [ownerResult, setOwnerResult] = useState("")
  const [folderResult, setFolderResult] = useState("")
  const [inventoryResult, setInventoryResult] = useState("")
  const [conversionResult, setConversionResult] = useState("")
  const [organizerResult, setOrganizerResult] = useState("")
  const [backupResult, setBackupResult] = useState("")
  const [knowledgeResult, setKnowledgeResult] = useState("")
  const [ingestResult, setIngestResult] = useState("")
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searchMeta, setSearchMeta] = useState("")
  const [answerResponse, setAnswerResponse] = useState<KnowledgeAnswerResponse | null>(null)
  const [answerError, setAnswerError] = useState("")
  const [answerLoading, setAnswerLoading] = useState(false)
  const [files, setFiles] = useState<FileRecord[]>([])
  const [knowledgeSources, setKnowledgeSources] = useState<KnowledgeSource[]>([])
  const [uploadPolicy, setUploadPolicy] = useState<any>(null)
  const [permissions, setPermissions] = useState<Record<string,string[]> | null>(null)

  // File browser extras
  const [fileSearch, setFileSearch] = useState("")
  const [selectedFile, setSelectedFile] = useState<FileRecord | null>(null)
  const [fileHistory, setFileHistory] = useState<any[]>([])
  const [fileVersions, setFileVersions] = useState<any[]>([])
  const [uploadStorageKey, setUploadStorageKey] = useState("incoming/example.txt")

  // Dialog
  const [confirm, setConfirm] = useState<{ open: boolean; title: string; msg: string; label: string; resolve?: (v:boolean)=>void }>({ open: false, title: "", msg: "", label: "" })
  function confirmAction(title: string, msg: string, label: string): Promise<boolean> {
    return new Promise(res => setConfirm({ open: true, title, msg, label, resolve: res }))
  }

  const showMessage = (msg: string, kind: "success" | "error" = "success") => {
    setFlash({ msg, kind }); setShowFlash(true); setTimeout(()=>setShowFlash(false), 4000)
  }

  const refreshHealth = useCallback(async () => {
    try {
      const payload: any = await apiRequest("/health")
      const ok = payload.status === "ok"
      setHealth({ ok, text: ok ? "Service is ready" : "Service check failed", detail: `GET /health · ${payload.status}` })
      setHealthBadge(ok ? "API online" : "API unavailable")
    } catch (e: any) {
      setHealth({ ok: false, text: "Service check failed", detail: e.message })
      setHealthBadge("API unavailable")
    }
  }, [])

  const refreshProjects = useCallback(async () => {
    try {
      const data = await apiRequest<Project[]>("/projects")
      setProjects(data)
      if (selectedId) {
        const found = data.find(p=>p.id===selectedId)
        if (found) setSelectedProject(found)
      }
    } catch (e: any) {
      setProjects([])
    }
  }, [selectedId])

  const refreshFiles = useCallback(async (projectId: string) => {
    if (!projectId) return
    try { const data = await apiRequest<FileRecord[]>(`/projects/${projectId}/files`); setFiles(data.filter(f=>f.status==="active")) } catch { setFiles([]) }
  }, [])
  const refreshKnowledgeSources = useCallback(async (projectId: string) => {
    if (!projectId) return
    try { const data = await apiRequest<KnowledgeSource[]>(`/projects/${projectId}/knowledge-sources`); setKnowledgeSources(data) } catch { setKnowledgeSources([]) }
  }, [])
  const refreshKnowledgeFiles = useCallback(async (projectId: string) => {
    if (!projectId) return
    try { const data = await apiRequest<FileRecord[]>(`/projects/${projectId}/files`); setFiles(data.filter(f=>f.status==="active")) } catch { setFiles([]) }
  }, [])

  useEffect(()=>{ refreshHealth(); apiRequest<any>("/permissions").then(d=>setPermissions(d.roles)).catch(()=>{}); apiRequest<any>("/upload-policy").then(setUploadPolicy).catch(()=>{}); }, [refreshHealth])
  useEffect(()=>{
    const oid = getOwnerId()
    if (oid) refreshProjects()
    else setProjects([])
  }, [refreshProjects])
  useEffect(()=>{
    if (selectedId) {
      refreshFiles(selectedId)
      refreshKnowledgeSources(selectedId)
    }
  }, [selectedId, refreshFiles, refreshKnowledgeSources])

  // Actions
  async function handleCreateOwner(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget as HTMLFormElement
    const fd = new FormData(form)
    const body = Object.fromEntries(fd.entries())
    const btn = form.querySelector("button[type=submit]") as HTMLButtonElement
    try {
      if (btn) { btn.disabled=true; btn.textContent="Creating…"; btn.setAttribute("aria-busy","true") }
      const user: any = await apiRequest("/users", { method: "POST", body: JSON.stringify(body) })
      setOwnerId(user.id)
      const ownerInput = document.querySelector<HTMLInputElement>("#owner-id")
      if (ownerInput) ownerInput.value = user.id
      setOwnerResult(`Created owner ${user.external_ref}\nID: ${user.id}`)
      await refreshProjects()
      showMessage("Development owner created. Its ID was copied into the project form.")
      if (btn) { btn.disabled=false; btn.removeAttribute("aria-busy"); btn.textContent="Create development owner" }
    } catch (err: any) {
      setOwnerResult(err.message)
      showMessage(err.message, "error")
      if (btn) { btn.disabled=false; btn.removeAttribute("aria-busy"); btn.textContent="Create development owner" }
    }
  }

  async function handleCreateProject(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget as HTMLFormElement
    const fd = new FormData(form)
    const body = Object.fromEntries(fd.entries())
    try {
      const proj: any = await apiRequest("/projects", { method: "POST", body: JSON.stringify(body) })
      setSelectedId(proj.id); setSelectedProject(proj); setAnswerResponse(null); setAnswerError("")
      // sync fields
      const setVal = (sel: string, v: string) => { const el = document.querySelector<HTMLInputElement>(sel); if (el) el.value = v; };
      setVal("#conversion-project-id", proj.id)
      setVal("#inventory-project-id", proj.id)
      setVal("#organizer-project-id", proj.id)
      setVal("#backup-project-id", proj.id)
      setVal("#project-folder-name", proj.storage_slug)
      setVal("#knowledge-project-id", proj.id)
      setVal("#knowledge-owner-id", proj.owner_id || "")
      await refreshProjects()
      showMessage(`Project “${proj.title}” registered. Generate its “${proj.storage_slug}” folder before scanning files.`)
      form.reset()
      const oid = (document.querySelector<HTMLInputElement>("#owner-id")?.value) || proj.owner_id
      if (oid) { const el = document.querySelector<HTMLInputElement>("#owner-id"); if (el) el.value = oid }
    } catch (err: any) { showMessage((err as Error).message, "error") }
  }

  async function handleGenerateFolder(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget as HTMLFormElement
    const fd = new FormData(form)
    try {
      const data: any = await apiRequest("/project-folders", { method: "POST", body: JSON.stringify(Object.fromEntries(fd.entries())) })
      setFolderResult(`Created ${data.project_path}\n${data.subdirectories.join("\n")}`)
      showMessage(`Generated the ${data.name} project folder layout.`)
    } catch (err: any) { setFolderResult((err as Error).message); showMessage((err as Error).message, "error") }
  }

  async function handleInventory(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const projectId = (document.querySelector<HTMLInputElement>("#inventory-project-id")?.value || "").trim()
    try {
      const data: any = await apiRequest(`/projects/${projectId}/inventory`, { method: "POST" })
      setInventoryResult(`Scanned ${data.files_scanned} file(s)\nDuplicate groups: ${data.duplicate_groups} (${data.duplicate_files} file(s))\nJSON: ${data.json_manifest}\nCSV: ${data.csv_manifest}`)
      showMessage("Inventory manifests created inside the project root.")
      refreshFiles(projectId)
    } catch (err: any) {
      const msg = (err as Error).message === "Project storage was not found." ? "Project storage was not found. Generate the selected project's folder layout before scanning." : (err as Error).message
      setInventoryResult(msg); showMessage(msg, "error")
    }
  }

  async function handleConversion(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget as HTMLFormElement
    const fd = new FormData(form)
    const vals = Object.fromEntries(fd.entries()) as any
    const pid = vals.project_id; delete vals.project_id
    try {
      const data: any = await apiRequest(`/projects/${pid}/conversions`, { method: "POST", body: JSON.stringify(vals) })
      setConversionResult(`Converted ${data.source_path} → ${data.destination_path}\n${data.source_format.toUpperCase()} → ${data.destination_format.toUpperCase()} · ${data.bytes_written} bytes`)
      showMessage("Conversion completed without replacing the source or destination.")
    } catch (err: any) { setConversionResult((err as Error).message); showMessage((err as Error).message, "error") }
  }

  async function handleOrganizerPreview() {
    const pid = (document.querySelector<HTMLInputElement>("#organizer-project-id")?.value || "").trim()
    if (!pid) return showMessage("Select a project before using the organiser.", "error")
    try {
      const plan: any = await apiRequest(`/projects/${pid}/organization/plan`, { method: "POST" })
      const actions = plan.actions.length ? plan.actions.map((a:any)=>`[${a.status}] ${a.source} → ${a.destination}`).join("\n") : "No files are waiting in incoming/."
      setOrganizerResult(`Plan: ${plan.plan_path}\n${actions}`)
      showMessage("Dry-run plan created. No files were moved.")
    } catch (e: any) { setOrganizerResult(e.message); showMessage(e.message, "error") }
  }
  async function handleOrganizerApply() {
    const pid = (document.querySelector<HTMLInputElement>("#organizer-project-id")?.value || "").trim()
    if (!pid) return showMessage("Select a project before using the organiser.", "error")
    const quarantine = (document.querySelector<HTMLInputElement>("#quarantine-conflicts")?.checked) || false
    const ok = await confirmAction("Apply the organisation plan?", `Eligible files in the active project will be moved into working/ folders. Conflicts will be protected${quarantine ? " and quarantined" : ""}, and a rollback journal will be saved.`, "Apply safe moves")
    if (!ok) return showMessage("Organisation apply cancelled.")
    try {
      const data: any = await apiRequest(`/projects/${pid}/organization/apply`, { method: "POST", body: JSON.stringify({ quarantine_conflicts: quarantine }) })
      const jp = document.querySelector<HTMLInputElement>("#journal-path"); if (jp) jp.value = data.journal_path
      setOrganizerResult(`Applied ${data.applied_count} of ${data.action_count} action(s)\nConflicts: ${data.conflict_count}\nJournal: ${data.journal_path}` + (data.quarantine_journal_path ? `\nQuarantine journal: ${data.quarantine_journal_path}` : ""))
      showMessage("Safe organisation completed and the rollback journal was saved.")
    } catch (e: any) { setOrganizerResult(e.message); showMessage(e.message, "error") }
  }
  async function handleRollback() {
    const pid = (document.querySelector<HTMLInputElement>("#organizer-project-id")?.value || "").trim()
    const journalPath = (document.querySelector<HTMLInputElement>("#journal-path")?.value || "").trim()
    const ok = await confirmAction("Roll back the organisation journal?", `The active project's recorded moves will be reversed from “${journalPath}” when the journal passes its hash checks.`, "Roll back")
    if (!ok) return showMessage("Organisation rollback cancelled.")
    try {
      const data: any = await apiRequest(`/projects/${pid}/organization/rollback`, { method: "POST", body: JSON.stringify({ journal_path: journalPath }) })
      setOrganizerResult(`Restored ${data.restored_count} file(s) from ${data.journal_path}.`)
      showMessage("Organisation rollback completed.")
    } catch (e: any) { setOrganizerResult(e.message); showMessage(e.message, "error") }
  }

  async function handleBackupCreate() {
    const pid = (document.querySelector<HTMLInputElement>("#backup-project-id")?.value || "").trim()
    if (!pid) return showMessage("Select a project before using backup and recovery.", "error")
    try {
      const data: any = await apiRequest(`/projects/${pid}/backups`, { method: "POST", body: "{}" })
      const bid = document.querySelector<HTMLInputElement>("#backup-id"); if (bid) bid.value = data.id
      setBackupResult(`Backup created and verified.\n${data.id} · ${data.status} · ${data.file_count} file(s) · ${data.total_bytes} bytes\nArchive SHA-256: ${data.archive_checksum_sha256}\nManifest SHA-256: ${data.manifest_checksum_sha256}`)
      showMessage("Project backup created and verified against its manifest.")
    } catch (e: any) { setBackupResult(e.message); showMessage(e.message, "error") }
  }
  async function handleBackupList() {
    const pid = (document.querySelector<HTMLInputElement>("#backup-project-id")?.value || "").trim()
    if (!pid) return showMessage("Select a project before using backup and recovery.", "error")
    try {
      const data: any[] = await apiRequest(`/projects/${pid}/backups`)
      if (!data.length) { setBackupResult("No backups recorded for this project."); showMessage("No project backups are available yet."); return }
      const bid = document.querySelector<HTMLInputElement>("#backup-id"); if (bid) bid.value = data[0].id
      setBackupResult(data.map(b=>`${b.id} · ${b.status} · ${b.file_count} file(s) · ${b.total_bytes} bytes\nArchive SHA-256: ${b.archive_checksum_sha256}\nManifest SHA-256: ${b.manifest_checksum_sha256}`).join("\n\n"))
      showMessage(`Loaded ${data.length} project backup(s). The newest backup is selected.`)
    } catch (e: any) { setBackupResult(e.message); showMessage(e.message, "error") }
  }
  async function handleBackupVerify() {
    const pid = (document.querySelector<HTMLInputElement>("#backup-project-id")?.value || "").trim()
    const bid = (document.querySelector<HTMLInputElement>("#backup-id")?.value || "").trim()
    if (!pid || !bid) return showMessage("Create or select a backup before continuing.", "error")
    try {
      const data: any = await apiRequest(`/projects/${pid}/backups/${bid}/verify`, { method: "POST", body: "{}" })
      setBackupResult(`Integrity verified: ${data.entries_verified} entries, ${data.files_verified} file(s), ${data.bytes_verified} bytes\n${data.backup.id} · ${data.backup.status} · ${data.backup.file_count} file(s)`)
      showMessage("Backup archive and manifest verified successfully.")
    } catch (e: any) { setBackupResult(e.message); showMessage(e.message, "error") }
  }
  async function handleBackupRestore() {
    const pid = (document.querySelector<HTMLInputElement>("#backup-project-id")?.value || "").trim()
    const bid = (document.querySelector<HTMLInputElement>("#backup-id")?.value || "").trim()
    const dest = (document.querySelector<HTMLInputElement>("#backup-destination")?.value || "").trim()
    if (!dest) return showMessage("Enter a new restore destination.", "error")
    const ok = await confirmAction("Restore a new safe copy?", `The selected backup will be copied to “${dest}”. The original project will remain unchanged.`, "Restore copy")
    if (!ok) return showMessage("Restore cancelled.")
    try {
      const data: any = await apiRequest(`/projects/${pid}/backups/${bid}/restore`, { method: "POST", body: JSON.stringify({ destination_path: dest }) })
      setBackupResult(`Restored ${data.files_restored} file(s) and ${data.bytes_restored} bytes\nDestination: ${data.destination_path}\nArchive SHA-256: ${data.archive_checksum_sha256}\nManifest SHA-256: ${data.manifest_checksum_sha256}`)
      showMessage("Backup restored to a new destination; the original was preserved.")
    } catch (e: any) { setBackupResult(e.message); showMessage(e.message, "error") }
  }

  async function handleKnowledgeRegister(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget as HTMLFormElement
    const fd = new FormData(form)
    const vals = Object.fromEntries(fd.entries()) as any
    const pid = vals.project_id; delete vals.project_id
    try {
      const src: any = await apiRequest(`/projects/${pid}/knowledge-sources`, { method: "POST", body: JSON.stringify(vals) })
      setKnowledgeResult(`Registered ${src.title}\nStatus: ${src.approval_status}\nFile: ${src.file_name}`)
      showMessage("Knowledge source registered for review. It cannot feed the knowledge base until approved.")
      ;(form.querySelector("input[name=title]") as HTMLInputElement).value=""
      refreshKnowledgeSources(pid)
    } catch (e: any) { setKnowledgeResult((e as Error).message); showMessage((e as Error).message, "error") }
  }
  async function handleIngest(sourceId: string) {
    const pid = selectedId
    if (!pid) return showMessage("Select a project first", "error")
    try {
      const data: any = await apiRequest(`/projects/${pid}/knowledge-sources/${sourceId}/ingest`, { method: "POST" })
      setIngestResult(`Ingested ${data.chunk_count} chunks · ${data.status}\nSource: ${data.source_id}`)
      showMessage(`Ingested ${data.chunk_count} chunks successfully.`)
      refreshKnowledgeSources(pid)
    } catch (e: any) { setIngestResult(e.message); showMessage(e.message, "error") }
  }
  async function handleReview(sourceId: string, decision: "approved" | "rejected") {
    const pid = selectedId
    const reason = decision==="rejected" ? prompt("Rejection reason:") : null
    if (decision==="rejected" && !reason) return
    try {
      await apiRequest(`/projects/${pid}/knowledge-sources/${sourceId}/review`, { method: "POST", body: JSON.stringify({ decision, reason: reason||undefined }) })
      showMessage(`Source ${decision}.`)
      refreshKnowledgeSources(pid)
    } catch (e: any) { showMessage(e.message, "error") }
  }
  async function handleSearch(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget as HTMLFormElement
    const fd = new FormData(form)
    const vals = Object.fromEntries(fd.entries()) as any
    const query = vals.query as string
    const limit = 5
    try {
      const data: any = await apiRequest(`/projects/${selectedId}/knowledge-search`, { method: "POST", body: JSON.stringify({ query, limit }) })
      setSearchResults(data.results || [])
      setSearchMeta(`${data.result_count} passages · ${data.embedding_model} ${data.embedding_dimensions}d`)
      showMessage(`Found ${data.result_count} passages.`)
    } catch (err: any) { setSearchMeta((err as Error).message); showMessage((err as Error).message, "error") }
  }
  async function handleAnswer(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget as HTMLFormElement
    const query = String(new FormData(form).get("query") || "").trim()
    if (!selectedId) return showMessage("Select a project before asking a question.", "error")
    setAnswerLoading(true)
    setAnswerError("")
    setAnswerResponse(null)
    try {
      const data = await apiRequest<KnowledgeAnswerResponse>(`/projects/${selectedId}/knowledge-answer`, {
        method: "POST",
        body: JSON.stringify({ query, evidence_limit: 5 }),
      })
      setAnswerResponse(data)
      if (data.status === "answered") {
        showMessage(`Grounded answer ready with ${data.citation_count} citation${data.citation_count === 1 ? "" : "s"}.`)
      } else {
        showMessage("No approved evidence supported that question.", "error")
      }
    } catch (err: any) {
      const message = (err as Error).message
      setAnswerError(message)
      showMessage(message, "error")
    } finally {
      setAnswerLoading(false)
    }
  }

  // File browser
  async function handleFileSearch() {
    if (!selectedId) return
    const q = fileSearch.trim()
    if (!q) { refreshFiles(selectedId); return }
    try { const data = await apiRequest<FileRecord[]>(`/projects/${selectedId}/files/search?q=${encodeURIComponent(q)}`); setFiles(data) } catch (e: any) { showMessage(e.message, "error") }
  }
  async function openFileDetail(f: FileRecord) {
    setSelectedFile(f)
    try {
      const h = await apiRequest<any[]>(`/projects/${selectedId}/files/${f.id}/history`)
      setFileHistory(h)
      const v = await apiRequest<any[]>(`/projects/${selectedId}/files/${f.id}/versions`)
      setFileVersions(v)
    } catch { setFileHistory([]); setFileVersions([]) }
  }
  async function handleRestoreVersion(versionNumber: number) {
    if (!selectedFile || !selectedId) return
    const dest = prompt("New destination path (relative, no overwrite):", `${selectedFile.storage_key}.restored`)
    if (!dest) return
    try {
      const data: any = await apiRequest(`/projects/${selectedId}/files/${selectedFile.id}/versions/${versionNumber}/restore`, { method: "POST", body: JSON.stringify({ destination_path: dest }) })
      showMessage(`Restored ${data.bytes_restored} bytes to ${data.destination_path}`)
    } catch (e: any) { showMessage(e.message, "error") }
  }
  async function handleUpload() {
    if (!selectedId) return showMessage("Select a project", "error")
    if (!uploadStorageKey) return showMessage("Enter storage key", "error")
    const content = prompt("File content to upload (text, for demo):", "Hello CCL")
    if (content===null) return
    try {
      const blob = new Blob([content], { type: "text/plain" })
      const res = await fetch(`/projects/${selectedId}/uploads/${encodeURIComponent(uploadStorageKey)}`, {
        method: "PUT",
        headers: { "X-User-ID": getOwnerId(), "Content-Type": "text/plain" },
        body: blob
      })
      const j = await res.json()
      if (!res.ok) throw new Error(j.detail || "Upload failed")
      showMessage(`Uploaded ${j.name} · ${j.size_bytes} bytes · ${j.checksum_sha256.slice(0,12)}…`)
      refreshFiles(selectedId)
    } catch (e: any) { showMessage(e.message, "error") }
  }

  const selectedProjectName = selectedProject?.title || "No project selected"

  function activateProject(project: Project) {
    setSelectedId(project.id)
    setSelectedProject(project)
    setAnswerResponse(null)
    setAnswerError("")
    const setVal = (selector: string, value: string) => {
      const element = document.querySelector<HTMLInputElement>(selector)
      if (element) element.value = value
    }
    setVal("#conversion-project-id", project.id)
    setVal("#inventory-project-id", project.id)
    setVal("#setup-inventory-project-id", project.id)
    setVal("#organizer-project-id", project.id)
    setVal("#backup-project-id", project.id)
    setVal("#project-folder-name", project.storage_slug)
    setVal("#knowledge-project-id", project.id)
    setVal("#knowledge-owner-id", project.owner_id || "")
  }

  const navigation: Array<{ view: WorkspaceView; label: string; icon: typeof Gauge }> = [
    { view: "operations", label: "Operations", icon: Gauge },
    { view: "files", label: "Files", icon: Files },
    { view: "knowledge", label: "Knowledge", icon: Library },
    { view: "recovery", label: "Recovery", icon: ArchiveRestore },
    { view: "setup", label: "Setup", icon: FolderCog },
  ]

  const viewCopy: Record<WorkspaceView, { title: string; description: string }> = {
    operations: { title: "Operations", description: "Preview and run controlled work inside the active project." },
    files: { title: "Files", description: "Search active files, inspect history, and restore immutable versions." },
    knowledge: { title: "Knowledge", description: "Register, review, ingest, search, and answer from approved sources." },
    recovery: { title: "Recovery", description: "Create, verify, and restore checksummed project backups." },
    setup: { title: "Workspace setup", description: "Provision an owner, register a project, and prepare local storage." },
  }

  const openView = (view: WorkspaceView) => {
    setActiveView(view)
    setMobileNavOpen(false)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  return (
    <div className="min-h-screen">
      <a className="skip-link" href="#main-content">Skip to main content</a>

      <aside className="app-sidebar hidden lg:flex" aria-label="Primary navigation">
        <div className="sidebar-inner">
          <a className="brand-lockup" href="/" aria-label="CCL AI Suite home">
            <span className="brand-mark">CCL</span>
            <strong className="brand-name">AI Suite</strong>
          </a>
          <nav className="app-links">
            <p className="nav-label">Operate</p>
            {navigation.slice(0, 4).map(({ view, label, icon: Icon }) => (
              <Button key={view} variant="ghost" className={activeView === view ? "is-active" : ""} onClick={() => openView(view)}>
                <Icon className="h-4 w-4" />{label}
              </Button>
            ))}
            <Separator className="my-3 bg-white/10" />
            <p className="nav-label">Administration</p>
            {navigation.slice(4).map(({ view, label, icon: Icon }) => (
              <Button key={view} variant="ghost" className={activeView === view ? "is-active" : ""} onClick={() => openView(view)}>
                <Icon className="h-4 w-4" />{label}
              </Button>
            ))}
          </nav>
          <div className="sidebar-status">
            <span id="health-badge" className={`health-pill ${health.ok ? "is-online" : "is-offline"}`} role="status" aria-live="polite">
              <span className="health-pulse" /> {healthBadge}
            </span>
            <a className="docs-link" href="/docs" target="_blank" rel="noreferrer"><CircleHelp className="h-4 w-4" />API documentation <ExternalLink className="ml-auto h-3 w-3" /></a>
          </div>
        </div>
      </aside>

      <header className="app-topbar">
        <div className="flex min-w-0 items-center gap-3">
          <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <SheetTrigger asChild><Button variant="outline" size="icon" className="lg:hidden" aria-label="Open navigation"><Menu className="h-4 w-4" /></Button></SheetTrigger>
            <SheetContent side="left" className="w-[18rem] bg-[#101828] p-0 text-white">
              <SheetHeader className="border-b border-white/10 p-5 text-left"><SheetTitle className="text-white">CCL AI Suite</SheetTitle><SheetDescription className="text-white/55">Controlled operations</SheetDescription></SheetHeader>
              <nav className="mobile-links p-3">
                {navigation.map(({ view, label, icon: Icon }) => (
                  <Button key={view} variant="ghost" className={activeView === view ? "is-active" : ""} onClick={() => openView(view)}><Icon className="h-4 w-4" />{label}</Button>
                ))}
              </nav>
            </SheetContent>
          </Sheet>
          <div className="project-switcher">
            <span className="hidden text-xs text-muted-foreground sm:inline">Project</span>
            <Select value={selectedId || undefined} onValueChange={(value) => { const project = projects.find(item => item.id === value); if (project) activateProject(project) }}>
              <SelectTrigger aria-label="Active project" className="w-[12rem] sm:w-[16rem]"><FolderKanban className="h-4 w-4" /><SelectValue placeholder="Select a project" /></SelectTrigger>
              <SelectContent>{projects.map(project => <SelectItem key={project.id} value={project.id}>{project.title}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`service-state ${health.ok ? "is-online" : "is-offline"}`}><span />{health.ok ? "Ready" : "Unavailable"}</span>
          <Separator orientation="vertical" className="hidden h-6 sm:block" />
          <Button variant="ghost" size="icon" className="hidden sm:inline-flex" asChild><a href="/docs" target="_blank" rel="noreferrer" aria-label="Open API documentation"><CircleHelp className="h-4 w-4" /></a></Button>
          <div className="operator-menu"><span>Operator</span><span className="operator-avatar">OP</span></div>
        </div>
      </header>

      <main id="main-content" className="app-main" data-view={activeView}>
        <header className={activeView === "operations" ? "sr-only" : "workspace-heading"}>
          <div><h1 id="page-title">{viewCopy[activeView].title}</h1><p>{viewCopy[activeView].description}</p></div>
          {activeView === "setup" && <Button id="workspace-projects-refresh" variant="outline" size="sm" onClick={() => refreshProjects()}><RefreshCw className="h-3.5 w-3.5" />Refresh projects</Button>}
        </header>

        {/* Flash */}
        <div id="flash" className={`rounded-lg border px-3 py-2.5 text-sm mb-4 ${showFlash ? "block" : "hidden"} ${flash.kind==="error" ? "border-red-200 bg-red-50 text-red-800" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`} role={flash.kind==="error" ? "alert" : "status"} aria-live="polite" hidden={!showFlash}>{flash.msg}</div>

        {/* Workflow steps — production */}
        <Card className={`${activeView === "setup" ? "block" : "hidden"} workflow-panel major-panel mb-5 card-elevated`}>
          <CardHeader className="pb-2 flex flex-row items-end justify-between">
            <div><CardTitle className="text-[1.1rem]">Build a ready workspace</CardTitle></div>
            <p className="text-xs text-muted-foreground hidden md:block">The active project is shared across the cards below.</p>
          </CardHeader>
          <CardContent>
            <ol className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2 list-none p-0">
              {[
                { n: 1, t: "Create an owner", d: "Get the ID needed for projects.", href: "#owner-setup" },
                { n: 2, t: "Register a project", d: "Give the workspace a stable folder name.", href: "#project-setup" },
                { n: 3, t: "Prepare storage", d: "Generate its controlled folder layout.", href: "#folder-setup" },
                { n: 4, t: "Run operations", d: "Scan, convert, organise, or recover.", href: "#file-operations" },
              ].map(s=>(
                <li key={s.n}><a href={s.href} className="workflow-step">
                  <span className="workflow-marker">{s.n}</span>
                  <span><strong className="block text-xs">{s.t}</strong><small className="text-[0.70rem] text-muted-foreground">{s.d}</small></span>
                </a></li>
              ))}
            </ol>
          </CardContent>
        </Card>

        {/* Active project context - preserve ids */}
        <div id="workspace-context" className="workspace-signal">
          <div className="project-ledger-title">
            <div className="min-w-0"><span>Project</span><h2 id="active-project-title">{selectedProjectName}</h2></div>
          </div>
          <details className="mobile-ledger-details">
            <summary>Project details</summary>
            <dl>
              <div><dt>Project ID</dt><dd title={selectedId}>{compactId(selectedId)}</dd></div>
              <div><dt>Owner</dt><dd>{selectedProject?.owner_id ? "Operator" : "not assigned"}</dd></div>
              <div><dt>Storage</dt><dd>{selectedProject?.storage_slug || "—"}</dd></div>
            </dl>
          </details>
          <div className="ledger-field"><span>Project ID</span><code id="active-project-id" title={selectedId}>{compactId(selectedId)}</code></div>
          <div className="ledger-field"><span>Owner</span><code title={selectedProject?.owner_id}>{selectedProject?.owner_id ? "Operator" : "not assigned"}</code></div>
          <div className="ledger-field"><span>Storage folder</span><code id="active-project-detail">{selectedProject?.storage_slug || "—"}</code></div>
          <div className="ledger-status">
            <span id="active-project-status" className={selectedId ? "ready" : "waiting"}><span />{selectedId ? "Ready to operate" : "Select project"}</span>
            {!selectedId && <Button variant="outline" size="sm" onClick={() => openView("setup")}>Open setup</Button>}
          </div>
        </div>

        {/* Setup grid */}
        <section id="setup" className={activeView === "setup" ? "mb-6" : "hidden"}>
          <div className="flex items-end justify-between mb-3">
            <div><h2 className="text-xl font-bold tracking-tight">Set up your workspace</h2></div>
            <p className="hidden md:block text-xs text-muted-foreground">Start here when the API is online or when you need to prepare a new project.</p>
          </div>

          <div className="setup-deck">
            {/* Health - preserve ids */}
            <Card id="service-health" className="setup-panel">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="panel-label">Service</p><CardTitle className="text-[1rem] flex items-center gap-1.5"><HeartPulse className="w-4 h-4 text-primary" />System health</CardTitle></div>
                <span className="panel-icon"><Activity className="h-4 w-4" /></span>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">Confirm that the API is reachable before starting an operation.</p>
                <div className="flex items-center gap-2 bg-muted/50 border rounded-xl p-2.5">
                  <span id="health-dot" className={`w-2.5 h-2.5 rounded-full ${health.ok ? "bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.15)]" : "bg-amber-500"}`} />
                  <div><strong id="health-text" className="block text-xs">{health.text}</strong><span id="health-detail" className="text-xs text-muted-foreground">{health.detail}</span></div>
                </div>
                <Button id="health-refresh" variant="secondary" size="sm" onClick={()=>refreshHealth()}><RefreshCw className="w-3.5 h-3.5 mr-1" />Refresh health</Button>
                {permissions && <div className="text-[0.68rem] text-muted-foreground">Roles: {Object.keys(permissions).join(" · ")} · upload: {uploadPolicy ? `${uploadPolicy.max_size_bytes/1024/1024}MB` : "…"}</div>}
              </CardContent>
            </Card>

            {/* Owner - preserve #user-form, #owner-id, #user-result */}
            <Card id="owner-setup" className="setup-panel">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="panel-label">Identity</p><CardTitle className="text-[1rem] flex items-center gap-1.5"><Users className="w-4 h-4 text-primary" />Development owner</CardTitle></div>
                <span className="panel-icon"><Users className="h-4 w-4" /></span>
              </CardHeader>
              <CardContent className="space-y-3">
                <p id="owner-form-help" className="text-xs text-muted-foreground">Create the local owner whose opaque ID will be attached to new projects.</p>
                <form id="user-form" onSubmit={handleCreateOwner} className="grid gap-3" aria-describedby="owner-form-help">
                  <div className="grid gap-1.5">
                    <Label htmlFor="user-external-ref" className="text-xs">External reference</Label>
                    <Input id="user-external-ref" name="external_ref" defaultValue="local-owner" required maxLength={128} />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="user-role" className="text-xs">Role</Label>
                    <Select name="role" defaultValue="member">
                      <SelectTrigger id="user-role"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="administrator">administrator</SelectItem>
                        <SelectItem value="supervisor">supervisor</SelectItem>
                        <SelectItem value="member">member (→ staff)</SelectItem>
                        <SelectItem value="staff">staff</SelectItem>
                        <SelectItem value="intern">intern (read-only)</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-[0.68rem] text-muted-foreground">member→staff, reviewer→supervisor aliases.</p>
                  </div>
                  <Button type="submit">Create development owner</Button>
                </form>
                <div id="user-result" className={`text-xs whitespace-pre-wrap ${ownerResult ? "quiet-result block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!ownerResult}>{ownerResult}</div>
              </CardContent>
            </Card>

            {/* Project - preserve #project-form, #owner-id */}
            <Card id="project-setup" className="setup-panel">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="panel-label">Workspace</p><CardTitle className="text-[1rem] flex items-center gap-1.5"><FolderKanban className="w-4 h-4 text-primary" />Register a project</CardTitle></div>
                <span className="panel-icon"><FolderPlus className="h-4 w-4" /></span>
              </CardHeader>
              <CardContent className="space-y-3">
                <p id="project-form-help" className="text-xs text-muted-foreground">The title becomes one immutable, lowercase storage folder name.</p>
                <form id="project-form" onSubmit={handleCreateProject} className="grid gap-3" aria-describedby="project-form-help">
                  <div className="grid gap-1.5"><Label htmlFor="project-title" className="text-xs">Project title</Label><Input id="project-title" name="title" placeholder="e.g. Client Intake Q3" required maxLength={100} /></div>
                  <div className="grid gap-1.5"><Label htmlFor="project-description" className="text-xs">Description</Label><Textarea id="project-description" name="description" rows={3} maxLength={500} placeholder="What will this workspace contain?" /></div>
                  <div className="grid gap-1.5"><Label htmlFor="owner-id" className="text-xs">Owner ID</Label><Input id="owner-id" name="owner_id" placeholder="Create an owner above" required defaultValue={getOwnerId()} /></div>
                  <Button type="submit">Register project</Button>
                </form>
              </CardContent>
            </Card>

            {/* Folder - preserve #folder-form, #project-folder-name, #folder-result */}
            <Card id="folder-setup" className="setup-panel">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="panel-label">Filesystem</p><CardTitle className="text-[1rem] flex items-center gap-1.5"><FolderKanban className="w-4 h-4 text-primary" />Generate project folders</CardTitle></div>
                <span className="panel-icon"><FolderCog className="h-4 w-4" /></span>
              </CardHeader>
              <CardContent className="space-y-3">
                <p id="folder-form-help" className="text-xs text-muted-foreground">Select a project first, then create its safe incoming, working, output, and archive layout.</p>
                <form id="folder-form" onSubmit={handleGenerateFolder} className="grid gap-3" aria-describedby="folder-form-help">
                  <div className="grid gap-1.5"><Label htmlFor="project-folder-name" className="text-xs">Project folder name</Label><Input id="project-folder-name" name="project_name" placeholder="Select a project below" required maxLength={100} defaultValue={selectedProject?.storage_slug || ""} /></div>
                  <Button type="submit">Generate folder layout</Button>
                </form>
                <div id="folder-result" className={`text-xs whitespace-pre-wrap ${folderResult ? "quiet-result block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!folderResult}>{folderResult}</div>
              </CardContent>
            </Card>

            {/* Inventory - preserve #inventory-form, #inventory-project-id, #inventory-result */}
            <Card id="setup-inventory" className="setup-panel">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="panel-label">Inventory</p><CardTitle className="text-[1rem] flex items-center gap-1.5"><Files className="w-4 h-4 text-primary" />Scan project files</CardTitle></div>
                <span className="panel-icon"><ScanLine className="h-4 w-4" /></span>
              </CardHeader>
              <CardContent className="space-y-3">
                <p id="setup-inventory-form-help" className="text-xs text-muted-foreground">After storage exists, create JSON and CSV manifests with MIME checks and SHA-256 hashes.</p>
                <form id="setup-inventory-form" onSubmit={handleInventory} className="grid gap-3" aria-describedby="setup-inventory-form-help">
                  <div className="grid gap-1.5"><Label htmlFor="setup-inventory-project-id" className="text-xs">Project ID</Label><Input id="setup-inventory-project-id" name="project_id" placeholder="Select a project below" required defaultValue={selectedId} /></div>
                  <Button variant="secondary" type="submit">Scan project files</Button>
                </form>
                <div id="setup-inventory-result" className={`text-xs whitespace-pre-wrap ${inventoryResult ? "quiet-result block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!inventoryResult}>{inventoryResult}</div>
              </CardContent>
            </Card>

            <Card className="setup-panel">
              <CardHeader className="pb-2">
                <p className="panel-label">Upload</p>
                <CardTitle className="text-[1rem] flex items-center gap-1.5"><HardDriveUpload className="w-4 h-4 text-primary" />Secure upload</CardTitle>
                <CardDescription className="text-xs">Allowlisted upload with size, extension, MIME checks.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {uploadPolicy && <div className="flex flex-wrap gap-1">{Object.entries(uploadPolicy.allowed_extensions as any).map(([cat, exts]: any)=><Badge key={cat} variant="outline" className="text-[0.68rem]">{cat}: {(exts as string[]).join(", ")}</Badge>)}<Badge className="bg-amber-100 text-amber-800 border-amber-200">max {Math.round(uploadPolicy.max_size_bytes/1024/1024)}MB</Badge></div>}
                <div className="grid gap-1.5"><Label className="text-xs">Storage key</Label><Input value={uploadStorageKey} onChange={e=>setUploadStorageKey(e.target.value)} placeholder="incoming/example.txt" /></div>
                <Button onClick={handleUpload} className="w-full" variant="outline">PUT Upload (text demo)</Button>
                <p className="text-[0.68rem] text-muted-foreground">Real endpoint: <code className="bg-muted px-1 rounded">PUT /projects/{`{id}`}/uploads/{`{key}`}</code></p>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* Projects list - preserve #projects, #projects-list, #projects-refresh */}
        <Card id="projects" className={`${activeView === "setup" ? "block" : "hidden"} major-panel mb-8 card-elevated`}>
          <CardHeader className="flex flex-row items-center justify-between">
            <div><CardTitle>Registered projects</CardTitle><CardDescription className="text-xs">Choose <strong>Use project</strong> to populate every operation form with the same project.</CardDescription></div>
            <Button id="projects-refresh" variant="secondary" size="sm" onClick={()=>refreshProjects()}><RefreshCw className="w-3.5 h-3.5 mr-1" />Refresh list</Button>
          </CardHeader>
          <CardContent>
            <div id="projects-list" aria-live="polite">
              {projects.length===0 ? <p className="border border-dashed rounded-xl p-4 text-sm text-muted-foreground">No projects registered yet. Create one above to start a workflow.</p> :
                <div className="overflow-x-auto">
                  <Table className="projects-table min-w-[680px]">
                    <TableHeader><TableRow><TableHead>Project</TableHead><TableHead>Status</TableHead><TableHead>Description</TableHead><TableHead>Action</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {projects.map(p=>(
                        <TableRow key={p.id} className={p.id===selectedId ? "bg-primary/10" : ""}>
                          <TableCell><span className="font-extrabold block">{escapeForTest(p.title)}</span><span className="font-mono text-xs text-muted-foreground">{p.id}</span><div className="text-xs text-muted-foreground">/{p.storage_slug}</div></TableCell>
                          <TableCell><Badge variant="secondary" className={p.status==="active" ? "bg-emerald-100 text-emerald-700" : ""}>{p.status}</Badge></TableCell>
                          <TableCell className="max-w-[260px] truncate text-xs">{p.description || "—"}</TableCell>
                          <TableCell><Button size="sm" variant={p.id===selectedId ? "default" : "secondary"} data-project-id={p.id} data-project-slug={p.storage_slug} data-project-title={p.title} data-project-owner={p.owner_id} aria-pressed={p.id===selectedId} className={`select-project ${p.id===selectedId ? "is-selected" : ""}`} onClick={()=>activateProject(p)}>Use project</Button></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              }
            </div>
          </CardContent>
        </Card>

        {/* File operations */}
        <section id="file-operations" className={activeView === "operations" ? "operation-workspace" : "hidden"}>
          <Tabs defaultValue="organize" className="operation-tabs">
            <TabsList aria-label="Operation type">
              <TabsTrigger value="upload"><HardDriveUpload className="h-4 w-4" />Upload</TabsTrigger>
              <TabsTrigger value="organize"><FolderKanban className="h-4 w-4" />Organize</TabsTrigger>
              <TabsTrigger value="convert"><ArrowLeftRight className="h-4 w-4" />Convert</TabsTrigger>
              <TabsTrigger value="inventory"><ScanLine className="h-4 w-4" />Inventory</TabsTrigger>
            </TabsList>
            <p className="mobile-tab-hint">Swipe to see all operations →</p>

            <TabsContent value="upload" className="mt-0">
              <div className="task-layout">
                <div className="task-surface">
                  <div className="task-header"><div><h2>Upload a file</h2><p>Add an allowlisted text file to the active project and index its metadata.</p></div><Badge variant="outline">Maximum {uploadPolicy ? `${Math.round(uploadPolicy.max_size_bytes/1024/1024)} MB` : "size loading"}</Badge></div>
                  <div className="task-body grid gap-5">
                    <div className="grid gap-2"><Label htmlFor="operation-upload-key">Storage key</Label><Input id="operation-upload-key" value={uploadStorageKey} onChange={event => setUploadStorageKey(event.target.value)} placeholder="incoming/example.txt" /></div>
                    {uploadPolicy && <div className="flex flex-wrap gap-1.5">{Object.entries(uploadPolicy.allowed_extensions as any).map(([category, extensions]: any) => <Badge key={category} variant="secondary">{category}: {(extensions as string[]).join(", ")}</Badge>)}</div>}
                    <Button onClick={handleUpload} className="w-fit"><HardDriveUpload className="h-4 w-4" />Upload text file</Button>
                  </div>
                </div>
                <aside className="evidence-rail" aria-label="Upload safeguards"><div className="evidence-panel"><div className="evidence-title"><ShieldCheck className="h-4 w-4" />Upload policy</div><ul><li><CheckCircle2 />Extension and MIME type must agree</li><li><CheckCircle2 />Storage paths remain project-scoped</li><li><CheckCircle2 />Rejected attempts are audited</li></ul></div><div className="evidence-panel"><div className="evidence-title"><FolderKanban className="h-4 w-4" />Destination</div><p><code>{uploadStorageKey || "Choose a storage key"}</code></p></div></aside>
              </div>
            </TabsContent>

            <TabsContent value="organize" className="mt-0">
              <div className="task-layout">
                <div className="task-surface">
                  <div className="task-header">
                    <div><h2>Organize project files</h2><p>Preview every proposed move before applying it to the active project.</p></div>
                    <Badge variant="outline">Dry run first</Badge>
                  </div>
                  <div className="task-body">
                    <div className="form-section">
                      <div className="form-section-heading"><h3>Project scope</h3><p>Only files inside this project can be moved.</p></div>
                      <div className="scope-grid">
                        <div className="grid gap-2"><Label htmlFor="organizer-project-id">Project ID</Label><Input id="organizer-project-id" placeholder="Select a project" required defaultValue={selectedId} readOnly /></div>
                        <div><Label>Source location</Label><code>incoming/</code></div>
                        <div><Label>Destination</Label><code>working/</code></div>
                      </div>
                    </div>
                    <Separator />
                    <div className="form-section">
                      <div className="form-section-heading"><h3>Plan controls</h3><p>Conflicts remain untouched unless quarantine is enabled.</p></div>
                      <div className="plan-control-grid">
                        <div className="grid gap-2"><Label htmlFor="plan-mode">Plan mode</Label><select id="plan-mode" defaultValue="dry-run"><option value="dry-run">Dry run (preview only)</option></select></div>
                        <div className="grid gap-2"><Label htmlFor="conflict-resolution">Conflict resolution</Label><select id="conflict-resolution" defaultValue="never-overwrite"><option value="never-overwrite">Never overwrite</option></select></div>
                        <label className="checkbox-row"><input id="quarantine-conflicts" type="checkbox" /> <span><strong>Quarantine conflicts</strong><small>Move conflicts to a protected quarantine folder.</small></span></label>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Button id="organizer-preview" onClick={handleOrganizerPreview}>Preview plan</Button>
                        {organizerResult && <Button id="organizer-apply" variant="outline" onClick={handleOrganizerApply}>Apply safe moves</Button>}
                        <span className="text-xs text-muted-foreground">Generates a proposed change set. No files move.</span>
                      </div>
                    </div>
                    <Separator />
                    <div className="preview-region">
                      <div className="preview-region-heading"><div><h3>Proposed changes</h3><p>The dry-run plan will appear here before any file moves.</p></div><Badge variant="secondary">0 changes</Badge></div>
                      <div className="preview-table-shell">
                        <Table>
                          <TableHeader><TableRow><TableHead>Action</TableHead><TableHead>Source</TableHead><TableHead>Destination</TableHead><TableHead>Type</TableHead><TableHead>Reason</TableHead></TableRow></TableHeader>
                        </Table>
                        <div className="preview-empty"><ScanLine className="h-5 w-5" /><strong>No preview yet</strong><span>{selectedId ? "Run Preview plan to inspect each proposed source and destination." : "Select a project, then preview the plan to inspect proposed changes."}</span></div>
                      </div>
                    </div>
                    <div id="organizer-result" className={organizerResult ? "result-panel" : "hidden"} role="status" aria-live="polite" tabIndex={-1} hidden={!organizerResult}>{organizerResult}</div>
                  </div>
                </div>
                <aside className="evidence-rail" aria-label="Operation evidence">
                  <div className="evidence-panel"><div className="evidence-title"><ShieldCheck className="h-4 w-4" />Safety constraints</div><ul><li><CheckCircle2 />Source files are never overwritten</li><li><CheckCircle2 />Preview makes no file changes</li><li><CheckCircle2 />Applied moves write a rollback journal</li><li><CheckCircle2 />Conflicts remain protected</li></ul></div>
                  <div className="evidence-panel"><div className="evidence-title"><FolderKanban className="h-4 w-4" />Project scope</div><dl><div><dt>Project</dt><dd>{selectedProjectName}</dd></div><div><dt>Source</dt><dd><code>{selectedProject?.storage_slug ? `${selectedProject.storage_slug}/incoming/` : "incoming/"}</code></dd></div><div><dt>Target</dt><dd><code>{selectedProject?.storage_slug ? `${selectedProject.storage_slug}/working/` : "working/"}</code></dd></div><div><dt>Indexed items</dt><dd>{files.length} files</dd></div></dl><Button variant="link" className="mt-2 h-auto p-0 text-xs" onClick={() => openView("files")}>View in Files <ExternalLink className="h-3 w-3" /></Button></div>
                  <div className="evidence-panel"><div className="evidence-title"><RefreshCw className="h-4 w-4" />Rollback journal</div><div className="grid gap-2"><Label htmlFor="journal-path">Journal path</Label><Input id="journal-path" defaultValue="organization-journal.json" required /><Button id="organizer-rollback" variant="secondary" size="sm" onClick={handleRollback}>Roll back journal</Button></div></div>
                  <div className="evidence-panel"><div className="evidence-title"><Activity className="h-4 w-4" />Latest result</div>{organizerResult ? <pre>{organizerResult}</pre> : <dl><div><dt>Status</dt><dd>Awaiting preview</dd></div><div><dt>Plan created</dt><dd>—</dd></div><div><dt>Changes</dt><dd>0 proposed</dd></div></dl>}</div>
                </aside>
              </div>
            </TabsContent>

            <TabsContent value="convert" className="mt-0">
              <div className="task-layout">
                <div className="task-surface">
                  <div className="task-header"><div><h2>Convert a file</h2><p>Create a new format inside the active project without replacing the source.</p></div><div className="flex gap-1"><Badge variant="outline">CSV ↔ JSON</Badge><Badge variant="outline">MD ↔ TXT</Badge><Badge variant="outline">PNG ↔ JPG</Badge></div></div>
                  <form id="conversion-form" onSubmit={handleConversion} className="task-body grid gap-5">
                    <div className="grid gap-2"><Label htmlFor="conversion-project-id">Project ID</Label><Input id="conversion-project-id" name="project_id" placeholder="Select a project" required defaultValue={selectedId} readOnly /></div>
                    <div className="grid gap-2 md:grid-cols-2"><div className="grid gap-2"><Label htmlFor="conversion-source-path">Source path</Label><Input id="conversion-source-path" name="source_path" defaultValue="incoming/records.csv" required /></div><div className="grid gap-2"><Label htmlFor="conversion-destination-path">Destination path</Label><Input id="conversion-destination-path" name="destination_path" defaultValue="output/records.json" required /></div></div>
                    <Button type="submit" className="w-fit">Run conversion</Button>
                    <div id="conversion-result" className={conversionResult ? "result-panel" : "hidden"} role="status" aria-live="polite" tabIndex={-1} hidden={!conversionResult}>{conversionResult}</div>
                  </form>
                </div>
                <aside className="evidence-rail" aria-label="Conversion safeguards"><div className="evidence-panel"><div className="evidence-title"><ShieldCheck className="h-4 w-4" />Conversion safeguards</div><ul><li><CheckCircle2 />Source remains unchanged</li><li><CheckCircle2 />Existing destinations are rejected</li><li><CheckCircle2 />Paths stay inside project storage</li></ul></div><div className="evidence-panel"><div className="evidence-title"><Activity className="h-4 w-4" />Latest result</div>{conversionResult ? <pre>{conversionResult}</pre> : <p>Run a conversion to see the generated artifact.</p>}</div></aside>
              </div>
            </TabsContent>

            <TabsContent value="inventory" className="mt-0">
              <div className="task-layout">
                <div className="task-surface">
                  <div className="task-header"><div><h2>Scan project inventory</h2><p>Create JSON and CSV manifests with MIME checks and SHA-256 hashes.</p></div><Badge variant="outline">Read-only scan</Badge></div>
                  <form id="inventory-form" onSubmit={handleInventory} className="task-body grid gap-5">
                    <div className="grid gap-2"><Label htmlFor="inventory-project-id">Project ID</Label><Input id="inventory-project-id" name="project_id" placeholder="Select a project" required defaultValue={selectedId} readOnly /></div>
                    <Button type="submit" className="w-fit"><ScanLine className="h-4 w-4" />Scan project files</Button>
                    <div id="inventory-result" className={inventoryResult ? "result-panel" : "hidden"} role="status" aria-live="polite" tabIndex={-1} hidden={!inventoryResult}>{inventoryResult}</div>
                  </form>
                </div>
                <aside className="evidence-rail" aria-label="Inventory outputs"><div className="evidence-panel"><div className="evidence-title"><ShieldCheck className="h-4 w-4" />Scan behavior</div><ul><li><CheckCircle2 />File contents are not modified</li><li><CheckCircle2 />Checksums identify duplicates</li><li><CheckCircle2 />History and versions remain immutable</li></ul></div><div className="evidence-panel"><div className="evidence-title"><Activity className="h-4 w-4" />Latest result</div>{inventoryResult ? <pre>{inventoryResult}</pre> : <p>Run an inventory scan to see manifest details.</p>}</div></aside>
              </div>
            </TabsContent>
          </Tabs>
        </section>

        {/* Files - NEW */}
        <Card id="files" className={`${activeView === "files" ? "block" : "hidden"} workspace-card major-panel`}>
          <CardHeader className="flex flex-row items-center justify-between">
            <div><CardTitle className="flex items-center gap-1.5"><Database className="w-4 h-4 text-primary" />File browser & versions</CardTitle><CardDescription className="text-xs">Search, history and version restore</CardDescription></div>
            <Badge className="bg-emerald-100 text-emerald-700">Active</Badge>
          </CardHeader>
          <CardContent className="space-y-3">
            {!selectedId ? <Alert><AlertCircle className="w-4 h-4" /><AlertDescription className="text-xs">Select a project to browse its files.</AlertDescription></Alert> : (
              <>
                <div className="flex gap-2">
                  <Input placeholder="Search file name / MIME / checksum (use API /files/search)" value={fileSearch} onChange={e=>setFileSearch(e.target.value)} className="flex-1" />
                  <Button variant="secondary" onClick={handleFileSearch}><Search className="w-3.5 h-3.5 mr-1" />Search</Button>
                  <Button variant="outline" onClick={()=>refreshFiles(selectedId)}>Refresh</Button>
                </div>
                <div className="overflow-x-auto border rounded-xl">
                  <Table>
                    <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Storage key</TableHead><TableHead>MIME</TableHead><TableHead>Size</TableHead><TableHead>Status</TableHead><TableHead></TableHead></TableRow></TableHeader>
                    <TableBody>
                      {files.length===0 ? <TableRow><TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-6">No active files. Scan inventory or upload.</TableCell></TableRow> :
                        files.map(f=>(
                          <TableRow key={f.id} className={selectedFile?.id===f.id ? "bg-primary/10" : ""}>
                            <TableCell className="font-medium max-w-[160px] truncate">{f.name}</TableCell>
                            <TableCell className="font-mono text-xs max-w-[200px] truncate">{f.storage_key}</TableCell>
                            <TableCell className="text-xs">{f.media_type}</TableCell>
                            <TableCell className="text-xs">{(f.size_bytes/1024).toFixed(1)} KB</TableCell>
                            <TableCell><Badge variant={f.status==="active" ? "default" : "secondary"} className={f.status==="active" ? "bg-emerald-100 text-emerald-700" : ""}>{f.status}</Badge></TableCell>
                            <TableCell><Button size="sm" variant="outline" onClick={()=>openFileDetail(f)}>Detail</Button></TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                </div>
                {selectedFile && (
                  <div className="grid md:grid-cols-2 gap-3">
                    <Card className="border-dashed">
                      <CardHeader className="pb-2"><CardTitle className="text-sm">History · {selectedFile.name}</CardTitle><CardDescription className="text-xs font-mono">{selectedFile.id}</CardDescription></CardHeader>
                      <CardContent className="space-y-2 max-h-[220px] overflow-auto text-xs">
                        {fileHistory.length===0 ? <p className="text-muted-foreground">No history.</p> : fileHistory.map((h:any)=>(
                          <div key={h.id} className="border-b py-1.5 last:border-0">
                            <div className="font-bold">{h.event_code} · {h.status}</div>
                            <div className="text-muted-foreground">{h.storage_key} · {h.checksum_sha256.slice(0,12)}… · {new Date(h.observed_at).toLocaleString()}</div>
                          </div>
                        ))}
                      </CardContent>
                    </Card>
                    <Card className="border-dashed">
                      <CardHeader className="pb-2"><CardTitle className="text-sm">Versions</CardTitle><CardDescription className="text-xs">Immutable snapshots · restore never overwrites original</CardDescription></CardHeader>
                      <CardContent className="space-y-2 max-h-[220px] overflow-auto text-xs">
                        {fileVersions.length===0 ? <p className="text-muted-foreground">No versions.</p> : fileVersions.map((v:any)=>(
                          <div key={v.id} className="flex items-center justify-between border-b py-1.5 last:border-0">
                            <div><div className="font-bold">v{v.version_number} {v.is_original ? "(original)" : ""}</div><div className="text-muted-foreground">{v.checksum_sha256.slice(0,12)}… · {v.size_bytes} bytes</div></div>
                            <Button size="sm" variant="secondary" onClick={()=>handleRestoreVersion(v.version_number)}>Restore</Button>
                          </div>
                        ))}
                      </CardContent>
                    </Card>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* Recovery */}
        <Card id="recovery" className={`${activeView === "recovery" ? "block" : "hidden"} workspace-card major-panel`}>
          <CardHeader className="flex flex-row items-start justify-between">
            <div><p className="panel-label">Recovery</p><CardTitle className="flex items-center gap-1.5"><RefreshCw className="w-4 h-4 text-primary" />Backup and restore</CardTitle><CardDescription className="text-xs">Create a checksummed project archive, re-verify every manifest entry, and restore a safe copy without replacing the original.</CardDescription></div>
            <span className="panel-icon"><ArchiveRestore className="h-4 w-4" /></span>
          </CardHeader>
          <CardContent className="grid md:grid-cols-[1.2fr_1fr] gap-6">
            <div className="space-y-2 text-xs text-muted-foreground">
              <div className="flex flex-wrap gap-1"><Badge variant="outline">SHA-256 manifest</Badge><Badge variant="outline">Originals preserved</Badge><Badge variant="outline">No-overwrite restore</Badge></div>
              <div className="quiet-result flex gap-2"><CheckCircle2 className="w-4 h-4 text-primary mt-0.5" /><p><strong>Safe by default.</strong> Restores use a new destination and never overwrite the source project.</p></div>
            </div>
            <div className="grid gap-3">
              <div className="grid gap-1.5"><Label htmlFor="backup-project-id" className="text-xs">Project ID</Label><Input id="backup-project-id" placeholder="Select a project below" required defaultValue={selectedId} /></div>
              <div className="flex gap-2"><Button id="backup-create" onClick={handleBackupCreate} className="flex-1">Create backup</Button><Button id="backup-list" variant="secondary" className="flex-1" onClick={handleBackupList}>List backups</Button></div>
              <div className="grid gap-1.5"><Label htmlFor="backup-id" className="text-xs">Backup ID</Label><Input id="backup-id" placeholder="Create or select a backup" required /></div>
              <Button id="backup-verify" variant="secondary" onClick={handleBackupVerify}>Verify backup</Button>
              <div className="grid gap-1.5"><Label htmlFor="backup-destination" className="text-xs">New restore destination</Label><Input id="backup-destination" defaultValue="restored/sample-project-check" required /></div>
              <Button id="backup-restore" onClick={handleBackupRestore}>Restore safe copy</Button>
              <div id="backup-result" className={`text-xs whitespace-pre-wrap ${backupResult ? "quiet-result block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!backupResult}>{backupResult}</div>
            </div>
          </CardContent>
        </Card>

        {/* Knowledge base - enhanced */}
        <Card id="knowledge-base" className={`${activeView === "knowledge" ? "block" : "hidden"} workspace-card major-panel`}>
          <CardHeader className="flex flex-row items-center justify-between">
            <div><CardTitle className="flex items-center gap-1.5"><Library className="w-4 h-4 text-primary" />Company Knowledge Base</CardTitle><CardDescription className="text-xs">Register metadata for SOPs, prompt banks, style guides, and project rules. New sources stay pending until a supervisor or administrator approves them.</CardDescription></div>
            <Button id="knowledge-files-refresh" variant="secondary" size="sm" onClick={()=>refreshKnowledgeFiles(selectedId)}><RefreshCw className="w-3.5 h-3.5 mr-1" />Refresh files</Button>
          </CardHeader>
          <CardContent className="space-y-4">
            <Tabs defaultValue="register" className="w-full">
              <TabsList className="grid grid-cols-4 w-full">
                <TabsTrigger value="register">Register</TabsTrigger>
                <TabsTrigger value="ingest">Ingest</TabsTrigger>
                <TabsTrigger value="search">Search</TabsTrigger>
                <TabsTrigger value="answer">Answer</TabsTrigger>
              </TabsList>

              <TabsContent value="register" className="space-y-3 mt-4">
                <form id="knowledge-source-form" onSubmit={handleKnowledgeRegister} className="grid gap-3">
                  <div className="grid md:grid-cols-2 gap-3">
                    <div className="grid gap-1.5"><Label htmlFor="knowledge-project-id" className="text-xs">Project ID</Label><Input id="knowledge-project-id" name="project_id" placeholder="Select a project below" readOnly required defaultValue={selectedId} /></div>
                    <div className="grid gap-1.5"><Label htmlFor="knowledge-owner-id" className="text-xs">Accountable owner ID</Label><Input id="knowledge-owner-id" name="owner_id" placeholder="Selected project owner" readOnly required defaultValue={selectedProject?.owner_id || ""} /></div>
                  </div>
                  <div className="grid gap-1.5"><Label htmlFor="knowledge-file-id" className="text-xs">Source file</Label>
                    <select id="knowledge-file-id" name="file_id" required defaultValue="" className="h-10 w-full rounded-lg border border-input bg-white px-3 text-sm shadow-sm focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-ring/20">
                      <option value="" disabled>Select an active project file</option>
                      {files.map(f=><option key={f.id} value={f.id}>{f.name} · {f.storage_key}</option>)}
                    </select>
                  </div>
                  <div className="grid gap-1.5"><Label htmlFor="knowledge-source-title" className="text-xs">Source title</Label><Input id="knowledge-source-title" name="title" placeholder="e.g. Customer support SOP" required maxLength={200} /></div>
                  <div className="grid md:grid-cols-2 gap-3">
                    <div className="grid gap-1.5"><Label htmlFor="knowledge-source-type" className="text-xs">Source type</Label>
                      <select id="knowledge-source-type" name="source_type" required className="h-10 w-full rounded-lg border border-input bg-white px-3 text-sm shadow-sm focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-ring/20">
                        <option value="sop">SOP</option><option value="prompt_bank">Prompt bank</option><option value="style_guide">Style guide</option><option value="project_rule">Project rule</option>
                      </select>
                    </div>
                    <div className="grid gap-1.5"><Label htmlFor="knowledge-sensitivity" className="text-xs">Sensitivity</Label>
                      <select id="knowledge-sensitivity" name="sensitivity" required className="h-10 w-full rounded-lg border border-input bg-white px-3 text-sm shadow-sm focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-ring/20">
                        <option value="internal">Internal</option><option value="public">Public</option><option value="confidential">Confidential</option><option value="restricted">Restricted</option>
                      </select>
                    </div>
                  </div>
                  <Button id="knowledge-register" type="submit" disabled={!selectedId}>Register source for review</Button>
                </form>
                <div id="knowledge-result" className={`text-xs whitespace-pre-wrap ${knowledgeResult ? "quiet-result block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!knowledgeResult}>{knowledgeResult}</div>
                <div id="knowledge-sources-list">
                  {knowledgeSources.length===0 ? <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed p-4"><div><strong className="text-sm">No knowledge sources yet</strong><p className="mt-1 text-xs text-muted-foreground">{selectedId ? "Upload or choose an active project file, then register it for review." : "Select a project to view and register its knowledge sources."}</p></div>{selectedId && <Button type="button" variant="outline" size="sm" onClick={() => openView("operations")}>Open file operations</Button>}</div> :
                    <div className="overflow-x-auto border rounded-xl">
                      <Table className="knowledge-table">
                        <TableHeader><TableRow><TableHead>Source</TableHead><TableHead>Type</TableHead><TableHead>Sensitivity</TableHead><TableHead>Review</TableHead><TableHead>Actions</TableHead></TableRow></TableHeader>
                        <TableBody>
                          {knowledgeSources.map(s=>(
                            <TableRow key={s.id}>
                              <TableCell><span className="font-bold block">{s.title}</span><span className="font-mono text-xs">{s.file_name}</span></TableCell>
                              <TableCell className="text-xs">{s.source_type}</TableCell>
                              <TableCell className="text-xs">{s.sensitivity}</TableCell>
                              <TableCell><Badge className={s.approval_status==="approved" ? "bg-emerald-100 text-emerald-700" : s.approval_status==="pending" ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}>{s.approval_status}</Badge></TableCell>
                              <TableCell className="flex gap-1">
                                {s.approval_status==="pending" && <><Button size="sm" variant="secondary" className="h-7 text-xs" onClick={()=>handleReview(s.id, "approved")}>Approve</Button><Button size="sm" variant="outline" className="h-7 text-xs" onClick={()=>handleReview(s.id, "rejected")}>Reject</Button></>}
                                {s.approval_status==="approved" && <Button size="sm" variant="outline" className="h-7 text-xs" onClick={()=>handleIngest(s.id)}>Ingest</Button>}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  }
                </div>
              </TabsContent>

              <TabsContent value="ingest" className="space-y-3 mt-4">
                <Alert className="border-teal-200 bg-teal-50/60"><FileText className="w-4 h-4 text-primary" /><AlertDescription className="text-xs"><strong>Document Ingestion:</strong> Extracts approved text, chunks with heading/location, stores deterministic vectors. Endpoint <code className="bg-white px-1 rounded">POST /knowledge-sources/{"{id}"}/ingest</code>. Only approved sources with active files.</AlertDescription></Alert>
                {ingestResult && <div className="quiet-result text-xs whitespace-pre-wrap">{ingestResult}</div>}
                <div className="overflow-x-auto border rounded-xl">
                  <Table>
                    <TableHeader><TableRow><TableHead>Approved sources</TableHead><TableHead>File</TableHead><TableHead>Action</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {knowledgeSources.filter(s=>s.approval_status==="approved").length===0 ? <TableRow><TableCell colSpan={3} className="text-center text-sm text-muted-foreground py-6">No approved sources. Approve one in Register tab.</TableCell></TableRow> :
                        knowledgeSources.filter(s=>s.approval_status==="approved").map(s=>(
                          <TableRow key={s.id}><TableCell className="font-medium">{s.title}</TableCell><TableCell className="text-xs">{s.file_name} · {s.file_storage_key}</TableCell><TableCell><Button size="sm" onClick={()=>handleIngest(s.id)}>Ingest</Button></TableCell></TableRow>
                        ))}
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>

              <TabsContent value="search" className="space-y-3 mt-4">
                <Alert className="border-teal-200 bg-teal-50/60"><Search className="w-4 h-4 text-primary" /><AlertDescription className="text-xs"><strong>Semantic Search:</strong> 256-dim local embedding, cosine ranking, newest-ingestion dedup, project + approval + active-file filtering. Staff sees own project only; supervisor/admin global. <code className="bg-white px-1 rounded">POST /knowledge-search</code></AlertDescription></Alert>
                <form onSubmit={handleSearch} className="flex gap-2">
                  <Input name="query" placeholder="Search approved, active source passages (e.g. 'backup recovery')" required className="flex-1" />
                  <Button type="submit"><Search className="w-4 h-4 mr-1" />Search</Button>
                </form>
                {searchMeta && <div className="text-xs text-muted-foreground">{searchMeta}</div>}
                {searchResults.length===0 ? <p className="border border-dashed rounded-xl p-4 text-sm text-muted-foreground text-center">No results yet. Ingest an approved source then search.</p> :
                  <div className="grid gap-2">
                    {searchResults.map((r:any)=>(
                      <Card key={r.chunk_id} className="border-teal-100">
                        <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2">{r.title} <Badge variant="outline" className="ml-auto text-[0.65rem]">score {r.score.toFixed(3)}</Badge></CardTitle><CardDescription className="text-xs">{r.heading || "—"} · {r.location} · {r.file_name} · lines {r.line_start}-{r.line_end} · {r.source_type}/{r.sensitivity}</CardDescription></CardHeader>
                        <CardContent><p className="text-sm whitespace-pre-wrap bg-muted/40 p-2.5 rounded-xl">{r.content}</p></CardContent>
                      </Card>
                    ))}
                  </div>
                }
              </TabsContent>

              <TabsContent value="answer" className="space-y-3 mt-4">
                <Alert className="border-border bg-card">
                  <ShieldCheck className="w-4 h-4" />
                  <AlertDescription className="text-xs">
                    <strong>Grounded answers:</strong> the MVP quotes only approved, active source evidence visible in this project. If the evidence is not strong enough, it refuses instead of guessing.
                  </AlertDescription>
                </Alert>
                <form id="knowledge-answer-form" onSubmit={handleAnswer} className="grid md:grid-cols-[1fr_auto] gap-3">
                  <div className="grid gap-1.5">
                    <Label htmlFor="knowledge-answer-query" className="text-xs">Question</Label>
                    <Input id="knowledge-answer-query" name="query" placeholder="Ask about an approved company rule" required maxLength={500} />
                    <p className="text-[0.68rem] text-muted-foreground">Answers are extractive and source-linked; they do not apply document text as system instructions.</p>
                  </div>
                  <Button id="knowledge-answer-submit" type="submit" disabled={!selectedId || answerLoading} className="md:self-end">
                    <ShieldCheck className="w-4 h-4 mr-1" />{answerLoading ? "Checking evidence…" : "Ask from evidence"}
                  </Button>
                </form>
                {answerError && <div id="knowledge-answer-error" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{answerError}</div>}
                {!answerResponse && !answerError && <p className="border border-dashed rounded-xl p-4 text-sm text-muted-foreground text-center">Ask a question after ingesting an approved source.</p>}
                {answerResponse && (
                  <div id="knowledge-answer-result" className="grid gap-3" aria-live="polite">
                    <div className={`rounded-2xl border p-4 ${answerResponse.status === "answered" ? "border-teal-200 bg-teal-50" : "border-amber-200 bg-amber-50"}`}>
                      <div className="flex flex-wrap items-center gap-2 mb-3">
                        <Badge className={answerResponse.status === "answered" ? "bg-teal-700 text-white" : "bg-amber-500 text-amber-950"}>{answerResponse.status}</Badge>
                        <span className="text-[0.68rem] text-muted-foreground">{answerResponse.answer_engine} · {answerResponse.retrieved_count} {answerResponse.status === "answered" ? "evidence" : "candidate"} passage{answerResponse.retrieved_count === 1 ? "" : "s"}</span>
                      </div>
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{answerResponse.answer}</p>
                      {answerResponse.refusal_reason && <p className="mt-3 text-xs text-amber-800">Refusal: {answerResponse.refusal_reason.replaceAll("_", " ")}</p>}
                    </div>
                    {answerResponse.citations.length > 0 && (
                      <div className="grid gap-2">
                        <div className="flex items-center justify-between">
                          <p className="text-[0.68rem] font-extrabold tracking-widest uppercase text-teal-700">Evidence rail</p>
                          <span className="text-[0.68rem] text-muted-foreground">{answerResponse.citation_count} citation{answerResponse.citation_count === 1 ? "" : "s"}</span>
                        </div>
                        {answerResponse.citations.map(citation=>(
                          <Card key={citation.chunk_id} className="border-teal-200 bg-white">
                            <CardHeader className="pb-2">
                              <CardTitle className="text-sm flex items-center gap-2"><Badge variant="outline" className="border-teal-300 text-teal-800">[{citation.citation_number}]</Badge>{citation.title}<Badge variant="outline" className="ml-auto text-[0.65rem]">score {citation.score.toFixed(3)}</Badge></CardTitle>
                              <CardDescription className="text-xs">{citation.heading || "Source passage"} · {citation.location} · {citation.file_name} · lines {citation.line_start}-{citation.line_end}</CardDescription>
                            </CardHeader>
                            <CardContent><p className="text-sm whitespace-pre-wrap bg-muted/40 p-2.5 rounded-xl">{citation.excerpt}</p><p className="text-[0.68rem] text-muted-foreground mt-2 font-mono">{citation.file_storage_key}</p></CardContent>
                          </Card>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

      </main>

      <Dialog open={confirm.open} onOpenChange={(open)=>!open && setConfirm(c=>{ c.resolve?.(false); return {...c, open:false}})}>
        <DialogContent id="confirm-dialog" className="sm:max-w-[28rem]" aria-describedby="confirm-message">
          <DialogHeader><DialogTitle id="confirm-title">{confirm.title}</DialogTitle><DialogDescription id="confirm-message" className="text-sm">{confirm.msg}</DialogDescription></DialogHeader>
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="secondary" onClick={()=>{ confirm.resolve?.(false); setConfirm(c=>({...c, open:false})) }}>Cancel</Button>
            <Button id="confirm-accept" variant="destructive" onClick={()=>{ confirm.resolve?.(true); setConfirm(c=>({...c, open:false})) }}>{confirm.label}</Button>
          </div>
        </DialogContent>
      </Dialog>

      <footer className="app-footer">
        <div className="flex items-center gap-3">
          <span className="w-8 h-8 rounded-lg bg-[#0e2a36] text-white grid place-items-center font-black">C</span>
          <div>
            <strong className="text-foreground">CCL AI Suite</strong> — Secure Operations Platform
            <br/><span className="text-[0.70rem]">Local operations · Audited · Recoverable</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <a href="/docs" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-foreground">API Docs <ExternalLink className="w-3 h-3" /></a>
          <span className="inline-flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> System operational</span>
        </div>
      </footer>
    </div>
  )
}
