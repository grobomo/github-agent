# Spec 011: Code Cleanup

## Problem
Redundant inline import of `datetime` in main.py after top-level import was added in Spec 010.

## Solution
Remove the redundant `from datetime import datetime, timezone` inside the poll loop (line 299) since it's now imported at the top of the file.
