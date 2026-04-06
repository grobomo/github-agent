# Spec 008: Long-term Brain Context — Tasks

- [x] T054: Create `core/memory.py` — MemoryStore class
  - File-based per-repo memory: `data/memory/{account}/repos/{owner}/{repo}.json`
  - Account-level memory: `data/memory/{account}/account.json`
  - CRUD: load_repo_memory, save_repo_memory, load_account_memory, save_account_memory
  - Schema: `{purpose, milestones, open_threads, collaborators, pr_themes, last_compacted_at, action_log}`

- [x] T055: Create `core/compactor.py` — MemoryCompactor
  - Runs after each full scan cycle
  - Loads repo memory + new events since last compaction (rowid-based tracking)
  - Uses `claude -p` to incrementally merge new events into existing memory
  - Fallback: if LLM unavailable, append raw event summaries (truncate to size limit)
  - Skips repos with no new events since last compaction

- [x] T056: Integrate memory into Brain prompt
  - `_build_context_prompt` receives Tier 2 (repo) + Tier 3 (account) memory
  - Only loads memories for repos touched by new events (bounded token usage)
  - Account summary prepended as cross-repo awareness section

- [x] T057: Wire compactor into main.py poll loop
  - After `poll_full()`, run compactor on repos with new events
  - Account summary regeneration: daily (track last_account_compacted_at)
  - Add `--no-memory` CLI flag to disable memory (for testing/debugging)

- [x] T058: Tests for memory store (14 tests — CRUD, file I/O, schema validation, limits)

- [x] T059: Tests for compactor (9 tests — mock LLM, incremental merge, skip-when-unchanged, thread closing)

- [x] T060: Tests for enhanced brain prompt (7 tests — memory injection, token bounding, backward compat)

- [x] T061: Update TODO.md with completion status
