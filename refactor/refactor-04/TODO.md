# Refactor-04: Integration Implementation

## Status: IMPLEMENTING

## Phase 1: Foundation (Core + Types) ✅
- [x] Analyze main repo structure
- [x] Analyze project files  
- [x] Analyze previous refactor iterations
- [x] Document integration candidates

## Phase 2: Implementation
- [ ] Create unified directory structure
- [ ] Integrate core/types.py (main repo - production ready)
- [ ] Integrate core/config.py (main repo - production ready)
- [ ] Integrate core/router.py (main repo - production ready)
- [ ] Integrate core/agent_client.py (main repo - production ready)
- [ ] Integrate managers/token_manager.py (main repo - 500+ LOC)
- [ ] Integrate managers/cost_manager.py (main repo - 500+ LOC)
- [ ] Consolidate session management
- [ ] Integrate executors/base.py
- [ ] Integrate streaming from project files
- [ ] Integrate prompts from refactor-02

## Phase 3: Optimization
- [ ] Remove duplicate files from project
- [ ] Consolidate overlapping functionality
- [ ] Eliminate dead code paths
- [ ] Reduce file count

## Phase 4: Verification
- [ ] Verify all imports resolve
- [ ] Run syntax checks on all Python files
- [ ] Validate module exports
- [ ] Test core functionality

## Phase 5: Documentation
- [ ] Update CLAUDE.md
- [ ] Update README.md
- [ ] Document migration guide

## Files to DELETE (after integration)
```
project/cost.py           → Replaced by managers/cost_manager.py
project/cost_tracking.py  → Merged into cost_manager.py
project/session_data.py   → Merged into session_manager.py
project/session_utils.py  → Merged into session_manager.py
project/progress_monitor.py → Merged into progress.py
project/mode.py           → Merged into router.py
project/mode_selector.py  → Merged into router.py
project/presets.py        → Merged into config/presets.py
project/constants.py      → Merged into core/config.py
project/registry.py       → Merged into prompts/registry.py
```

## Target File Count: ~25 (down from ~50+)
## Target Code Reduction: ~40%
