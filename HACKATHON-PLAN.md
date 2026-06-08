# Hackathon Intelligence — Build Plan

Branch: `feat/hackathon-intelligence` (both repos), off main (ai-router cb16c17 /
new-frontend fa237fe).

## Problem (verified 2026-06-07)
ZERO hackathon intelligence in backend (grep "hackathon" = 0 across all .py).
Frontend: founder flow works LOCALLY (no persistence, scoreBrief = keyword mock);
org "Live Command Centre" is fully mock — stats hardcoded, build-velocity heatmap
is Math.random() per render. No idea→workspace pipe, no real-time reporting to
org host or to teams/founders.

## Target capability (user's Q2)
Hackathon intelligence that (a) tracks + pipes analyzed hackathon ideas into a
workspace, and (b) gives real-time intelligence + reports to the ORG host AND to
team collaborators + founders, per hackathon.

## Design (slices, commit each)
### Backend (ai-router)
- H1 Models: Hackathon, HackathonTeam (registration+members), HackathonBrief
  (scored), HackathonCheckIn (build velocity source), HackathonScore (judge +
  platform composite).
- H2 HackathonService — ORG-facing: get_overview (registrants/teams/solo, live
  status), get_velocity_heatmap (REAL aggregation from check-ins, not random),
  get_leaderboard + composite scoring, get_pipeline (CRS buckets).
- H3 HackathonService — TEAM-facing: register, submit_brief (real composite
  score: judgePct*0.5 + platformAvg*0.5; platformAvg = avg(problem_clarity,
  team_momentum, min(100, demo_readiness_hours*6))), log_check_in, get_team_status.
- H3b Idea→Workspace pipe: provision a workspace from a hackathon brief (reuse
  WorkspaceService) so analyzed hackathon ideas flow into their team workspace.
- H4 Endpoints: /hackathons, /hackathons/{id}/overview|velocity|leaderboard|pipeline,
  POST /hackathons/{id}/register|brief|checkin, GET .../teams/{tid}/status,
  POST .../teams/{tid}/workspace.

### Frontend (new-frontend)
- H5 lib/api/hackathon.ts (org + team fetchers).
- H6 Org HackathonDetail.tsx: overview stats + build-velocity heatmap + composite
  from backend (replace Math.random + hardcoded). Poll for "real-time".
- H7 Founder hackathon (BriefStage/BuildStage): submit brief → backend score;
  log check-ins → backend; provision team workspace from brief.

## Constraints
Backend py_compile gate (deps absent); Vite SIGBUS (no browser verify). Commit each slice.

## Status (✅ done · 🚧 wip · ⬜ todo)
- ✅ H1 models (Hackathon, HackathonTeam, HackathonBrief, HackathonCheckIn, HackathonScore)
- ✅ H2 org service (overview, velocity heatmap from check-ins, leaderboard, pipeline)
- ✅ H3 team service (register, submit_brief w/ composite score, log_check_in, get_team_status)
- ✅ H3b workspace pipe (provision_team_workspace via WorkspaceService)
- ✅ H4 endpoints (GET /hackathons[/{id}/overview|velocity|leaderboard|pipeline|teams/{tid}/status]; POST .../register|brief|checkin|teams/{tid}/workspace)
- ⬜ H5 FE api ⬜ H6 FE org ⬜ H7 FE founder
