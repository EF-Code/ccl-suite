---
name: CCL AI Suite
description: A controlled-ledger interface for project-scoped file, knowledge, and recovery operations.
colors:
  canvas: "hsl(220 33% 98%)"
  surface: "#ffffff"
  evidence-surface: "#fbfcfe"
  sidebar: "#101828"
  graphite: "hsl(221 39% 11%)"
  slate: "hsl(218 15% 35%)"
  cobalt: "hsl(222 71% 49%)"
  cobalt-foreground: "#ffffff"
  verified: "#047857"
  verified-surface: "#ecfdf5"
  warning: "#b45309"
  destructive: "hsl(4 74% 48%)"
  border: "hsl(220 20% 88%)"
  input-border: "hsl(220 20% 84%)"
  muted: "hsl(220 24% 96%)"
typography:
  headline:
    fontFamily: "Geist Variable, Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Geist Variable, Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "normal"
  body:
    fontFamily: "Geist Variable, Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Geist Variable, Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "normal"
  data:
    fontFamily: "Geist Mono, SFMono-Regular, Consolas, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "12px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.cobalt}"
    textColor: "{colors.cobalt-foreground}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "40px"
  button-secondary:
    backgroundColor: "{colors.muted}"
    textColor: "{colors.graphite}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "40px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.graphite}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "4px 12px"
    height: "40px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.graphite}"
    rounded: "{rounded.xl}"
    padding: "20px"
---

# Design System: CCL AI Suite

## Overview

**Creative North Star: "The Controlled Ledger"**

CCL AI Suite is a calm operations workstation with the visual discipline of financial back-office software. A dark navigation rail anchors a cool, light workspace; the active project is treated like an account ledger; and each consequential task pairs its controls with visible scope, safeguards, and outcome evidence. Brand expression comes from precision, density, and trustworthy state communication rather than decoration.

The system is designed for repeat operators. Operations is the primary workspace, while Files, Knowledge, Recovery, and Setup preserve the existing product workflows in focused destinations. The implementation follows the approved comp's shell, hierarchy, tabbed task model, and task-plus-evidence composition without fabricating the comp's sample files, counts, timestamps, or successful results.

The build workflow is mechanically closed with a `ship` finish disposition. After mobile project details, tab overflow guidance, and contextual empty states were corrected, the final read-only Impeccable reviewer returned `approve-with-notes`. Hero similarity reached 76.9% and desktop similarity 71.6%; the remaining note covers minor brand and desktop-density drift. The requested Knowledge evidence capture was subsequently refreshed without console errors. This is recorded as polish debt, not as permission to remove guarded functionality.

**Key Characteristics:**

- Persistent project scope and service readiness.
- Cool light canvas with a stable graphite navigation rail.
- Compact Geist typography and monospaced operational data.
- Cobalt actions, teal verification, and semantic warning/error color only.
- Focused task surfaces paired with an evidence rail.
- Explicit dry-run, no-overwrite, rollback, and approval boundaries.

## Colors

The palette is restrained and operational: graphite establishes the shell, cool neutrals carry the workspace, cobalt identifies action, and teal is reserved for verified state.

### Primary

- **Operator Cobalt:** The sole interactive accent for primary actions, focus rings, selected tabs, links, and the current destination.

### Secondary

- **Verified Teal:** Success, readiness, and validated safeguards only; pair quiet ink with a pale verification surface.

### Neutral

- **Graphite Rail:** Persistent desktop navigation and the strongest product anchor.
- **Cool Canvas:** The application background separating work surfaces without visual noise.
- **Ledger White:** Primary task, table, and metadata surfaces.
- **Evidence Mist:** A subtly cooler surface for safety, scope, journal, and result context.
- **Slate Ink:** Supporting descriptions, labels, and metadata; graphite remains the high-emphasis text color.
- **Hairline Border:** Structure for fields, tables, ledger cells, and bounded panels.

**The One Accent Rule.** Cobalt owns interaction; teal, amber, and red communicate state and must not compete as decorative accents.

**The Evidence Color Rule.** Never use success color to imply an operation completed when the API has not returned verified evidence.

## Typography

**Display Font:** Geist Variable (with Geist and system sans fallbacks)  
**Body Font:** Geist Variable (with Geist and system sans fallbacks)  
**Label/Mono Font:** Geist Mono (with SFMono-Regular and Consolas fallbacks)

**Character:** Compact, neutral, and highly legible. The hierarchy is intentionally product-sized: no marketing display type appears inside the workstation, and monospaced text is reserved for identifiers, paths, hashes, timestamps, and commands.

### Hierarchy

- **Headline** (600, 24px, 1.25): Secondary workspace titles such as Files, Recovery, Knowledge, and Setup.
- **Title** (600, 16px, 1.5): Task titles, panel titles, and primary operational groupings.
- **Body** (400, 14px, 1.5): Instructions, descriptions, form content, and table values.
- **Label** (600, 12px, 1.25): Field labels, action labels, and compact state text. Navigation group eyebrows may use smaller uppercase text with restrained tracking.
- **Data** (400, 12px, 1.5): Project IDs, storage paths, journal names, and machine-readable results.

**The Data Voice Rule.** Use monospace only when the value benefits from exact character recognition; ordinary interface language stays in Geist Sans.

## Layout

Desktop uses a fixed 208px navigation rail, a sticky 64px project switcher bar, and a centered task canvas capped at 1280px. The active-project ledger precedes the current workflow. Operations uses a tab strip followed by a two-column task shell: the flexible primary surface holds scope, controls, and preview; the 304px evidence rail holds safeguards, project scope, rollback state, and latest results.

Secondary workspaces retain the same shell and ledger but may use a single bounded work surface when their existing functionality does not support a truthful evidence rail. Setup remains deliberately denser because it preserves onboarding, health, owner, project, storage, inventory, upload, and project-list workflows in one secondary administration destination.

At widths below the large desktop breakpoint (1024px), the fixed rail becomes a left-side sheet opened from the top bar and the content loses its left offset. The evidence rail stacks below the task surface before it becomes cramped. At mobile widths below 768px, ledger metadata moves into a disclosure labeled Project details, task controls become one-column, and operation tabs scroll horizontally with an explicit swipe cue so Upload, Organize, Convert, and Inventory remain reachable. Content must fit the viewport without page-level horizontal overflow.

**The Ledger First Rule.** On every project-scoped destination, establish the active project and readiness before presenting an operation.

**The Narrow Truth Rule.** Mobile may collapse metadata, but it must keep project name, readiness, and a discoverable path to ID, owner, and storage details.

## Elevation & Depth

The system is flat by default. Borders, white-on-canvas layering, and the darker navigation rail establish hierarchy. Small shadows are limited to actionable controls, popovers, and floating overlays; major workspace cards do not float above the page. The sidebar carries a faint lateral ambient shadow, while Select and Sheet overlays may use stronger elevation to communicate temporary layering.

**The Flat Work Surface Rule.** Do not turn the workstation into a wall of floating cards. Use borders and tonal separation for persistent structure; reserve elevated shadows for interaction layers.

## Shapes

Controls use gently curved corners: 10px for the standard shadcn field and button language, 8px for compact variants, and 12px for major bounded work surfaces. Status indicators may be fully pill-shaped, but ordinary labels and containers should not become pills. Borders are thin and cool; icons are line-based and remain subordinate to labels.

**The Bounded, Not Bubbly Rule.** Curves soften dense operations without making the interface playful; repeated oversized capsules are not part of the system.

## Components

### Buttons

- **Shape:** Gently curved standard controls (8–10px radius), 40px high by default.
- **Primary:** Cobalt with white text, semibold 14px labeling, and compact horizontal padding. Use for the single task-forward action such as Preview plan, Create backup, or Register source for review.
- **Hover / Focus:** A slight cobalt tone change and small shadow on hover; a visible two-pixel cobalt focus ring with offset. Active state may move down by one pixel. Disabled controls retain their footprint and become visibly muted.
- **Secondary / Outline / Ghost:** Neutral fills or white bordered surfaces for reversible, navigational, and supporting actions. Destructive styling is reserved for genuinely destructive operations.

### Chips

- **Style:** Small semantic badges communicate ready, active, dry-run, file policy, or verified states. Neutral chips use muted surfaces; verified chips use teal ink on a pale teal surface.
- **State:** Chips report state and do not masquerade as actions unless implemented as keyboard-accessible controls.

### Cards / Containers

- **Corner Style:** Major surfaces use a 12px radius; internal evidence and preview containers use 8–10px.
- **Background:** White for task surfaces and slightly cooler white for evidence rails.
- **Shadow Strategy:** Flat at rest; structure comes from borders and tonal layering.
- **Border:** One-pixel cool neutral dividers define ledger cells, task regions, and table rows.
- **Internal Padding:** 16–20px for task and evidence regions, reduced only for dense table or tab chrome.

### Inputs / Fields

- **Style:** White, 40px high, 10px radius, compact 12–14px type, and a cool input border. Paths and IDs may use the data typeface.
- **Focus:** Border shifts toward cobalt and gains a restrained translucent cobalt ring.
- **Error / Disabled:** Errors use semantic red with direct recovery copy. Disabled fields use the muted surface and remain legible.

### Navigation

- **Desktop:** A fixed graphite rail groups Operate destinations separately from Administration. Active items use a quiet translucent white surface with white text and a cobalt icon accent.
- **Mobile:** The rail becomes a left Sheet. The current project remains in the top bar, and opening a destination closes the sheet.
- **Tabs:** Operations uses a full-width, horizontally scrollable tab strip. The selected task has a white active treatment and clear weight; mobile includes an overflow cue.

### Active-Project Ledger

The ledger is the signature component. It presents project name, immutable ID, owner, storage folder, and readiness in a single scan line on desktop. On mobile, name and readiness stay visible while the remaining fields live in a disclosure. Never populate the ledger with invented state.

### Task and Evidence Pair

The primary column asks for only the inputs required to perform or preview the current operation. The evidence rail states scope and invariants before action, then surfaces rollback and returned result information after action. Empty result regions describe the actual next step, not a generic request to select a project when one is already active.

Motion is functional and brief: navigation and control transitions run at approximately 150ms; workspace disclosure enters with a 180ms opacity and 4px vertical transition; Radix overlays use their state-driven open/close motion. `prefers-reduced-motion` reduces animation and transition durations to effectively zero and disables smooth scrolling.

## Do's and Don'ts

### Do:

- **Do** keep the active project and readiness visible or immediately discoverable before every scoped operation.
- **Do** lead with dry-run, no-overwrite, quarantine, approval, checksum, and rollback behavior where it changes operator decisions.
- **Do** preserve real API state, empty state, identifiers, test hooks, confirmation steps, and permission boundaries even when sample-filled comps look denser.
- **Do** use direct next-action copy that names the missing prerequisite or expected result.
- **Do** maintain keyboard access, visible focus, readable contrast, and reduced-motion behavior.
- **Do** preserve the final `approve-with-notes` reviewer record and address its minor brand and density notes in future polish work.

### Don't:

- **Don't** add hero sections, marketing claims, fabricated metrics, sample customer proof, or decorative dashboard statistics.
- **Don't** reintroduce a fully dark interface, gradients, cream editorial styling, giant headings, glass effects, or ornamental card walls.
- **Don't** hide all project identity on mobile or rely on clipped tabs without a discoverable overflow cue.
- **Don't** claim a successful operation before the backend returns evidence.
- **Don't** copy the approved comp's fabricated files, counts, timestamps, or result state into production behavior.
- **Don't** interpret visual fidelity work as permission to weaken guarded functionality or human approval boundaries.
