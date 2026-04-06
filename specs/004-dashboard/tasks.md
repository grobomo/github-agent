# Tasks: 004 Dashboard & Reporting

## Core Report Generator
- [ ] T036: Create core/report.py — query EventStore for report data (recent events, actions, errors, hourly volume)
- [ ] T037: Create report template — self-contained HTML with inline CSS, 5 sections (status, events, actions, errors, chart)
- [ ] T038: Add SVG bar chart — events per hour for last 24h, pure inline SVG (no JS libraries)

## CLI Integration
- [ ] T039: Add --report and --output flags to main.py, generate report and open in browser

## Tests
- [ ] T040: Tests for report data queries and HTML generation

## Task Tracking
- [ ] T041: Update TODO.md with spec 004 status
