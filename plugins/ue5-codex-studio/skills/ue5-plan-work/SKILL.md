---
name: ue5-plan-work
description: Turn accepted UE5 baseline requirements into dependency-ordered, cross-discipline work items, milestones, and sprint plans. Use when planning implementation, estimating work, reviewing milestones, or tracking production progress.
---

# Plan Production Work

Run `../../scripts/validate_baseline.py design/baseline.yaml --gdd design/gdd/gdd.yaml` before planning accepted work. Use `../../templates/work-item.yaml` and validate each item with `../../scripts/validate_work_item.py`. A work item has a stable ID, discipline, work type, deliverables, linked requirements, baseline revision, dependencies, capabilities, acceptance evidence, and status. It may represent code, level, VO, localization, save migration, cook/package, or QA work; do not force a fake ADR onto nontechnical work.

Plan in dependency order and mark scope changes through `$ue5-change-design`. A work item becomes `READY` only after all referenced requirements are accepted and its expected evidence is concrete. Do not generate an executable work item from a superseded baseline revision.
