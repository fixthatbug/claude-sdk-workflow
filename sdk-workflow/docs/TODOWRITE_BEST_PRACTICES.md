# TodoWrite Best Practices for SDK Workflow Development
This document provides comprehensive guidance on using the TodoWrite tool effectively in SDK workflow development. TodoWrite helps organize complex multi-step tasks, track progress, and ensure systematic completion of work.
## Table of Contents
1. [When to Use TodoWrite](#when-to-use-todowrite)
2. [When NOT to Use TodoWrite](#when-not-to-use-todowrite)
3. [Task State Management](#task-state-management)
4. [Task Description Best Practices](#task-description-best-practices)
5. [Task Workflow Rules](#task-workflow-rules)
6. [Common Patterns](#common-patterns)
7. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
---
## When to Use TodoWrite
Use TodoWrite proactively in these scenarios:
### 1. Multi-Step Tasks (3+ Steps)
When a task requires three or more distinct steps or actions:
- Implementing a new feature (design → implement → test → document)
- Refactoring code across multiple files
- Bug fixes requiring investigation and multiple file changes
- Database migrations with multiple phases
### 2. Complex Workflows
Non-trivial, complex tasks that require careful planning:
- Implementing a new SDK executor with multiple components
- Performance optimization across multiple modules
- Architectural changes affecting multiple subsystems
- Dependency updates affecting many files
### 3. User-Requested Multiple Tasks
When users provide a list of things to be done:
- Numbered lists of requirements
- Comma-separated feature list
- Multiple related bug fixes
- Epic-level work with subtasks
### 4. After Receiving New Instructions
Capture user requirements as todos immediately when instructions are complex or multi-faceted:
- Feature specifications with multiple requirements
- Technical debt cleanup lists
- Testing coverage improvements across multiple areas
### 5. When Starting Complex Work
Mark the first task as `in_progress` BEFORE beginning work:
- Helps visualize scope upfront
- Prevents scope creep
- Provides clear completion checklist
- Shows progress to users
---
## When NOT to Use TodoWrite
Skip using TodoWrite when:
### 1. Single, Straightforward Task
- No tracking benefit if there's only one simple action
- Example: "Fix a typo in README.md"
- Example: "Update a single line of code"
### 2. Trivial Tasks
- Tasks that can be completed in less than 3 trivial steps
- Example: "Run npm install"
- Example: "Add a single comment to a function"
### 3. Purely Conversational/Informational
- Answering questions about architecture
- Explaining how something works
- Reviewing code without making changes
### 4. Single Command Execution
- Running a build command
- Executing tests with immediate results
- Checking git status
### 5. When Context is Unclear
- Wait until requirements are well-defined
- Too many unknowns = unreliable task list
- Better to start with exploration first
---
## Task State Management
### Three Valid States
#### 1. `pending`
- Task not yet started
- Use for tasks in the queue
- Can have many pending tasks simultaneously
**Example:**
```json
{
  "content": "Write unit tests for Executor class",
  "status": "pending",
  "activeForm": "Writing unit tests for Executor class"
}
```
#### 2. `in_progress`
- Currently being worked on
- **CRITICAL RULE: Only ONE task should be in_progress at a time**
- Change to `in_progress` before starting work
- Update this task's state throughout execution
**Example:**
```json
{
  "content": "Implement MailboxExecutor core functionality",
  "status": "in_progress",
  "activeForm": "Implementing MailboxExecutor core functionality"
}
```
#### 3. `completed`
- Task finished successfully
- Mark immediately after finishing
- Don't wait to batch completions
- Prerequisites:
  - Work is fully accomplished
  - Tests pass (if applicable)
  - No unresolved errors or blockers
**Example:**
```json
{
  "content": "Add error handling to executor",
  "status": "completed",
  "activeForm": "Adding error handling to executor"
}
```
---
## Task Description Best Practices
### Two Required Forms Per Task
Every task MUST have both forms:
#### 1. `content`: Imperative Form
- What needs to be done
- Start with action verbs: Fix, Implement, Add, Update, Refactor, Write, Review, Test
- Clear and concise
- Examples:
  - "Implement mailbox communication protocol"
  - "Fix executor error handling"
  - "Add validation for config parameters"
  - "Refactor session manager for clarity"
  - "Write integration tests for cache"
#### 2. `activeForm`: Present Continuous
- What is currently being done
- Start with -ing form: Implementing, Fixing, Adding, Updating, Refactoring, Writing, Reviewing, Testing
- Mirrors the `content` but describes active work
- Examples:
  - "Implementing mailbox communication protocol"
  - "Fixing executor error handling"
  - "Adding validation for config parameters"
  - "Refactoring session manager for clarity"
  - "Writing integration tests for cache"
### Guidelines for Writing Task Descriptions
1. **Be Specific**
   - Good: "Add retry logic to MailboxExecutor with exponential backoff"
   - Bad: "Fix bugs"
2. **Include Context/Module**
   - Good: "Implement configuration validation in cli/config.py"
   - Bad: "Validate configuration"
3. **Use Consistent Verb Patterns**
   - Create/Create new features
   - Update/Fix enhancements and bugs
   - Refactor for code structure changes
   - Write for tests and documentation
   - Review for code review and validation
4. **Keep Descriptions Concise**
   - Aim for 1-2 lines maximum
   - Details go in implementation, not task name
   - Example task names (appropriate length):
     - "Implement AsyncMailboxExecutor with retry mechanisms"
     - "Fix race condition in session cache"
     - "Refactor error handling across all executors"
---
## Task Workflow Rules
### Rule 1: Update Status in Real-Time
Don't wait for tasks to complete before updating:
- Update when starting a task → mark as `in_progress`
- Update as you encounter blockers → create new blocking task
- Update immediately after finishing → mark as `completed`
**Anti-Pattern (Bad):**
```
1. Create full task list
2. Do all work
3. Mark everything done at the end
```
**Pattern (Good):**
```
1. Create initial task list
2. Mark first task in_progress
3. Do work and update status
4. Mark complete immediately
5. Move to next task
```
### Rule 2: Only ONE in_progress at a Time
This is a critical constraint:
**Why:**
- Prevents context switching overhead
- Makes progress tracking clear
- Signals availability to users
- Prevents task abandonment
**What to do if you need to context switch:**
1. Mark current task as blocked (if applicable)
2. Document blocking reason
3. Create new task for blocker
4. Don't have two tasks in_progress simultaneously
### Rule 3: Complete Tasks Immediately
Don't batch completion:
**Bad:**
```
- Task A: completed
- Task B: completed
- Task C: completed
- Task D: in_progress (multiple tasks finishing at once)
```
**Good:**
```
1. Task A: completed (mark immediately)
2. Task B: completed (mark immediately)
3. Task C: completed (mark immediately)
4. Task D: in_progress (now switch)
```
### Rule 4: Never Mark Incomplete Work as Done
ONLY mark completed when:
- Work is fully accomplished
- Tests pass (if applicable)
- No unresolved errors
- All prerequisites met
**NOT completed if:**
- Partial implementation
- Tests failing
- Unresolved errors
- Dependencies not satisfied
- Code not reviewed
### Rule 5: Remove Invalid Tasks
Delete tasks no longer relevant:
- Don't mark "outdated" tasks as done
- Remove tasks that are no longer needed
- Reflect reality in the task list
- Keep list current and accurate
---
## Common Patterns
### Pattern 1: Feature Implementation
```json
[
  {
    "content": "Design AsyncMailboxExecutor interface and data structures",
    "status": "in_progress",
    "activeForm": "Designing AsyncMailboxExecutor interface and data structures"
  },
  {
    "content": "Implement core AsyncMailboxExecutor functionality",
    "status": "pending",
    "activeForm": "Implementing core AsyncMailboxExecutor functionality"
  },
  {
    "content": "Add error handling and retry logic",
    "status": "pending",
    "activeForm": "Adding error handling and retry logic"
  },
  {
    "content": "Write comprehensive unit tests",
    "status": "pending",
    "activeForm": "Writing comprehensive unit tests"
  },
  {
    "content": "Add integration tests with MessageBus",
    "status": "pending",
    "activeForm": "Adding integration tests with MessageBus"
  },
  {
    "content": "Write documentation and usage examples",
    "status": "pending",
    "activeForm": "Writing documentation and usage examples"
  }
]
```
### Pattern 2: Bug Investigation and Fix
```json
[
  {
    "content": "Reproduce and document the race condition",
    "status": "in_progress",
    "activeForm": "Reproducing and documenting the race condition"
  },
  {
    "content": "Analyze root cause in cache synchronization",
    "status": "pending",
    "activeForm": "Analyzing root cause in cache synchronization"
  },
  {
    "content": "Implement fix with proper locking mechanism",
    "status": "pending",
    "activeForm": "Implementing fix with proper locking mechanism"
  },
  {
    "content": "Add regression test to prevent recurrence",
    "status": "pending",
    "activeForm": "Adding regression test to prevent recurrence"
  },
  {
    "content": "Verify fix doesn't introduce new issues",
    "status": "pending",
    "activeForm": "Verifying fix doesn't introduce new issues"
  }
]
```
### Pattern 3: Refactoring Workflow
```json
[
  {
    "content": "Identify all error handling code patterns",
    "status": "in_progress",
    "activeForm": "Identifying all error handling code patterns"
  },
  {
    "content": "Create centralized error handler module",
    "status": "pending",
    "activeForm": "Creating centralized error handler module"
  },
  {
    "content": "Refactor ExecutorA to use new error handler",
    "status": "pending",
    "activeForm": "Refactoring ExecutorA to use new error handler"
  },
  {
    "content": "Refactor ExecutorB to use new error handler",
    "status": "pending",
    "activeForm": "Refactoring ExecutorB to use new error handler"
  },
  {
    "content": "Refactor ExecutorC to use new error handler",
    "status": "pending",
    "activeForm": "Refactoring ExecutorC to use new error handler"
  },
  {
    "content": "Run full test suite and verify no regressions",
    "status": "pending",
    "activeForm": "Running full test suite and verifying no regressions"
  }
]
```
---
## Anti-Patterns to Avoid
### Anti-Pattern 1: Vague Task Descriptions
**Bad:**
```json
{
  "content": "Fix things",
  "status": "in_progress",
  "activeForm": "Fixing things"
}
```
**Good:**
```json
{
  "content": "Fix memory leak in executor cleanup logic",
  "status": "in_progress",
  "activeForm": "Fixing memory leak in executor cleanup logic"
}
```
### Anti-Pattern 2: Too Many Tasks in_progress
**Bad:**
```json
[
  {"content": "Task A", "status": "in_progress", "activeForm": "Doing Task A"},
  {"content": "Task B", "status": "in_progress", "activeForm": "Doing Task B"},
  {"content": "Task C", "status": "in_progress", "activeForm": "Doing Task C"}
]
```
**Good:**
```json
[
  {"content": "Task A", "status": "in_progress", "activeForm": "Doing Task A"},
  {"content": "Task B", "status": "pending", "activeForm": "Doing Task B"},
  {"content": "Task C", "status": "pending", "activeForm": "Doing Task C"}
]
```
### Anti-Pattern 3: Not Updating Status in Real-Time
**Bad - Waits until end:**
```
[Create task list]
[Do all work]
[Update all tasks at once]
```
**Good - Updates as you go:**
```
[Create task list]
[Mark Task A in_progress]
[Do Task A work]
[Mark Task A completed immediately]
[Mark Task B in_progress]
[Do Task B work]
[Mark Task B completed immediately]
```
### Anti-Pattern 4: Including Trivial Tasks
**Bad:**
```json
[
  {"content": "Run npm install", "status": "pending", ...},
  {"content": "Check git status", "status": "pending", ...},
  {"content": "Create new feature", "status": "pending", ...}
]
```
**Good:**
```json
[
  {"content": "Create new feature with proper error handling", "status": "pending", ...},
  {"content": "Write comprehensive tests", "status": "pending", ...}
]
```
(Just run npm install and git status directly without adding to task list)
### Anti-Pattern 5: Marking Incomplete Work as Done
**Bad:**
```json
{
  "content": "Implement executor with error handling",
  "status": "completed",
  "activeForm": "Implementing executor with error handling"
}
// But tests still failing, errors not fully handled
```
**Good:**
```json
{
  "content": "Implement executor with error handling",
  "status": "in_progress",
  "activeForm": "Implementing executor with error handling"
}
// Keep working until truly done
```
### Anti-Pattern 6: Not Creating Follow-up Tasks for Blockers
**Bad - Just abandons work:**
```
[Hit blocker: missing dependency]
[Don't update task list]
[Continue with unrelated work]
```
**Good - Creates explicit blocking task:**
```
[Hit blocker: missing dependency]
[Mark current task as blocked]
[Create new task: "Install and configure missing dependency"]
[Move to that new task]
```
---
## Task Completion Checklist
Before marking a task as `completed`, verify:
- [ ] All work is fully accomplished
- [ ] Code changes are complete and tested
- [ ] Tests pass (if applicable)
- [ ] No unresolved errors or warnings
- [ ] All prerequisites are satisfied
- [ ] Documentation is updated (if needed)
- [ ] Code review completed (if required)
- [ ] Related files are updated
- [ ] No new issues introduced
---
## Summary of Rules
| Rule | Description | Why It Matters |
|------|-------------|----------------|
| **Use for multi-step** | 3+ steps or complex work | Prevents missed steps, tracks progress |
| **Skip for trivial** | Single simple task | Reduces overhead, keeps list manageable |
| **Specific descriptions** | Include module, exact action | Clarity prevents ambiguity |
| **Two forms required** | Imperative + continuous | Consistent formatting, professional output |
| **One in_progress** | Only one task at a time | Prevents context switch chaos |
| **Update in real-time** | Mark status as you work | Users see actual progress |
| **Complete immediately** | Mark done right after finishing | Accurate completion tracking |
| **Never mark incomplete** | Only done when truly done | Maintains trust in task list |
| **Handle blockers** | Create new tasks for blockers | Don't abandon work, be explicit |
| **Remove invalid** | Delete outdated tasks | Keep list accurate and current |
---
## References
- TodoWrite Tool Documentation
- SDK Workflow Implementation Guide
- Task Management Best Practices
