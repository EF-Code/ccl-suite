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
import { apiRequest, getOwnerId, setOwnerId, type Project, type FileRecord, type KnowledgeSource } from "@/lib/api"
import {
  HeartPulse, Users, FolderKanban, Files, Search, RefreshCw, ShieldCheck,
  Database, FileText, ArrowLeftRight, Library,
  AlertCircle, ChevronRight, ExternalLink, CheckCircle2
} from "lucide-react"

// Helpers
function escapeForTest(v: string) { return v }

export default function App() {
  // Global
  const [health, setHealth] = useState<{ ok: boolean; text: string; detail: string }>({ ok: false, text: "Checking connection…", detail: "Waiting for /health" })
  const [healthBadge, setHealthBadge] = useState("Checking API…")
  const [flash, setFlash] = useState<{ msg: string; kind: "success" | "error" | null }>({ msg: "", kind: null })
  const [showFlash, setShowFlash] = useState(false)

  const [projects, setProjects] = useState<Project[]>([])
  const [selectedId, setSelectedId] = useState("")
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)

  // Forms + results
  const [ownerResult, setOwnerResult] = useState("")
  const [folderResult, setFolderResult] = useState("")
  const [inventoryResult, setInventoryResult] = useState("")
  const [conversionResult, setConversionResult] = useState("")
  const [organizerResult, setOrganizerResult] = useState("")
  const [backupResult, setBackupResult] = useState("")
  const [knowledgeResult, setKnowledgeResult] = useState("")
  const [ingestResult, setIngestResult] = useState("")
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searchMeta, setSearchMeta] = useState("")
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
      setSelectedId(proj.id); setSelectedProject(proj)
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

  return (
    <div className="min-h-screen">
      <a className="skip-link" href="#main-content">Skip to main content</a>

      {/* Production Topbar */}
      <header className="sticky top-0 z-30 bg-[#0e2a36] border-b border-white/10 shadow-[0_4px_20px_rgba(8,22,31,0.12)]">
        <div className="mx-auto max-w-[1280px] px-4 lg:px-8 h-[56px] flex items-center justify-between gap-4">
          <a className="flex items-center gap-3" href="/" aria-label="CCL AI Suite home">
            <span className="w-9 h-9 rounded-xl bg-white text-[#0e2a36] grid place-items-center font-black text-[1.15rem] shadow-md">C</span>
            <span className="hidden sm:block">
              <strong className="block text-[0.95rem] leading-none tracking-tight text-white">CCL AI Suite</strong>
              <small className="text-[0.70rem] text-white/60 tracking-wide">Operations Platform</small>
            </span>
          </a>
          <nav className="flex items-center gap-2" aria-label="Application links">
            <a className="hidden md:inline-flex items-center gap-1.5 text-xs font-bold text-white/70 hover:text-white px-2.5 py-1.5 rounded-lg hover:bg-white/10 transition-colors" href="#projects">Projects</a>
            <a className="hidden md:inline-flex items-center gap-1.5 text-xs font-bold text-white/70 hover:text-white px-2.5 py-1.5 rounded-lg hover:bg-white/10 transition-colors" href="#file-operations">Files</a>
            <a className="hidden md:inline-flex items-center gap-1.5 text-xs font-bold text-white/70 hover:text-white px-2.5 py-1.5 rounded-lg hover:bg-white/10 transition-colors" href="#knowledge-base">Knowledge</a>
            <span id="health-badge" className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[0.68rem] font-extrabold border ${health.ok ? "bg-emerald-500 text-white border-emerald-400" : "bg-amber-500 text-white border-amber-400"}`} role="status" aria-live="polite">
              <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" /> {healthBadge}
            </span>
            <a className="inline-flex items-center gap-1.5 text-xs font-bold bg-white text-[#0e2a36] px-3.5 py-2 rounded-full hover:bg-white/90 shadow-sm" href="/docs" target="_blank" rel="noreferrer">API docs <ExternalLink className="w-3 h-3" /></a>
          </nav>
        </div>
      </header>

      <main id="main-content" className="mx-auto max-w-[1280px] px-4 lg:px-8 py-8">
        {/* Production Hero — Operate mode: task-first, no prototype language */}
        <section className="relative overflow-hidden rounded-[1.5rem] bg-[#0e2a36] text-white mb-6">
          <div className="absolute inset-0">
            <div className="absolute -top-24 -right-24 w-[520px] h-[520px] rounded-full bg-[radial-gradient(circle_at_center,rgba(20,121,111,0.22),transparent_70%)]" />
            <div className="absolute -bottom-32 -left-24 w-[640px] h-[640px] rounded-full bg-[radial-gradient(circle_at_center,rgba(232,121,93,0.14),transparent_70%)]" />
            <div className="absolute inset-0 opacity-[0.04]" style={{backgroundImage: `linear-gradient(rgba(255,255,255,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.4) 1px, transparent 1px)`, backgroundSize: '32px 32px'}} />
          </div>
          <div className="relative grid lg:grid-cols-[1.15fr_0.85fr] gap-6 p-6 lg:p-8">
            <div>
              <div className="inline-flex items-center gap-2 text-[0.68rem] font-extrabold tracking-[0.14em] uppercase text-white/60 mb-3">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_0_4px_rgba(52,211,153,0.2)]" /> Secure operations
              </div>
              <h1 id="page-title" className="text-[clamp(2.2rem,4.5vw,2.9rem)] font-black tracking-[-0.03em] leading-[0.95] mb-3">
                Control your<br/>operations, end-to-end.
              </h1>
              <p className="text-white/70 max-w-[36rem] leading-relaxed">
                Create an owner, open a project, and run file, knowledge and recovery workflows — all audited, reversible, and scoped to your workspace.
              </p>
              <div className="flex flex-wrap gap-2.5 mt-5">
                <a className="inline-flex items-center gap-1.5 bg-white text-[#0e2a36] px-5 py-2.5 rounded-full text-sm font-extrabold shadow hover:bg-white/90" href="#setup">Start setup <ChevronRight className="w-4 h-4" /></a>
                <a className="inline-flex items-center gap-1.5 bg-white/10 text-white border border-white/20 px-5 py-2 rounded-full text-sm font-bold hover:bg-white/15 backdrop-blur" href="#projects">View projects</a>
              </div>
            </div>
            <div className="grid grid-cols-3 lg:grid-cols-3 gap-3 content-start">
              {[
                { k: "Projects", v: String(projects.length), sub: `${projects.filter(p=>p.status==="active").length} active`, icon: FolderKanban },
                { k: "Files", v: String(files.length), sub: "indexed", icon: Files },
                { k: "Sources", v: String(knowledgeSources.length), sub: `${knowledgeSources.filter(s=>s.approval_status==="approved").length} approved`, icon: Library },
              ].map(s=>(
                <div key={s.k} className="rounded-2xl bg-white/[0.06] border border-white/10 p-3 backdrop-blur">
                  <div className="flex items-center gap-2 text-white/60 mb-2"><s.icon className="w-3.5 h-3.5" /><span className="text-[0.68rem] font-extrabold tracking-widest uppercase">{s.k}</span></div>
                  <div className="text-[1.6rem] font-black leading-none text-white">{s.v}</div>
                  <div className="text-xs text-white/60 mt-1">{s.sub}</div>
                </div>
              ))}
              <div className="col-span-3 rounded-2xl bg-white text-[#0e2a36] p-3 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="w-8 h-8 rounded-xl bg-emerald-500 text-white grid place-items-center"><ShieldCheck className="w-4 h-4" /></span>
                  <div><div className="text-xs font-extrabold">Audited & recoverable</div><div className="text-[0.70rem] text-muted-foreground">Backups verified · journals reversible</div></div>
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground" />
              </div>
            </div>
          </div>
        </section>

        {/* Flash */}
        <div id="flash" className={`rounded-xl border px-3 py-2.5 text-sm mb-4 shadow-sm ${showFlash ? "block" : "hidden"} ${flash.kind==="error" ? "bg-red-50 border-red-200 text-red-700" : "bg-emerald-50 border-emerald-200 text-emerald-800"}`} role={flash.kind==="error" ? "alert" : "status"} aria-live="polite" hidden={!showFlash}>{flash.msg}</div>

        <nav className="flex flex-wrap items-center gap-1 bg-card border border-border/60 rounded-xl p-1.5 mb-4 shadow-sm" aria-label="Dashboard sections">
          <span className="text-[0.70rem] font-extrabold text-muted-foreground px-2">Jump to</span>
          <a className="text-xs font-bold px-2.5 py-1.5 rounded-lg hover:bg-accent" href="#setup">Setup</a>
          <a className="text-xs font-bold px-2.5 py-1.5 rounded-lg hover:bg-accent" href="#projects">Projects</a>
          <a className="text-xs font-bold px-2.5 py-1.5 rounded-lg hover:bg-accent" href="#file-operations">Operations</a>
          <a className="text-xs font-bold px-2.5 py-1.5 rounded-lg hover:bg-accent" href="#files">Files</a>
          <a className="text-xs font-bold px-2.5 py-1.5 rounded-lg hover:bg-accent" href="#knowledge-base">Knowledge</a>
          <a className="text-xs font-bold px-2.5 py-1.5 rounded-lg hover:bg-accent" href="#recovery">Recovery</a>
        </nav>

        {/* Workflow steps — production */}
        <Card className="mb-4 card-elevated card-accent">
          <CardHeader className="pb-2 flex flex-row items-end justify-between">
            <div><p className="text-[0.68rem] font-extrabold tracking-widest uppercase text-teal-700">A clear path</p><CardTitle className="text-[1.1rem]">Complete the steps in order</CardTitle></div>
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
                <li key={s.n}><a href={s.href} className="flex gap-2.5 border rounded-xl p-3 hover:bg-accent transition-colors">
                  <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground grid place-items-center text-xs font-extrabold">{s.n}</span>
                  <span><strong className="block text-xs">{s.t}</strong><small className="text-[0.70rem] text-muted-foreground">{s.d}</small></span>
                </a></li>
              ))}
            </ol>
          </CardContent>
        </Card>

        {/* Active project context - preserve ids */}
        <div id="workspace-context" className={`flex flex-col md:flex-row items-start md:items-center gap-3 border rounded-2xl p-3.5 mb-6 shadow-sm ${selectedId ? "bg-[#e6f2ee] border-teal-300 shadow" : "bg-card card-elevated"}`}>
          <div className="w-11 h-11 rounded-xl bg-[#e6f2ee] grid place-items-center text-teal-800">⌂</div>
          <div className="flex-1 min-w-0">
            <p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-teal-700">Active project</p>
            <h2 id="active-project-title" className="text-[1rem] font-bold truncate">{selectedProjectName}</h2>
            <p id="active-project-detail" className="text-xs text-muted-foreground truncate">Folder: {selectedProject?.storage_slug || "—"} · Owner: {selectedProject?.owner_id || "not assigned"}</p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span id="active-project-status" className={`text-[0.68rem] font-extrabold px-2.5 py-1 rounded-full ${selectedId ? "bg-emerald-100 text-emerald-700" : "bg-muted text-muted-foreground"}`}>{selectedId ? "Ready to operate" : "Waiting for selection"}</span>
            <span className="text-[0.60rem] font-extrabold tracking-widest uppercase text-muted-foreground">Project ID</span>
            <code id="active-project-id" className="text-[0.68rem] text-muted-foreground max-w-[14rem] truncate bg-muted px-1.5 py-0.5 rounded">{selectedId || "—"}</code>
          </div>
          <a className="inline-flex items-center justify-center bg-secondary text-secondary-foreground px-3 py-2 rounded-xl text-xs font-bold" href="#projects">Choose project</a>
        </div>

        {/* Setup grid */}
        <section id="setup" className="mb-6">
          <div className="flex items-end justify-between mb-3">
            <div><p className="text-[0.68rem] font-extrabold tracking-widest uppercase text-teal-700">Workspace controls</p><h2 className="text-xl font-bold tracking-tight">Set up your workspace</h2></div>
            <p className="hidden md:block text-xs text-muted-foreground">Start here when the API is online or when you need to prepare a new project.</p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Health - preserve ids */}
            <Card id="service-health" className="card-elevated card-accent border-teal-100/60">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-muted-foreground">01 · Service</p><CardTitle className="text-[1rem] flex items-center gap-1.5"><HeartPulse className="w-4 h-4 text-teal-600" />System health</CardTitle></div>
                <span className="w-8 h-8 rounded-lg bg-[#e6f2ee] grid place-items-center">✦</span>
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
            <Card id="owner-setup" className="card-elevated">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-muted-foreground">02 · Identity</p><CardTitle className="text-[1rem] flex items-center gap-1.5"><Users className="w-4 h-4" />Development owner</CardTitle></div>
                <span className="w-8 h-8 rounded-lg bg-[#e6f2ee] grid place-items-center">◎</span>
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
                <div id="user-result" className={`rounded-xl border p-2.5 text-xs whitespace-pre-wrap ${ownerResult ? "bg-emerald-50 border-emerald-200 text-emerald-800 block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!ownerResult}>{ownerResult}</div>
              </CardContent>
            </Card>

            {/* Project - preserve #project-form, #owner-id */}
            <Card id="project-setup" className="card-elevated">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-muted-foreground">03 · Workspace</p><CardTitle className="text-[1rem] flex items-center gap-1.5"><FolderKanban className="w-4 h-4" />Register a project</CardTitle></div>
                <span className="w-8 h-8 rounded-lg bg-[#e6f2ee] grid place-items-center">＋</span>
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
            <Card id="folder-setup" className="card-elevated">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-muted-foreground">04 · Filesystem</p><CardTitle className="text-[1rem] flex items-center gap-1.5"><FolderKanban className="w-4 h-4" />Generate project folders</CardTitle></div>
                <span className="w-8 h-8 rounded-lg bg-[#e6f2ee] grid place-items-center">▦</span>
              </CardHeader>
              <CardContent className="space-y-3">
                <p id="folder-form-help" className="text-xs text-muted-foreground">Select a project first, then create its safe incoming, working, output, and archive layout.</p>
                <form id="folder-form" onSubmit={handleGenerateFolder} className="grid gap-3" aria-describedby="folder-form-help">
                  <div className="grid gap-1.5"><Label htmlFor="project-folder-name" className="text-xs">Project folder name</Label><Input id="project-folder-name" name="project_name" placeholder="Select a project below" required maxLength={100} defaultValue={selectedProject?.storage_slug || ""} /></div>
                  <Button type="submit">Generate folder layout</Button>
                </form>
                <div id="folder-result" className={`rounded-xl border p-2.5 text-xs whitespace-pre-wrap ${folderResult ? "bg-emerald-50 border-emerald-200 block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!folderResult}>{folderResult}</div>
              </CardContent>
            </Card>

            {/* Inventory - preserve #inventory-form, #inventory-project-id, #inventory-result */}
            <Card id="inventory" className="card-elevated">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-muted-foreground">05 · Inventory</p><CardTitle className="text-[1rem] flex items-center gap-1.5"><Files className="w-4 h-4" />Scan project files</CardTitle></div>
                <span className="w-8 h-8 rounded-lg bg-[#e6f2ee] grid place-items-center">≋</span>
              </CardHeader>
              <CardContent className="space-y-3">
                <p id="inventory-form-help" className="text-xs text-muted-foreground">After storage exists, create JSON and CSV manifests with MIME checks and SHA-256 hashes.</p>
                <form id="inventory-form" onSubmit={handleInventory} className="grid gap-3" aria-describedby="inventory-form-help">
                  <div className="grid gap-1.5"><Label htmlFor="inventory-project-id" className="text-xs">Project ID</Label><Input id="inventory-project-id" name="project_id" placeholder="Select a project below" required defaultValue={selectedId} /></div>
                  <Button variant="secondary" type="submit">Scan project files</Button>
                </form>
                <div id="inventory-result" className={`rounded-xl border p-2.5 text-xs whitespace-pre-wrap ${inventoryResult ? "bg-emerald-50 border-emerald-200 block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!inventoryResult}>{inventoryResult}</div>
              </CardContent>
            </Card>

            <Card className="card-elevated border-amber-200/50">
              <CardHeader className="pb-2">
                <p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-muted-foreground">Upload</p>
                <CardTitle className="text-[1rem] flex items-center gap-1.5"><ShieldCheck className="w-4 h-4" />Secure upload</CardTitle>
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
        <Card id="projects" className="mb-6 card-elevated">
          <CardHeader className="flex flex-row items-center justify-between">
            <div><p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-muted-foreground">06 · Workspaces</p><CardTitle>Registered projects</CardTitle><CardDescription className="text-xs">Choose <strong>Use project</strong> to populate every operation form with the same project.</CardDescription></div>
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
                        <TableRow key={p.id} className={p.id===selectedId ? "bg-emerald-50/60" : ""}>
                          <TableCell><span className="font-extrabold block">{escapeForTest(p.title)}</span><span className="font-mono text-xs text-muted-foreground">{p.id}</span><div className="text-xs text-muted-foreground">/{p.storage_slug}</div></TableCell>
                          <TableCell><Badge variant="secondary" className={p.status==="active" ? "bg-emerald-100 text-emerald-700" : ""}>{p.status}</Badge></TableCell>
                          <TableCell className="max-w-[260px] truncate text-xs">{p.description || "—"}</TableCell>
                          <TableCell><Button size="sm" variant={p.id===selectedId ? "default" : "secondary"} data-project-id={p.id} data-project-slug={p.storage_slug} data-project-title={p.title} data-project-owner={p.owner_id} aria-pressed={p.id===selectedId} className={`select-project ${p.id===selectedId ? "is-selected" : ""}`} onClick={()=>{
                            setSelectedId(p.id); setSelectedProject(p);
                            const setVal = (sel: string, v: string) => { const el = document.querySelector<HTMLInputElement>(sel); if (el) el.value = v; };
                            setVal("#conversion-project-id", p.id);
                            setVal("#inventory-project-id", p.id);
                            setVal("#organizer-project-id", p.id);
                            setVal("#backup-project-id", p.id);
                            setVal("#project-folder-name", p.storage_slug);
                            setVal("#knowledge-project-id", p.id);
                            setVal("#knowledge-owner-id", p.owner_id || "");
                          }}>Use project</Button></TableCell>
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
        <section id="file-operations" className="mb-6">
          <div className="flex items-end justify-between mb-3">
            <div><p className="text-[0.68rem] font-extrabold tracking-widest uppercase text-teal-700">Operate with guardrails</p><h2 className="text-xl font-bold">File operations</h2></div>
            <p className="hidden md:block text-xs text-muted-foreground">Every action is scoped to the active project shown above.</p>
          </div>
          <div className="grid lg:grid-cols-2 gap-4">
            <Card className="card-elevated">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-muted-foreground">07 · Conversion</p><CardTitle className="flex items-center gap-1.5"><ArrowLeftRight className="w-4 h-4" />Controlled conversion</CardTitle></div>
                <span className="w-8 h-8 rounded-lg bg-[#e6f2ee] grid place-items-center">↗</span>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">Convert files inside a generated project folder. The source is preserved and existing destinations are never replaced.</p>
                <div className="flex flex-wrap gap-1"><Badge variant="outline">CSV ↔ JSON</Badge><Badge variant="outline">MD ↔ TXT</Badge><Badge variant="outline">PNG ↔ JPG</Badge></div>
                <form id="conversion-form" onSubmit={handleConversion} className="grid gap-3">
                  <div className="grid gap-1.5"><Label htmlFor="conversion-project-id" className="text-xs">Project ID</Label><Input id="conversion-project-id" name="project_id" placeholder="Select a project below" required defaultValue={selectedId} /></div>
                  <div className="grid gap-1.5"><Label htmlFor="conversion-source-path" className="text-xs">Source path</Label><Input id="conversion-source-path" name="source_path" defaultValue="incoming/records.csv" required /></div>
                  <div className="grid gap-1.5"><Label htmlFor="conversion-destination-path" className="text-xs">Destination path</Label><Input id="conversion-destination-path" name="destination_path" defaultValue="output/records.json" required /></div>
                  <Button type="submit" className="bg-[#e9765b] hover:bg-[#ce6048]">Run conversion</Button>
                </form>
                <div id="conversion-result" className={`rounded-xl border p-2.5 text-xs whitespace-pre-wrap ${conversionResult ? "bg-emerald-50 border-emerald-200 block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!conversionResult}>{conversionResult}</div>
              </CardContent>
            </Card>

            <Card className="card-elevated">
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div><p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-muted-foreground">08 · Organisation</p><CardTitle className="flex items-center gap-1.5"><FolderKanban className="w-4 h-4" />Preview and apply</CardTitle></div>
                <span className="w-8 h-8 rounded-lg bg-[#e6f2ee] grid place-items-center">⇢</span>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">Preview moves from <code className="bg-muted px-1 rounded">incoming/</code> to categorised <code className="bg-muted px-1 rounded">working/</code> folders. Applying creates a rollback journal and can quarantine conflicts.</p>
                <div className="flex flex-wrap gap-1"><Badge variant="outline">Dry run first</Badge><Badge variant="outline">No overwrite</Badge><Badge variant="outline">Hash-checked rollback</Badge></div>
                <div className="grid gap-2">
                  <div className="grid gap-1.5"><Label htmlFor="organizer-project-id" className="text-xs">Project ID</Label><Input id="organizer-project-id" placeholder="Select a project below" required defaultValue={selectedId} /></div>
                  <label className="flex items-center gap-2 text-xs font-bold"><input id="quarantine-conflicts" type="checkbox" className="accent-teal-600" />Quarantine conflicts when applying</label>
                  <div className="flex gap-2">
                    <Button id="organizer-preview" variant="secondary" className="flex-1" onClick={handleOrganizerPreview}>Preview plan</Button>
                    <Button id="organizer-apply" className="flex-1 bg-[#e9765b] hover:bg-[#ce6048]" onClick={handleOrganizerApply}>Apply safe moves</Button>
                  </div>
                  <div className="grid gap-1.5"><Label htmlFor="journal-path" className="text-xs">Journal path for rollback</Label><Input id="journal-path" defaultValue="organization-journal.json" required /></div>
                  <Button id="organizer-rollback" variant="ghost" size="sm" onClick={handleRollback}>Roll back journal</Button>
                </div>
                <div id="organizer-result" className={`rounded-xl border p-2.5 text-xs whitespace-pre-wrap ${organizerResult ? "bg-emerald-50 border-emerald-200 block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!organizerResult}>{organizerResult}</div>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* Files - NEW */}
        <Card id="files" className="mb-6 card-elevated border-teal-200/60">
          <CardHeader className="flex flex-row items-center justify-between">
            <div><p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-teal-700">Asset Management</p><CardTitle className="flex items-center gap-1.5"><Database className="w-4 h-4" />File browser & versions</CardTitle><CardDescription className="text-xs">Search, history and version restore</CardDescription></div>
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
                          <TableRow key={f.id} className={selectedFile?.id===f.id ? "bg-teal-50" : ""}>
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
        <Card id="recovery" className="mb-6 card-elevated">
          <CardHeader className="flex flex-row items-start justify-between">
            <div><p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-muted-foreground">09 · Recovery</p><CardTitle className="flex items-center gap-1.5"><RefreshCw className="w-4 h-4" />Backup and restore</CardTitle><CardDescription className="text-xs">Create a checksummed project archive, re-verify every manifest entry, and restore a safe copy without replacing the original.</CardDescription></div>
            <span className="w-8 h-8 rounded-lg bg-[#e6f2ee] grid place-items-center">⟳</span>
          </CardHeader>
          <CardContent className="grid md:grid-cols-[1.2fr_1fr] gap-6">
            <div className="space-y-2 text-xs text-muted-foreground">
              <div className="flex flex-wrap gap-1"><Badge variant="outline">SHA-256 manifest</Badge><Badge variant="outline">Originals preserved</Badge><Badge variant="outline">No-overwrite restore</Badge></div>
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-2.5 flex gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5" /><p><strong>Safe by default.</strong> Restores use a new destination and never overwrite the source project.</p></div>
            </div>
            <div className="grid gap-3">
              <div className="grid gap-1.5"><Label htmlFor="backup-project-id" className="text-xs">Project ID</Label><Input id="backup-project-id" placeholder="Select a project below" required defaultValue={selectedId} /></div>
              <div className="flex gap-2"><Button id="backup-create" onClick={handleBackupCreate} className="flex-1">Create backup</Button><Button id="backup-list" variant="secondary" className="flex-1" onClick={handleBackupList}>List backups</Button></div>
              <div className="grid gap-1.5"><Label htmlFor="backup-id" className="text-xs">Backup ID</Label><Input id="backup-id" placeholder="Create or select a backup" required /></div>
              <Button id="backup-verify" variant="secondary" onClick={handleBackupVerify}>Verify backup</Button>
              <div className="grid gap-1.5"><Label htmlFor="backup-destination" className="text-xs">New restore destination</Label><Input id="backup-destination" defaultValue="restored/sample-project-check" required /></div>
              <Button id="backup-restore" className="bg-[#e9765b] hover:bg-[#ce6048]" onClick={handleBackupRestore}>Restore safe copy</Button>
              <div id="backup-result" className={`rounded-xl border p-2.5 text-xs whitespace-pre-wrap ${backupResult ? "bg-emerald-50 border-emerald-200 block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!backupResult}>{backupResult}</div>
            </div>
          </CardContent>
        </Card>

        {/* Knowledge base - enhanced */}
        <Card id="knowledge-base" className="mb-6 card-elevated">
          <CardHeader className="flex flex-row items-center justify-between">
            <div><p className="text-[0.65rem] font-extrabold tracking-widest uppercase text-teal-700">Knowledge Base</p><CardTitle className="flex items-center gap-1.5"><Library className="w-4 h-4" />Company Knowledge Base</CardTitle><CardDescription className="text-xs">Register metadata for SOPs, prompt banks, style guides, and project rules. New sources stay pending until a supervisor or administrator approves them.</CardDescription></div>
            <Button id="knowledge-files-refresh" variant="secondary" size="sm" onClick={()=>refreshKnowledgeFiles(selectedId)}><RefreshCw className="w-3.5 h-3.5 mr-1" />Refresh files</Button>
          </CardHeader>
          <CardContent className="space-y-4">
            <Tabs defaultValue="register" className="w-full">
              <TabsList className="grid grid-cols-3 w-full">
                <TabsTrigger value="register">Register</TabsTrigger>
                <TabsTrigger value="ingest">Ingest · Tue</TabsTrigger>
                <TabsTrigger value="search">Search · Wed</TabsTrigger>
              </TabsList>

              <TabsContent value="register" className="space-y-3 mt-4">
                <form id="knowledge-source-form" onSubmit={handleKnowledgeRegister} className="grid gap-3">
                  <div className="grid md:grid-cols-2 gap-3">
                    <div className="grid gap-1.5"><Label htmlFor="knowledge-project-id" className="text-xs">Project ID</Label><Input id="knowledge-project-id" name="project_id" placeholder="Select a project below" readOnly required defaultValue={selectedId} /></div>
                    <div className="grid gap-1.5"><Label htmlFor="knowledge-owner-id" className="text-xs">Accountable owner ID</Label><Input id="knowledge-owner-id" name="owner_id" placeholder="Selected project owner" readOnly required defaultValue={selectedProject?.owner_id || ""} /></div>
                  </div>
                  <div className="grid gap-1.5"><Label htmlFor="knowledge-file-id" className="text-xs">Source file</Label>
                    <select id="knowledge-file-id" name="file_id" required className="h-9 rounded-xl border bg-card px-3 text-sm">
                      <option value="" disabled selected>Select an active project file</option>
                      {files.map(f=><option key={f.id} value={f.id}>{f.name} · {f.storage_key}</option>)}
                    </select>
                  </div>
                  <div className="grid gap-1.5"><Label htmlFor="knowledge-source-title" className="text-xs">Source title</Label><Input id="knowledge-source-title" name="title" placeholder="e.g. Customer support SOP" required maxLength={200} /></div>
                  <div className="grid md:grid-cols-2 gap-3">
                    <div className="grid gap-1.5"><Label htmlFor="knowledge-source-type" className="text-xs">Source type</Label>
                      <select id="knowledge-source-type" name="source_type" required className="h-9 rounded-xl border bg-card px-3 text-sm">
                        <option value="sop">SOP</option><option value="prompt_bank">Prompt bank</option><option value="style_guide">Style guide</option><option value="project_rule">Project rule</option>
                      </select>
                    </div>
                    <div className="grid gap-1.5"><Label htmlFor="knowledge-sensitivity" className="text-xs">Sensitivity</Label>
                      <select id="knowledge-sensitivity" name="sensitivity" required className="h-9 rounded-xl border bg-card px-3 text-sm">
                        <option value="internal">Internal</option><option value="public">Public</option><option value="confidential">Confidential</option><option value="restricted">Restricted</option>
                      </select>
                    </div>
                  </div>
                  <Button id="knowledge-register" type="submit" disabled={!selectedId}>Register source for review</Button>
                </form>
                <div id="knowledge-result" className={`rounded-xl border p-2.5 text-xs whitespace-pre-wrap ${knowledgeResult ? "bg-emerald-50 border-emerald-200 block" : "hidden"}`} role="status" aria-live="polite" tabIndex={-1} hidden={!knowledgeResult}>{knowledgeResult}</div>
                <div id="knowledge-sources-list">
                  {knowledgeSources.length===0 ? <p className="border border-dashed rounded-xl p-3 text-sm text-muted-foreground">Select a project to view its knowledge sources.</p> :
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
                <Alert className="bg-card border-teal-800/50"><FileText className="w-4 h-4" /><AlertDescription className="text-xs"><strong>Document Ingestion:</strong> Extracts approved text, chunks with heading/location, stores deterministic vectors. Endpoint <code className="bg-muted px-1 rounded">POST /knowledge-sources/{"{id}"}/ingest</code>. Only approved sources with active files.</AlertDescription></Alert>
                {ingestResult && <div className="rounded-xl border bg-emerald-50 border-emerald-200 p-2.5 text-xs whitespace-pre-wrap">{ingestResult}</div>}
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
                <Alert className="bg-card border-teal-800/50"><Search className="w-4 h-4" /><AlertDescription className="text-xs"><strong>Semantic Search:</strong> 256-dim local embedding, cosine ranking, newest-ingestion dedup, project + approval + active-file filtering. Staff sees own project only; supervisor/admin global. <code className="bg-muted px-1 rounded">POST /knowledge-search</code></AlertDescription></Alert>
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
            </Tabs>
          </CardContent>
        </Card>

      </main>

      <Dialog open={confirm.open} onOpenChange={(open)=>!open && setConfirm(c=>{ c.resolve?.(false); return {...c, open:false}})}>
        <DialogContent id="confirm-dialog" className="sm:max-w-[28rem]" aria-describedby="confirm-message">
          <DialogHeader><DialogTitle id="confirm-title">{confirm.title}</DialogTitle><DialogDescription id="confirm-message" className="text-sm">{confirm.msg}</DialogDescription></DialogHeader>
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="secondary" onClick={()=>{ confirm.resolve?.(false); setConfirm(c=>({...c, open:false})) }}>Cancel</Button>
            <Button id="confirm-accept" className="bg-[#e9765b] hover:bg-[#ce6048]" onClick={()=>{ confirm.resolve?.(true); setConfirm(c=>({...c, open:false})) }}>{confirm.label}</Button>
          </div>
        </DialogContent>
      </Dialog>

      <footer className="mx-auto max-w-[1280px] px-4 lg:px-8 py-8 flex flex-col md:flex-row justify-between gap-4 text-xs text-muted-foreground border-t mt-8">
        <div className="flex items-center gap-3">
          <span className="w-8 h-8 rounded-lg bg-[#0e2a36] text-white grid place-items-center font-black">C</span>
          <div>
            <strong className="text-foreground">CCL AI Suite</strong> — Secure Operations Platform
            <br/><span className="text-[0.70rem]">© 2026 Controcontrollos · Audited · Recoverable</span>
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
