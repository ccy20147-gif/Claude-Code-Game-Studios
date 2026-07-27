---
name: godot-run-playtest
description: Plan, conduct, and analyze Godot 4 player playtests with consent, hypotheses, representative journeys, and traceable findings. Use after a playable build or vertical slice is available for external or internal player feedback.
---

# Run A Godot 4 Playtest

Define the research question, participant profile, consent and privacy boundary, build identity, facilitator script, tasks, stopping rules, and observation plan before inviting players. Test an observable player journey tied to requirement IDs, including onboarding, failure recovery, accessibility settings where relevant, and the intended ending or loop. Do not treat playtester preference as proof of a design decision without triangulating behavior, context, and sample limits.

Store anonymized observations and raw-session retention policy separately from ordinary source control. Produce `production/playtests` reports that identify build, cohorts, tasks, metrics, observations, quotes with consent status, limitations, and linked issue or change IDs. Preserve contradictory findings; triage their impact through `$godot-triage-issues` or `$godot-change-design` rather than rewriting evidence to fit the current plan.
