# Extended Thinking Optimization Patterns

Strategies for optimal extended thinking usage in Claude Agent SDK workflows.

## When to Use Extended Thinking

### High-Value Use Cases

| Use Case | Description | Budget |
|----------|-------------|--------|
| Multi-step planning | Breaking down complex projects, identifying dependencies | 20-32K |
| Architectural decisions | Evaluating trade-offs, scalability, maintainability | 25-32K |
| Root cause analysis | Debugging complex interactions, tracing execution | 15-25K |
| Research synthesis | Cross-referencing sources, building conclusions | 20-32K |
| Security threat modeling | Attack vectors, risk prioritization | 20-30K |

### Low-Value Use Cases (Avoid)

- Simple file operations (read, write, edit)
- Straightforward pattern-following implementations
- Routine refactoring with obvious improvements
- Well-defined tasks with step-by-step instructions
- Basic CRUD operations
- Formatting and linting fixes

## Budget Allocation by Task Type

```yaml
Discovery:
  haiku: 5000
  sonnet: 10000
  opus: 16000

Planning:
  haiku: 8000
  sonnet: 20000
  opus: 32000

Execution:
  haiku: 5000
  sonnet: 20000
  opus: 25000

Verification:
  haiku: 5000
  sonnet: 15000
  opus: 20000
```

## Thinking Structure Patterns

### Pattern 1: Hierarchical Analysis

```xml
<thinking>
# Problem Understanding
[Define the problem clearly]

# Context Analysis
[Analyze relevant context from tools]

# Approach Options
## Option A: [Name]
Pros: [...] Cons: [...] Complexity: [Low/Medium/High]

## Option B: [Name]
Pros: [...] Cons: [...] Complexity: [Low/Medium/High]

# Decision
Selected: [Option X]
Rationale: [Why this option is best]

# Implementation Plan
1. [Step 1]
2. [Step 2]
3. [Step 3]
</thinking>
```

### Pattern 2: Debugging Analysis

```xml
<thinking>
# Symptom Analysis
Observed: [What's broken]
Expected: [What should happen]

# Hypothesis Generation
H1: [Possible cause 1] - Likelihood: [High/Medium/Low]
H2: [Possible cause 2] - Likelihood: [High/Medium/Low]

# Evidence Gathering
[Plan which tools to use to test hypotheses]

# Root Cause
Based on evidence: [Confirmed cause]

# Fix Strategy
Approach: [How to fix]
Verification: [How to confirm fix works]
</thinking>
```

### Pattern 3: Research Synthesis

```xml
<thinking>
# Source Analysis
Source 1: [Key claims] - Credibility: [High/Medium/Low]
Source 2: [Key claims] - Credibility: [High/Medium/Low]

# Cross-Validation
Agreement: [Points where sources agree]
Conflict: [Points where sources disagree]

# Synthesis
Pattern: [Emergent understanding]
Confidence: [High/Medium/Low]
</thinking>
```

## Model-Specific Patterns

### Haiku: Fast, Focused

```xml
<thinking>
Task: [Clear one-liner]
Approach: [Direct solution]
Verification: [Quick check]
</thinking>
```

Use for: Discovery, simple implementation, quick validation.

### Sonnet: Balanced

```xml
<thinking>
# Context
[Relevant information from tools]

# Approach
[Step-by-step plan]

# Potential Issues
[Quick risk check]
</thinking>
```

Use for: Complex implementation, integration, testing.

### Opus: Deep Analysis

```xml
<thinking>
# Comprehensive Analysis
[Deep dive into problem space]

# Option Evaluation
[Detailed comparison with trade-offs]

# Long-term Implications
[Architecture, maintainability, scalability]

# Decision Rationale
[Well-reasoned conclusion with evidence]
</thinking>
```

Use for: Architecture, strategic planning, complex debugging.

## Budget Conservation Techniques

### 1. Front-Load Tool Usage

```python
# GOOD: Gather context first, think once with full information
Read("file1.py")
Read("file2.py")
Grep("pattern", output_mode="content")
# Then use extended thinking to analyze all results together

# BAD: Think → Tool → Think → Tool (wastes budget)
```

### 2. Progressive Refinement

First pass (cheap): Quick analysis, identify key decision points
Second pass (if needed): Deep analysis on complex decisions only

### 3. Batch Related Decisions

```xml
<thinking>
# Analyze all related decisions together
Decision set: [Auth + Session + Permissions]
# More efficient than separate thinking blocks
</thinking>
```

## Anti-Patterns

### Thinking About Thinking

```xml
<!-- BAD -->
<thinking>
I should think about how to approach this...
Let me consider what the user wants...
</thinking>

<!-- GOOD -->
<thinking>
Problem: Authentication bug
Root cause hypothesis: Token validation timing
Test: Check auth.py lines 45-60
</thinking>
```

### Redundant Thinking

```xml
<!-- BAD: Repeats tool output -->
<thinking>
Based on grep, there are 15 files using auth...
</thinking>

<!-- GOOD: Analyzes implications -->
<thinking>
15 files depend on auth → Changes require:
- Backward compatibility
- Migration path
- Deprecation warnings
</thinking>
```

---
**Version**: 1.0.0
