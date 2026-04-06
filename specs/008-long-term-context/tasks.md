# Spec 008: Long-term Brain Context — Tasks

- [ ] T054: Create `core/memory.py` — MemoryStore class
  - File-based per-repo memory: `data/memory/{account}/repos/{owner}/{repo}.json`
  - Account-level memory: `data/memory/{account}/account.json`
  - CRUD: load_repo_memory, save_repo_memory, load_account_memory, save_account_memory
  - Schema: `{purpose, milestones, open_threads, collaborators, pr_themes, last_compacted_at, action_log}`

- [ ] T055: Create `core/compactor.py` — MemoryCompactor
  - Runs after each full scan cycle
  - Loads repo memory + new events since `last_compacted_at`
  - Uses `claude -p` to incrementally merge new events into existing memory
  - Fallback: if LLM unavailable, append raw event summaries (truncate to size limit)
  - Skips repos with no new events since last compaction

- [ ] T056: Integrate memory into Brain prompt
  - `_build_context_prompt` receives Tier 2 (repo) + Tier 3 (account) memory
  - Only loads memories for repos touched by new events (bounded token usage)
  - Account summary prepended as cross-repo awareness section

- [ ] T057: Wire compactor into main.py poll loop
  - After `poll_full()`, run compactor on repos with new events
  - Account summary regeneration: daily (track last_account_compacted_at)
  - Add `--no-memory` CLI flag to disable memory (for testing/debugging)

- [ ] T058: Tests for memory store (CRUD, file I/O, schema validation)

- [ ] T059: Tests for compactor (mock LLM, incremental merge, skip-when-unchanged)

- [ ] T060: Tests for enhanced brain prompt (memory injection, token bounding)

- [ ] T061: Update TODO.md with completion status
