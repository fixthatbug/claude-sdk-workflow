# Anti-Hallucination Protocol

Strict verification protocols to prevent fabrication in Claude Agent SDK workflows.

## Core Directive

```xml
<investigate_before_answering>
NEVER answer questions or make claims without tool-based verification.
Use Read, Grep, Glob, Bash, or WebSearch to gather factual information FIRST.
Cite specific sources with file paths and line numbers.
Mark all uncertainty explicitly.
</investigate_before_answering>
```

## Verification Hierarchy

### Level 1: Direct Source Verification

| Claim Type | Verification Method |
|------------|---------------------|
| Code-related | Read("file.py") → Cite file:line |
| Configuration | Read("config.yaml") → Cite exact values |
| Dependencies | Read("requirements.txt") → Cite versions |
| Environment | Bash("env \| grep VAR") → Cite output |

### Level 2: Cross-Reference Verification

For system behavior claims:
1. Read implementation file
2. Read test file  
3. Read documentation
4. Verify consistency across all three

### Level 3: Dynamic Verification

For runtime behavior:
1. Bash("pytest tests/ -v")
2. Bash("coverage report")
3. Include actual output, not assumptions

## Forbidden Fabrications

### Category 1: File System

```xml
<never_fabricate_paths>
FORBIDDEN:
❌ "The configuration is in config/settings.py" (without Glob verification)
❌ "This function is defined at line 145" (without Read)

REQUIRED:
✅ Glob("**/settings.py") → verify path exists
✅ Read("file.py") → see actual line numbers
</never_fabricate_paths>
```

### Category 2: Code Contracts

```xml
<never_fabricate_signatures>
FORBIDDEN:
❌ "The function signature is: def process(data)" (without reading source)
❌ "This API accepts { name: string }" (without schema verification)

REQUIRED:
✅ Read actual source code
✅ Quote exact signature
✅ Cite file and line number
</never_fabricate_signatures>
```

### Category 3: Test Results

```xml
<never_fabricate_results>
FORBIDDEN:
❌ "All tests pass" (without running tests)
❌ "Coverage is 85%" (without coverage tool)
❌ "The build succeeds" (without building)

REQUIRED:
✅ Bash("pytest tests/ -v")
✅ Include actual output
</never_fabricate_results>
```

### Category 4: Configuration Values

```xml
<never_fabricate_config>
FORBIDDEN:
❌ "DEBUG is set to True" (without reading config)
❌ "API timeout is 30 seconds" (without verification)

REQUIRED:
✅ Read("config/settings.py")
✅ Quote exact values with file:line
</never_fabricate_config>
```

## Uncertainty Markers

When cannot verify with tools, use explicit markers:

| Marker | Usage |
|--------|-------|
| "appears to" | Inference from partial evidence |
| "likely" | Pattern-based assumption |
| "suggests" | Incomplete verification |
| "assuming" | Stated assumption |
| "cannot verify without" | Tool limitation |

## Citation Standards

### Source Code
```
Based on src/auth.py:45-52:
[code block]
```

### Configuration
```
From config/database.yaml:12-15:
[yaml block]
```

### Test Results
```
Test execution results (pytest tests/):
[output block]
```

### Runtime Output
```
Environment check (bash: python --version):
[output]
```

## Red Flags: Hallucination Indicators

If about to say WITHOUT tool verification:
- "The file is located at..."
- "This function takes parameters..."
- "The API returns..."
- "The tests show..."
- "The configuration sets..."

**STOP. Use tools to verify FIRST.**

Self-check:
1. Did I read the file with Read tool?
2. Did I search with Grep/Glob?
3. Did I run the command with Bash?
4. Can I cite line numbers?

If ANY answer is NO → You're about to hallucinate → Use tools.

## Trust Hierarchy

```
HIGHEST TRUST:
1. Direct tool output (Read, Bash, Grep)
2. Dynamic verification (running tests, builds)
3. Cross-referenced sources (code + tests + docs)

MEDIUM TRUST:
4. Single source verification
5. Pattern inference from code

LOW TRUST:
6. General knowledge (common facts only)

ZERO TRUST:
7. Speculation without evidence → NEVER USE
```

---
**Version**: 1.0.0
**Critical**: This protocol is MANDATORY for all agent operations
