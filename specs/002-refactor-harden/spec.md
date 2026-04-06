# Spec 002: Refactor & Harden

## Goal
DRY up duplicated code, improve modularity, and harden the codebase for production use.

## Problem
- `gh_command` and `parse_json` are duplicated across `github/poller.py` and `core/dispatcher.py`
- `github/settings.py` imports `gh_command` from `poller.py` (coupling settings to poller)
- No shared utility module for GitHub CLI operations

## Solution
- Extract shared `gh_command` and `parse_json` into `github/gh_cli.py`
- Update all consumers to import from the shared module
- Remove duplicate code from poller.py and dispatcher.py
