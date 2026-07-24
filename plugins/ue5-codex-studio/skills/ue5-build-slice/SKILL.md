---
name: ue5-build-slice
description: Plan and validate a production-quality UE5 vertical slice spanning the representative player journey, assets, save state, audio, QA, and packaging evidence. Use before committing a game to full production.
---

# Build A Vertical Slice

Select a representative journey that proves the project profiles rather than merely a feature list. Include the risky system interaction, level/scene flow, UI, art import, audio behavior, persistence, and target-platform build evidence. Define explicit `PROCEED`, `PIVOT`, and `STOP` thresholds.

Use `$ue5-plan-work` to create scoped work items. The slice cannot pass from screenshots alone: require saved/reloaded state, runtime behavior, and Windows/Linux package evidence when those targets apply.
