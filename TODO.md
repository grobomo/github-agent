# GitHub Agent — TODO

## Vision
Extend teams-agent's core architecture (poll → store → resolve → route) to GitHub events.
Continuously monitors comments, issues, PRs, discussions, and settings changes (especially
permissions). Routes actionable events to a shared dispatcher brain (same one teams-agent uses).

## Architecture
```
GitHub API (polling or webhooks)
  │
  ▼
GitHub Poller (per-repo/per-org)
  ├── Issues: new, updated, closed
  ├── PRs: opened, reviewed, merged, comments
  ├── Discussions: new comments
  ├── Settings: permission changes, branch protection
  ├── Actions: workflow failures
  │
  ▼
Unified Message Store (SQLite + FTS, shared schema with teams-agent)
  │
  ▼
Shared Dispatcher (LLM classifier → router → workers)
  │
  ▼
CCC Workers / Local Claude / AWS Spot
```

## Key Design Decisions

### Containerized agents
Each agent (teams-agent, github-agent, future agents) runs in its own container.
- Dockerfile per agent, shared base image with Python + msgraph-lib + anthropic
- Can deploy to: local Docker, RONE K8s pod, AWS spot instance
- Agents communicate via shared bridge (git-bridge, PVC, or message queue)
- Golden dispatcher image shared across all agents

### Shared dispatcher
- NOT a separate project — reuse teams-agent/dispatcher/dispatcher.py
- Dispatcher reads from bridge, classifies, routes — channel-agnostic
- Each agent writes to the bridge in the same format
- Dispatcher doesn't care if message came from Teams or GitHub

### AWS spot for github-agent
- No local Docker (disk space constraint)
- Use aws skill to provision EC2 spot instance
- Container runs github-agent + dispatcher
- Bridge via git (ccc-rone-bridge pattern)

## Phase 1: Foundation
- [ ] T001: Initialize project (git, publish.json, CLAUDE.md, secret-scan)
- [ ] T002: Port lib/github.py from teams-agent as the GitHub poller core
- [ ] T003: GitHub event normalizer — convert issues/PRs/comments to unified message format
- [ ] T004: Reuse teams-agent's MessageStore (import or shared package)
- [ ] T005: Config: repos.yaml listing monitored repos/orgs with event filters

## Phase 2: Event Coverage
- [ ] T006: Issue events (opened, closed, commented, labeled)
- [ ] T007: PR events (opened, reviewed, merged, comment, CI status)
- [ ] T008: Discussion events (new, comment)
- [ ] T009: Settings/permission change detection (compare snapshots)
- [ ] T010: Actions workflow failure detection

## Phase 3: Dispatcher Integration
- [ ] T011: Write to shared bridge in dispatcher-compatible format
- [ ] T012: Dockerfile for github-agent (Python slim + deps)
- [ ] T013: Dockerfile for dispatcher (reuse from teams-agent)
- [ ] T014: docker-compose.yaml for local testing (agent + dispatcher + bridge volume)

## Phase 4: AWS Deployment
- [ ] T015: EC2 spot instance provisioning via aws skill
- [ ] T016: Deploy github-agent container to spot instance
- [ ] T017: Bridge sync (git push/pull between spot and local)
- [ ] T018: Health monitoring + email alerts (reuse install.py pattern)

## Phase 5: Multi-Agent Orchestration
- [ ] T019: Shared base Docker image (python + common deps)
- [ ] T020: Agent discovery protocol (agents register with dispatcher)
- [ ] T021: Cross-agent message routing (GitHub event → Teams notification)
- [ ] T022: Unified dashboard (health of all agents in one view)
