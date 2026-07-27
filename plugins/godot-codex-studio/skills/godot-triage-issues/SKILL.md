---
name: godot-triage-issues
description: Reproduce, classify, prioritize, and route Godot 4 defects, regressions, technical debt, content failures, and release risks. Use for bug reports, issue triage, incident follow-up, and maintenance backlog decisions.
---

# Triage Godot 4 Issues

Require a stable issue ID, reporter context, build identity, platform, reproducible steps or an explicit non-reproducible status, expected and actual result, evidence, affected requirement, severity, impact, owner, and disposition. Separate defect, regression, debt, content, security, performance, accessibility, and operational categories. Assess priority from player impact, likelihood, scope, release proximity, workaround, and evidence quality rather than reporter urgency alone.

Maintain `production/issues` as the source of issue state. Link accepted remediation to a work item and verification evidence; link invalid, duplicate, deferred, or waived issues to their reason and review date. Never close an issue from a code diff or MCP acknowledgement alone: require the appropriate independent readback, regression evidence, and packaged runtime result when relevant.
