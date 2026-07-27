---
name: godot-design-investigation
description: Design and validate fair detective or mystery gameplay using a truth-to-clue-to-inference graph. Use for investigation games, deduction puzzles, clue chains, hypothesis systems, or spoiler-safe playtest preparation.
---

# Design An Investigation

Use `../../templates/truth-graph.yaml` and run `../../scripts/validate_truth_graph.py` before accepting a graph. Model world truths, player observations, clues, inferred facts, hypotheses, validation or refutation, and the final solution as separate nodes. Every required truth needs reachable supporting clues; avoid circular proof, unmarked soft locks, and a solution that depends on hidden information.

When the graph passes structural validation, still require a spoiler-safe fresh-tester playtest. Store a tester export without truth or solution nodes. A clue or line revision must flow through `$godot-change-design` and invalidate only its dependent hypotheses, level placements, media, and tests.
