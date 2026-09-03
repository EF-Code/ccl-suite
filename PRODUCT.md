# CCL AI Suite

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is an operator who repeatedly selects an existing project and performs controlled file, knowledge, and recovery work. Staff and interns carry out routine work; supervisors and administrators handle protected review and approval decisions.

## Product Purpose

CCL AI Suite gives local teams one project-scoped workspace for handling files, searchable approved knowledge, reversible organisation, and verified recovery. Success means an operator can enter a project, understand its state, complete the intended task, and see the result without navigating a wall of unrelated controls.

## Positioning

Operations are bound to one active project and preserve auditability, source identity, reversibility, and human approval boundaries across file and knowledge workflows.

## Operating Context

Operators work in a browser against a local FastAPI service. The frequent flow is selecting an existing project, then scanning, uploading, converting, organising, browsing, versioning, backing up, restoring, registering knowledge, searching approved sources, or answering from cited evidence. Creating a development owner, registering a project, and preparing its storage are secondary onboarding tasks.

## Capabilities and Constraints

- Preserve every existing API workflow, permission boundary, confirmation step, DOM identifier used by browser tests, and project-scoping behavior.
- Files and restore destinations must remain confined to approved project storage.
- Conversion, organisation, version restore, and backup restore must not overwrite protected originals.
- Knowledge sources require review before ingestion, search, or grounded answers.
- The interface must remain usable on desktop, tablet, and mobile web.
- Vite, React, Tailwind CSS, and the existing shadcn/Radix component source are the established stack. The user delegated selection of the best UI framework; the redesign will deepen the existing shadcn system instead of adding a competing framework.

## Brand Commitments

The product name is CCL AI Suite. Interface language is direct, operational, and evidence-aware. No unverified commercial claims or invented customer proof should appear.

## Evidence on Hand

The repository contains working API routes, database models, browser workflow tests, role and upload policies, project/file/knowledge records, and the current dashboard implementation. These are product truth. No customer testimonials, usage metrics, or external brand assets are available and none should be fabricated.

## Product Principles

- Put the active project and its current state before every operation.
- Show only the controls needed for the task at hand.
- Make protected, reversible, and approval-gated behavior explicit at the moment it matters.
- Use empty and error states to tell the operator what to do next.
- Prefer familiar, keyboard-accessible product patterns over decorative novelty.

## Accessibility & Inclusion

The interface must support keyboard navigation, visible focus, reduced motion, readable contrast, semantic labels, and responsive operation at mobile widths.
