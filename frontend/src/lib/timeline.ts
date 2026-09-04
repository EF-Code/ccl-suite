export type ModuleStatus = "complete" | "current" | "upcoming" | "planned";

export interface TimelineModule {
  id: number;
  title: string;
  purpose: string;
  weeks: string;
  status: ModuleStatus;
  backendReady: boolean;
  frontendCoverage: "full" | "partial" | "placeholder";
  endpoints: string[];
  uiComponents: string[];
}

export const SIWES_TIMELINE: TimelineModule[] = [
  {
    id: 1,
    title: "Secure File Automation",
    purpose: "Organise, track, convert, protect and restore company files",
    weeks: "Foundation delivery · 17-28 Aug",
    status: "complete",
    backendReady: true,
    frontendCoverage: "full",
    endpoints: [
      "POST /project-folders",
      "POST /projects/{id}/inventory",
      "POST /projects/{id}/files · GET search/history/versions/restore",
      "PUT /projects/{id}/uploads/{key}",
      "GET /upload-policy",
      "POST /projects/{id}/organization/plan/apply/rollback",
      "POST /projects/{id}/conversions",
      "POST /projects/{id}/backups · verify · restore",
      "GET /permissions",
    ],
    uiComponents: ["Folder Gen", "Inventory", "File Browser", "Versions", "Upload", "Organization", "Conversion", "Backup"],
  },
  {
    id: 2,
    title: "Company Knowledge Base",
    purpose: "Answer questions from approved SOPs and project rules",
    weeks: "Knowledge delivery · 31 Aug - 11 Sep",
    status: "current",
    backendReady: true,
    frontendCoverage: "full",
    endpoints: [
      "POST /projects/{id}/knowledge-sources",
      "GET /projects/{id}/knowledge-sources",
      "POST /projects/{id}/knowledge-sources/{id}/review",
      "POST /projects/{id}/knowledge-sources/{id}/ingest",
      "POST /projects/{id}/knowledge-search",
    ],
    uiComponents: ["Register", "Review", "Ingest", "Semantic Search"],
  },
  {
    id: 3,
    title: "Research Evidence Agent",
    purpose: "Extract claims and flag missing or mismatched evidence",
    weeks: "Research delivery · 14-18 Sep",
    status: "upcoming",
    backendReady: false,
    frontendCoverage: "placeholder",
    endpoints: ["POST /projects/{id}/evidence/* (planned)"],
    uiComponents: ["Claim Extractor", "Evidence Register (preview)"],
  },
  {
    id: 4,
    title: "Workflow Orchestrator",
    purpose: "Move projects through controlled tasks and approvals",
    weeks: "Workflow delivery · 21 Sep - 2 Oct",
    status: "upcoming",
    backendReady: true, // workflows/approvals exist in backend
    frontendCoverage: "partial",
    endpoints: [
      "POST /projects/{id}/workflows",
      "GET /projects/{id}/workflows",
      "POST /workflows/{id}/approvals",
      "POST /approvals/{id}/decision",
    ],
    uiComponents: ["Project Intake", "States", "Approvals (read-only now)"],
  },
  {
    id: 5,
    title: "Security Dashboard",
    purpose: "Monitor project status, agent actions, failures and incidents",
    weeks: "Security delivery · 5-22 Oct",
    status: "planned",
    backendReady: true,
    frontendCoverage: "partial",
    endpoints: ["GET /security-events", "POST /security-events", "GET /projects status"],
    uiComponents: ["Security Events", "Project Metrics (preview)", "Weekly Reports"],
  },
];

export const CURRENT_WEEK = "Current capability";
export const CURRENT_PHASE = "Knowledge Base · Grounded Answers";
