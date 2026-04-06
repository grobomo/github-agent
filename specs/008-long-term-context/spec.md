# Spec 008: Long-term Brain Context

## Problem
The Brain currently operates with a 24-hour sliding context window (max 200 events). This means it has no memory of why repos exist, what major decisions were made, or the trajectory of ongoing work. Every analysis starts nearly from scratch. Issue #16 describes the need for human-like awareness: the agent should know the purpose and history of every repo, recall past actions and rationales instantly, and maintain this knowledge automatically.

## Solution: Three-tier Memory Architecture

### Tier 1: Hot Cache (existing — 24h events)
- Current `ContextCache` stays as-is for immediate situational awareness
- Recent events, active issues/PRs, notification stream

### Tier 2: Project Memory (`data/memory/{account}/repos/{owner}/{repo}.json`)
- One JSON file per repo: purpose, key milestones, ongoing threads, last-known state
- Updated by the **Memory Compactor** after each full scan cycle
- LLM-summarized from recent events + existing memory (incremental, not full rewrite)
- Includes: repo description, key collaborators, recent PR themes, open issues summary, action history

### Tier 3: Account Memory (`data/memory/{account}/account.json`)
- Cross-repo awareness: which repos relate to each other, overall account trajectory
- Action log: every RESPOND/DISPATCH/ALERT with rationale (append-only, compacted periodically)
- Updated less frequently (every N full scans or daily)

## Memory Compactor
Runs after each full scan. Steps:
1. Load current repo memory files
2. Get new events since last compaction (tracked via `last_compacted_at` in memory file)
3. Use `claude -p` to merge new events into existing memory (incremental update prompt)
4. Write updated memory files
5. Append actions to action log
6. Periodically (daily) regenerate account-level summary from all repo memories

## Enhanced Brain Prompt
Before analyzing new events, the Brain receives:
1. **Account summary** (Tier 3) — cross-repo awareness, recent action log
2. **Relevant repo memories** (Tier 2) — only repos touched by new events
3. **Hot context** (Tier 1) — last 24h events as today

This keeps token usage bounded: we don't send all history, just the distilled memory.

## Optimization: Cost Control
- Memory compaction uses a smaller/cheaper model when available (`--model` flag)
- Compaction is skipped if no new events since last compaction
- Repo memories have a max size (truncate oldest sections)
- Account summary regeneration is daily, not per-cycle

## Non-goals
- No vector DB or embedding search (keep it file-based and simple)
- No cross-account memory (accounts remain isolated)
- No retroactive memory generation from old DB events (start fresh)
