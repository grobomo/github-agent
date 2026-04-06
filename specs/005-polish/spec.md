# Spec 005: Polish & Hardening

## Problem
Code review identified minor gaps: no requirements.txt, README missing dashboard docs, no auto-report generation after full scans. These reduce usability for new users and limit operational visibility.

## Scope
1. **requirements.txt** — formal dependency list
2. **README update** — document `--report` CLI flag and dashboard
3. **Auto-report** — optionally generate HTML report after each full scan cycle
4. **.gitignore** — ensure report HTML files in data/ are excluded

## Non-goals
- No new features beyond what's listed
- No refactoring of existing modules
