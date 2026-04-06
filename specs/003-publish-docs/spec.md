# Spec 003: Publish & Documentation

## Problem
The project is fully functional (39 tests, continuous service, 11 PRs merged) but has no README, no LICENSE, and hasn't been pushed to GitHub as a presentable public repo. The grobomo account is public-facing — projects need clear documentation for anyone discovering them.

## Scope
1. **README.md** — project overview, architecture diagram, quick start, configuration, project structure
2. **LICENSE** — MIT (standard for grobomo public repos)
3. **service.bat commit** — already done (untracked Windows launcher)
4. **Push to GitHub** — ensure remote is up to date with all recent work

## Non-goals
- No marketplace publishing yet (that's a separate effort)
- No generated API docs (project is simple enough for a single README)
- No changelog (git log serves this purpose for now)

## Success criteria
- README.md exists with accurate architecture diagram and usage examples
- LICENSE file exists
- All local commits pushed to grobomo/github-agent on GitHub
- `gh repo view` shows description and topics
