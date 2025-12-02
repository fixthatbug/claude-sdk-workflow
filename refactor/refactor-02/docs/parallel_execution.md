# Parallel Tool Execution Patterns

Strategies for maximizing parallelism in Claude Agent SDK workflows.

## Core Principle

```xml
<use_parallel_tool_calls>
Execute independent tool calls in parallel (same message) for 10x faster workflows.
Only use sequential calls (separate messages) when operations have dependencies.
</use_parallel_tool_calls>
```

## Decision Matrix

| Operation Type | Mode | Reason |
|---------------|------|--------|
| Reading multiple unrelated files | PARALLEL | No dependencies |
| Grep different patterns | PARALLEL | Independent searches |
| Multiple independent bash commands | PARALLEL | Can execute simultaneously |
| Web searches on different topics | PARALLEL | Independent research |
| Reading file → Editing same file | SEQUENTIAL | Edit depends on read |
| mkdir → cp into directory | SEQUENTIAL | cp needs directory |
| Gather → Analyze → Implement | SEQUENTIAL | Phase dependencies |

## Pattern 1: Parallel File Analysis

```python
# GOOD: Parallel (single message)
Read("src/auth.py")
Read("src/config.py")
Read("src/database.py")
Read("tests/test_auth.py")
# All execute simultaneously

# BAD: Sequential (5 messages, 5x slower)
# Message 1: Read("src/auth.py") → wait
# Message 2: Read("src/config.py") → wait...
```

## Pattern 2: Multi-Pattern Search

```python
# GOOD: Parallel grep
Grep("class.*Auth", output_mode="files_with_matches")
Grep("def.*login", output_mode="files_with_matches")
Grep("import.*database", output_mode="files_with_matches")
Grep("TODO|FIXME", output_mode="content", glob="*.py")
# All execute simultaneously
```

## Pattern 3: Parallel Research

```python
# GOOD: Parallel web research
WebSearch("authentication best practices 2025")
WebSearch("JWT vs session tokens comparison")
WebSearch("OAuth2 implementation guide")
# All searches execute in parallel, synthesize after
```

## Pattern 4: Sequential When Required

```python
# CORRECT: Sequential (dependencies exist)
# Message 1: Read file
Read("src/config.py")

# Message 2: Edit (depends on read)
Edit("src/config.py", old_string="DEBUG = True", new_string="DEBUG = False")

# Message 3: Verify
Bash("python -m py_compile src/config.py")
```

## Pattern 5: Hybrid Parallel-Sequential

```python
# Phase 1: Parallel discovery
Read("src/module1.py")
Read("src/module2.py")
Read("src/module3.py")

# CHECKPOINT: Analyze, plan changes

# Phase 2: Parallel implementation (independent edits)
Edit("src/module1.py", ...)
Edit("src/module2.py", ...)

# Phase 3: Sequential verification
Bash("pytest tests/test_module1.py")
# Check result, then next test
```

## Pattern 6: Subagent Parallelization

```python
# Parallel subagent delegation
agents = {
    'discovery-1': {'description': 'Analyze auth', 'model': 'haiku'},
    'discovery-2': {'description': 'Analyze database', 'model': 'haiku'},
    'discovery-3': {'description': 'Analyze API', 'model': 'haiku'},
}
# All 3 subagents execute in parallel
```

## Performance Rules

### Rule 1: Maximize Batch Size

```python
# GOOD: 10 parallel operations
Read("file1.py")
Read("file2.py")
# ...
Read("file10.py")

# BAD: 5 messages with 2 operations each
```

### Rule 2: Front-Load Context

```python
# GOOD: All context in first message
Read("src/auth.py")
Read("src/config.py")
Grep("class.*Auth", output_mode="content")
Glob("src/**/*.py")
# Then analyze in subsequent messages

# BAD: Interleaved read-analyze-read-analyze
```

## Checklist Before Executing

1. Are operations independent? → PARALLEL
2. Does B need results from A? → SEQUENTIAL
3. Can I batch more together? → Add to current message
4. Am I waiting unnecessarily? → Consolidate

---
**Version**: 1.0.0
**Performance Impact**: 5-10x speedup in discovery phases
