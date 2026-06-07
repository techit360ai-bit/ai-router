# Workspace ↔ Incubation Pipeline + Founder Multi-Project — Build Plan

Branch: `feat/workspace-incubation-pipeline` (both repos). Off updated main
(ai-router f88670c / new-frontend f063cb3).

## Problem (verified 2026-06-07)
- No `workspaces` table; WorkspaceAIService is stateless/idea-agnostic.
- run_full_venture_pipeline returns an ephemeral blueprint — never persisted, no project_id.
- "Create Workspace" button = bare navigate("/workspaces"); ?startup= param ignored.
- Founders: one scalar project_id; Incubation Hub = one idea at a time, no history/selector.

## Design (vertical slices, commit each)
### Backend (ai-router)
- S1 Models: `Workspace` (FK project_id, owner_id, name, status, blueprint_ref),
  `ProjectAnalysis` (FK project_id, persisted pipeline blueprint JSON + scores + created_at).
- S2 ProjectService: list_founder_projects, create_project, get_project. Multi-project.
- S3 Pipeline persistence: IncubationHubService.run_full_venture_pipeline persists a
  ProjectAnalysis + upserts Project scores, returns project_id. New
  `provision_workspace_from_project` on a WorkspaceService.
- S4 WorkspaceService: get_or_create workspace for a project, list workspaces, get
  workspace context (loads the project's latest analysis/blueprint). Thread project_id.
- S5 Endpoints: GET /founder/projects, POST /founder/projects, GET /projects/{id}/analysis,
  POST /workspaces/provision, GET /workspaces (list), GET /workspaces/{id}/context.

### Frontend (new-frontend)
- S6 lib/api/projects.ts + workspaces.ts (list projects, provision workspace, context).
- S7 Founder multi-project: project selector surfaced (Dashboard + Incubation Hub) over
  GET /founder/projects.
- S8 Incubation→Workspace handoff: "Create Workspace" provisions a workspace bound to the
  analyzed project_id and routes to it; workspace reads project context.

## Constraints
Backend not runnable here (py_compile gate); Vite SIGBUS (no browser verify). Commit each slice.

## Status (✅ done · 🚧 wip · ⬜ todo)
- ✅ S1 models (Workspace, ProjectAnalysis)
- ✅ S2 ProjectService (list/create founder projects — multi-project)
- ✅ S3 pipeline persistence (run_full_venture_pipeline persists ProjectAnalysis + returns project_id)
- ✅ S4 WorkspaceService (provision/list/context, project-scoped)
- ✅ S5 endpoints (GET/POST /founder/projects, GET /workspaces, POST /workspaces/provision, GET /workspaces/{id}/context)
- ⬜ S6 FE api  ⬜ S7 FE multi-project selector  ⬜ S8 FE handoff
