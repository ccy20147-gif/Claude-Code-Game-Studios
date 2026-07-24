---
name: ue5-profile-performance
description: Profile and improve UE5 frame time, memory, loading, package size, and simulation performance through reproducible target-platform evidence. Use for performance budgets, regressions, optimization decisions, and release gates.
---

# Profile UE5 Performance

Define target hardware or platform, build configuration, content state, reproducible route, capture method, warm-up, sample duration, and budget before profiling. Measure CPU, GPU, frame pacing, memory, streaming, loading, package size, shader or cook state, and subsystem-specific cost where applicable. Compare like-for-like captures only; editor numbers never substitute for target packaged runtime evidence.

Write reports to `production/performance` with build identity, route, raw capture hash or location, percentiles, budget, regression comparison, suspected owner, and retest requirement. Change one bounded cause at a time and preserve the before/after capture. A lower average frame time cannot close a stutter, memory, loading, or simulation failure that has not been independently measured.
