# Refactor-04: Integration Analysis Report

## Executive Summary

After analyzing the entire repository, I've identified **high-value components** from the main repo that should be integrated into the refactored codebase. The main repo contains production-ready managers and core utilities that supersede the project files.

## Repository Structure Analysis

### Main Repo (`claude-sdk-workflow/`)
```
core/           → Agent SDK integration, routing, types, config
managers/       → TokenManager, CostManager (production-ready, 500+ LOC each)
executors/      → Base executor, streaming, orchestrator
cli/            → Command line interface
communication/  → Message bus, progress tracking
resources/      → Prompts, tools, agents
```

### Project Files (`/mnt/project/`)
```
*.py files      → Refactored modules (session, streaming, workflow, etc.)
*.md files      → Documentation (anti_hallucination, base_directives, etc.)
```

### Previous Refactors
```
refactor-01/    → Base refactored Python modules (matches project files)
refactor-02/    → Prompts/ and docs/ subdirectories
refactor-03/    → Execution core (base_executor, execution_result, etc.)
```

---

## Integration Candidates (Priority Order)

### P0 - CRITICAL (Must Integrate)

| Component | Source | LOC | Reason |
|-----------|--------|-----|--------|
| `types.py` | `core/types.py` | 250 | Clean dataclasses: TokenUsage, CostBreakdown, SessionState, ExecutionResult |
| `token_manager.py` | `managers/` | 500+ | Production-ready with analytics, rate limiting, export |
| `cost_manager.py` | `managers/` | 500+ | Budget alerts, cache efficiency, multi-session tracking |
| `agent_client.py` | `core/` | 300 | Clean SDK adapter with singleton management |
| `base.py` | `executors/` | 100 | Abstract base executor with Strategy pattern |

### P1 - HIGH VALUE

| Component | Source | LOC | Reason |
|-----------|--------|-----|--------|
| `router.py` | `core/` | 120 | Task routing with complexity analysis |
| `config.py` | `core/` | 200 | Configuration management with model aliases |
| `streaming_orchestrator.py` | `executors/` | 300 | Consolidated streaming + oneshot |
| `prompts/` | `refactor-02/` | - | Team prompts (research, discussion, CICD, workflow) |

### P2 - CONSOLIDATE

| Component | Action | Reason |
|-----------|--------|--------|
| `session.py` (project) | Merge with `SessionManager` | Overlapping functionality |
| `cost.py` (project) | Replace with `CostManager` | Main repo version is superior |
| `progress.py` (project) | Merge with `ProgressMonitor` | Similar functionality |

---

## Overlap Analysis

### DUPLICATE IMPLEMENTATIONS (Remove from project files)

1. **Cost Tracking**
   - `project/cost.py` + `project/cost_tracking.py` → Replace with `managers/cost_manager.py`
   - Main repo version has: budget alerts, cache efficiency, export, multi-session

2. **Session Management**
   - `project/session.py` + `project/session_data.py` + `project/session_utils.py`
   - Consolidate into single session module using `core/types.py` SessionState

3. **Progress Monitoring**
   - `project/progress.py` + `project/progress_monitor.py`
   - Consolidate into single module

4. **Mode Selection**
   - `project/mode.py` + `project/mode_selector.py`
   - Consolidate with `core/router.py` complexity analysis

### KEEP FROM PROJECT FILES

- `streaming.py` - StreamingHandler, StreamingDecisionEngine
- `evaluation.py` - EvaluationFramework, HallucinationGuard
- `workflow.py` - BatchProcessor, WorkflowResult
- `cache.py` - ContextCacheManager
- `container.py` - ContainerManager

---

## Proposed Final Structure

```
claude-sdk-workflow/
├── src/sdk_workflow/
│   ├── __init__.py              # Clean exports
│   │
│   ├── core/                    # Foundation layer
│   │   ├── __init__.py
│   │   ├── types.py             # FROM: core/types.py
│   │   ├── config.py            # FROM: core/config.py  
│   │   ├── router.py            # FROM: core/router.py
│   │   └── agent_client.py      # FROM: core/agent_client.py
│   │
│   ├── managers/                # Resource managers
│   │   ├── __init__.py
│   │   ├── token_manager.py     # FROM: managers/token_manager.py
│   │   ├── cost_manager.py      # FROM: managers/cost_manager.py
│   │   ├── session_manager.py   # Consolidated from project files
│   │   └── cache_manager.py     # FROM: project/cache.py
│   │
│   ├── executors/               # Execution strategies
│   │   ├── __init__.py
│   │   ├── base.py              # FROM: executors/base.py
│   │   ├── streaming.py         # FROM: project/streaming.py
│   │   ├── orchestrator.py      # FROM: executors/orchestrator.py
│   │   └── userscope.py         # FROM: refactor-03/userscope_executor.py
│   │
│   ├── workflow/                # Workflow orchestration
│   │   ├── __init__.py
│   │   ├── processor.py         # FROM: project/workflow.py
│   │   ├── evaluation.py        # FROM: project/evaluation.py
│   │   └── optimization.py      # FROM: project/optimization.py
│   │
│   ├── prompts/                 # Agent prompts
│   │   ├── __init__.py
│   │   ├── base.py              # FROM: refactor-02/prompts/base.py
│   │   ├── registry.py          # FROM: refactor-02/prompts/registry.py
│   │   └── teams/               # FROM: refactor-02/prompts/teams/
│   │
│   └── utils/                   # Utilities
│       ├── __init__.py
│       ├── container.py         # FROM: project/container.py
│       ├── memory.py            # FROM: project/memory.py
│       └── parser.py            # FROM: project/parser.py
│
├── docs/                        # Documentation
│   ├── anti_hallucination.md    # FROM: project/
│   ├── base_directives.md       # FROM: project/
│   ├── parallel_execution.md    # FROM: project/
│   └── thinking_optimization.md # FROM: project/
│
└── refactor/                    # Archive previous iterations
    ├── refactor-01/             # KEEP for reference
    ├── refactor-02/             # MERGE prompts/
    └── refactor-03/             # MERGE executors/
```

---

## Implementation Tasks

### Phase 1: Foundation (Core + Types)
- [ ] Create `src/sdk_workflow/core/` directory
- [ ] Copy `types.py` from main repo
- [ ] Copy `config.py` from main repo
- [ ] Copy `router.py` from main repo
- [ ] Copy `agent_client.py` from main repo

### Phase 2: Managers
- [ ] Create `src/sdk_workflow/managers/` directory
- [ ] Copy `token_manager.py` from main repo
- [ ] Copy `cost_manager.py` from main repo
- [ ] Consolidate session management into `session_manager.py`
- [ ] Copy cache management from project files

### Phase 3: Executors
- [ ] Create `src/sdk_workflow/executors/` directory
- [ ] Copy `base.py` from main repo
- [ ] Copy `streaming.py` from project files
- [ ] Merge refactor-03 execution core

### Phase 4: Workflow
- [ ] Create `src/sdk_workflow/workflow/` directory
- [ ] Copy workflow modules from project files
- [ ] Integrate evaluation framework

### Phase 5: Prompts
- [ ] Create `src/sdk_workflow/prompts/` directory
- [ ] Copy from refactor-02/prompts/

### Phase 6: Cleanup
- [ ] Delete duplicate files from project
- [ ] Update all imports
- [ ] Run syntax verification
- [ ] Update documentation

---

## Files to DELETE (Duplicates)

From project files:
```
cost.py             # Replaced by managers/cost_manager.py
cost_tracking.py    # Merged into cost_manager.py
session_data.py     # Merged into session_manager.py
session_utils.py    # Merged into session_manager.py
progress_monitor.py # Merged into progress.py
mode.py             # Merged into router.py
mode_selector.py    # Merged into router.py
presets.py          # Merged into config/presets.py
constants.py        # Merged into core/config.py
registry.py         # Merged into prompts/registry.py
```

---

## Validation Checklist

- [ ] All Python files compile without errors
- [ ] All imports resolve correctly
- [ ] No circular dependencies
- [ ] All exports defined in __init__.py
- [ ] Unit tests pass
- [ ] Documentation updated

---

## Summary

**Total Files After Refactor:** ~25 (down from ~50+)
**Code Reduction:** ~40%
**Key Improvements:**
- Single source of truth for each capability
- Clean module boundaries
- Production-ready managers from main repo
- Unified type system
- Consistent naming conventions
