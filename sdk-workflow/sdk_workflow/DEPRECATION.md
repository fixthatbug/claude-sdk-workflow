# SDK Workflow Deprecation Guide
## Overview
The SDK Workflow project has transitioned from a complex mailbox-based inter-orchestrator communication system to a simpler, more direct approach using **TodoWrite** for progress tracking and task management.
### Why Deprecate the Mailbox System?
The original mailbox system was designed to enable:
- Inter-orchestrator message passing through files
- Status updates and progress reporting
- Control signals (pause, resume, abort)
- Session-based communication
However, in practice:
1. **Complexity overhead**: Multi-layer abstraction for simple use cases
2. **File I/O bottlenecks**: Disk I/O for every message
3. **State management**: Complex message routing and cleanup
4. **Limited integration**: Difficult to integrate with Claude Code native tools
5. **Maintenance burden**: Large codebase for communication that can be handled more elegantly
The **TodoWrite** tool provides a cleaner, more direct integration with Claude Code, eliminating the need for this intermediate layer while providing better visibility into task progress.
---
## Deprecated Modules
### Core Mailbox System
All modules in the mailbox system are deprecated and have been archived:
| Module | Location | Replacement |
|--------|----------|-------------|
| `Mailbox` | `sdk_workflow/archive/mailbox_system/mailbox.py` | Direct TodoWrite API |
| `MailboxEventPublisher` | `sdk_workflow/archive/mailbox_system/mailbox_events.py` | Event listeners on TodoWrite |
| `OrchestratorMailboxMixin` | `sdk_workflow/archive/mailbox_system/mailbox_integration.py` | Direct TodoWrite in orchestrator |
| `Message`, `MessageType` | `sdk_workflow/archive/mailbox_system/mailbox.py` | TodoWrite task objects |
| `SessionMailbox` | `sdk_workflow/archive/communication/session_mailbox.py` | TodoWrite session tracking |
| `ProgressMailbox` | `sdk_workflow/archive/mailbox_system/progress_mailbox.py` | TodoWrite progress tracking |
### Communication System
Modules in `sdk_workflow/communication/` that were designed to work with mailbox:
| Module | Status | Notes |
|--------|--------|-------|
| `progress_mailbox.py` | Deprecated | Use TodoWrite for progress tracking |
| `session_mailbox.py` | Deprecated | Use TodoWrite for session tracking |
| `mailbox_events.py` | Archived | Event system superseded by TodoWrite |
### Session Viewer/Parser
Additional deprecated components:
| Component | Location | Status |
|-----------|----------|--------|
| `SessionParser` | `sdk_workflow/archive/session_viewer/session_parser.py` | Archived - Use TodoWrite for session state |
| Examples | `examples/mailbox_*.py` | Archived - Reference only |
---
## Migration Guide
### Conceptual Mapping
#### Old Mailbox Approach
```python
from sdk_workflow.core.mailbox import Mailbox, MessageType, send_status
# Initialize mailbox
mailbox = Mailbox(owner_id="orchestrator-123")
# Send status updates
send_status(
    recipient="claude-code",
    phase="implementation",
    progress=0.5,
    summary="Implementing features..."
)
# Check for control signals
message = mailbox.receive(msg_type=MessageType.SIGNAL, limit=1)
if message and message.payload.get('signal') == 'ABORT':
    # Handle abort
    pass
```
#### New TodoWrite Approach
```python
from anthropic_sdk import TodoWrite
# Create todo items for workflow phases
todos = [
    {"content": "Plan implementation", "status": "completed", "activeForm": "Planning implementation"},
    {"content": "Implement features", "status": "in_progress", "activeForm": "Implementing features"},
    {"content": "Run tests", "status": "pending", "activeForm": "Running tests"},
    {"content": "Deploy", "status": "pending", "activeForm": "Deploying"},
]
# Update progress directly
TodoWrite(todos)
```
**Key Differences:**
- **Before**: Stateful message passing through files with implicit ordering
- **After**: Explicit task list that represents current progress state
- **Before**: Messages need routing and cleanup
- **After**: Single source of truth for what's being worked on
---
## Code Examples: Before and After
### Pattern 1: Sending Status Updates
**OLD (Mailbox):**
```python
from sdk_workflow.communication.progress_mailbox import ProgressMailbox
from sdk_workflow.core.mailbox import send_status
class DataProcessingOrchestrator(OrchestratorMailboxMixin):
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._init_mailbox()
    def run(self):
        # Phase 1: Data loading
        self.report_status(
            phase="data_loading",
            progress=0.0,
            summary="Starting to load data..."
        )
        # ... actual work ...
        self.report_status(
            phase="data_loading",
            progress=0.5,
            summary="Data loading 50% complete"
        )
        # ... more work ...
        self.report_status(
            phase="data_loading",
            progress=1.0,
            summary="Data loading complete"
        )
        # Phase 2: Processing
        self.report_status(
            phase="processing",
            progress=0.0,
            summary="Starting data processing..."
        )
        # ... processing work ...
```
**NEW (TodoWrite):**
```python
from anthropic_sdk import TodoWrite
class DataProcessingOrchestrator:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.todos = []
    def run(self):
        # Initialize workflow tasks
        self.todos = [
            {"content": "Load data", "status": "in_progress", "activeForm": "Loading data"},
            {"content": "Process data", "status": "pending", "activeForm": "Processing data"},
            {"content": "Validate results", "status": "pending", "activeForm": "Validating results"},
        ]
        TodoWrite(self.todos)
        # Phase 1: Data loading
        self.todos[0]["status"] = "in_progress"
        self.todos[0]["activeForm"] = "Loading data (0% complete)"
        TodoWrite(self.todos)
        # ... actual work ...
        self.todos[0]["activeForm"] = "Loading data (50% complete)"
        TodoWrite(self.todos)
        # ... more work ...
        self.todos[0]["status"] = "completed"
        self.todos[0]["activeForm"] = "Loading data (complete)"
        self.todos[1]["status"] = "in_progress"
        self.todos[1]["activeForm"] = "Processing data (0% complete)"
        TodoWrite(self.todos)
        # ... processing work ...
```
**Benefits:**
- No file I/O overhead
- Clear task hierarchy visible in Claude Code
- Single state update instead of messaging pattern
- Easier to understand progress at a glance
---
### Pattern 2: Checking for Control Signals
**OLD (Mailbox):**
```python
class StreamingOrchestrator(OrchestratorMailboxMixin):
    def execute_phase(self, phase_name):
        self._init_mailbox()
        for step in self.steps:
            # Check for control signals between steps
            signal = self.check_mailbox()
            if signal:
                if not self.handle_signal(signal):
                    self.logger.warning(f"Unknown signal: {signal}")
            # Execute step
            self.execute_step(step)
# External control: Send PAUSE signal
orchestrator_mailbox = Mailbox(owner_id="external-controller")
orchestrator_mailbox.send(
    recipient="streaming-orchestrator",
    msg_type=MessageType.SIGNAL,
    payload={"signal": "PAUSE"}
)
```
**NEW (TodoWrite):**
```python
class StreamingOrchestrator:
    def execute_phase(self, phase_name):
        self.todos = [
            {"content": phase_name, "status": "in_progress", "activeForm": f"Executing {phase_name}"},
        ]
        for i, step in enumerate(self.steps):
            # Update progress
            self.todos[0]["activeForm"] = f"Executing {phase_name} (step {i+1}/{len(self.steps)})"
            TodoWrite(self.todos)
            # Execute step
            self.execute_step(step)
# External control: Update task status directly through TodoWrite
# This becomes part of the workflow state management
```
**Key Change:**
- Control signals are now managed at a higher level through task state
- No need to check files for incoming signals
- State is directly observable in Claude Code
---
### Pattern 3: OrchestratorMailboxMixin Usage
**OLD:**
```python
from sdk_workflow.core.mailbox_integration import OrchestratorMailboxMixin
from sdk_workflow.core.mailbox import send_command, MessageType
class ComplexOrchestrator(OrchestratorMailboxMixin):
    def __init__(self, session_id: str, config: dict):
        self.session_id = session_id
        self.config = config
        self._init_mailbox()  # Initialize mailbox
    def run(self):
        try:
            # Check for abort signal
            abort_msg = self.check_mailbox(msg_type=MessageType.SIGNAL)
            if abort_msg and abort_msg.payload.get('signal') == 'ABORT':
                self._abort()
                return
            # Run workflow phases
            for phase in ['planning', 'implementation', 'testing']:
                self.report_status(phase, 0, f"Starting {phase}...")
                self._run_phase(phase)
                self.report_status(phase, 1.0, f"{phase} complete")
        except Exception as e:
            self.report_status('error', 0, str(e))
            self.cleanup_mailbox()
            raise
```
**NEW:**
```python
from anthropic_sdk import TodoWrite
class ComplexOrchestrator:
    def __init__(self, session_id: str, config: dict):
        self.session_id = session_id
        self.config = config
        self.todos = []
    def run(self):
        try:
            # Initialize todos for workflow
            self.todos = [
                {"content": "Plan implementation", "status": "in_progress", "activeForm": "Planning implementation"},
                {"content": "Implement features", "status": "pending", "activeForm": "Implementing features"},
                {"content": "Run tests", "status": "pending", "activeForm": "Running tests"},
            ]
            TodoWrite(self.todos)
            # Run workflow phases
            for i, phase_todo in enumerate(self.todos):
                phase_todo["status"] = "in_progress"
                TodoWrite(self.todos)
                self._run_phase(phase_todo["content"])
                phase_todo["status"] = "completed"
                if i + 1 < len(self.todos):
                    self.todos[i + 1]["status"] = "in_progress"
                TodoWrite(self.todos)
        except Exception as e:
            # Mark failed task
            for todo in self.todos:
                if todo["status"] == "in_progress":
                    todo["status"] = "pending"
            TodoWrite(self.todos)
            raise
```
**Key Differences:**
- No inheritance of mixin class
- TodoWrite called directly with current state
- All phases visible upfront
- Simpler error handling
---
## Common Patterns Translation
| Pattern | Old Approach | New Approach |
|---------|------------|--------------|
| Initialize communication | `self._init_mailbox()` | Create `self.todos = []` list |
| Report progress | `self.report_status(phase, progress)` | Update todo status and call `TodoWrite()` |
| Check for signals | `self.check_mailbox()` | Read task state from TodoWrite |
| Mark complete | `self.report_status(phase, 1.0)` | Set todo status to "completed" |
| Handle errors | Report via mailbox | Update todo status, call `TodoWrite()` |
| Cleanup | `self.cleanup_mailbox()` | No cleanup needed |
---
## TodoWrite Benefits
### 1. Simpler API
- **Mailbox**: 15+ methods (send, receive, reply, clear, list_mailboxes, etc.)
- **TodoWrite**: Single point of update with clear structure
```python
# TodoWrite is straightforward
todos = [
    {"content": "Task 1", "status": "in_progress", "activeForm": "Working on Task 1"},
    {"content": "Task 2", "status": "pending", "activeForm": "Doing Task 2"},
]
TodoWrite(todos)
```
### 2. Built-in Progress Tracking
- Direct representation of workflow state
- No need for separate progress messages
- Automatic progress visibility in Claude Code UI
```python
# Progress is immediately visible
todos[0]["activeForm"] = "Task 1 (75% complete)"
TodoWrite(todos)  # Claude Code shows progress in real-time
```
### 3. No Infrastructure Overhead
- **Mailbox**: Requires file system management, cleanup, TTL handling
- **TodoWrite**: Managed by Claude Code, no maintenance needed
```python
# No cleanup code needed
# Old: mailbox.clear_all() for each orchestrator
# New: Nothing - state is managed by Claude Code
```
### 4. Direct Integration with Claude Code
- TodoWrite is a native Claude Code tool
- Designed for the workflow this orchestrator supports
- Consistent with Claude Code's execution model
### 5. Cleaner State Management
- Single source of truth for task state
- No message routing complexity
- Explicit task dependencies and ordering
### 6. Better Performance
- No file I/O for every status update
- Direct in-memory update
- Batch updates supported
```python
# Efficient batch update
for task in self.todos:
    task["status"] = "completed"
TodoWrite(self.todos)  # Single operation
```
---
## Archived Locations
All deprecated modules have been moved to the archive directory for historical reference:
```
sdk_workflow/archive/
├── README.md                                    # Archive overview
├── communication/
│   └── session_mailbox.py                       # Old session tracking
├── core/
│   └── mailbox.py                               # Legacy mailbox implementation
├── mailbox_system/                              # Complete old system
│   ├── mailbox.py                               # Core mailbox class
│   ├── mailbox_events.py                        # Event system
│   ├── mailbox_example.py                       # Usage examples
│   ├── mailbox_integration.py                   # Orchestrator integration
│   ├── mailbox_messagebus_integration_example.py
│   ├── mailbox_protocol.py                      # Message protocol
│   ├── progress_mailbox.py                      # Progress tracking
│   ├── session_mailbox.py                       # Session management
│   └── test_mailbox.py                          # Old test suite
└── session_viewer/
    └── session_parser.py                        # Session parsing (deprecated)
```
### Reference Locations
Reference only - do not use in new code:
- `/examples/mailbox_example.py` - Shows old patterns (archived reference)
- `/examples/mailbox_messagebus_integration_example.py` - Integration example (archived)
### Accessing Archived Code
If you need to reference old code:
```bash
# View old mailbox implementation
cat sdk_workflow/archive/mailbox_system/mailbox.py
# See old usage patterns
cat sdk_workflow/archive/mailbox_system/mailbox_example.py
# Read integration examples
cat sdk_workflow/archive/mailbox_system/mailbox_integration.py
```
---
## Timeline
### Deprecation Timeline
| Date | Event | Status |
|------|-------|--------|
| **Dec 2024** | Mailbox system deprecated in favor of TodoWrite | CURRENT |
| **Dec 2024** | All modules moved to `sdk_workflow/archive/` | CURRENT |
| **Dec 2024** | Deprecation warnings added to archived modules | CURRENT |
| **Q1 2025** | Documentation and examples migrated to TodoWrite | PLANNED |
| **Q2 2025** | Archive reviewed for removal | PLANNED |
| **Q3 2025** | Archived modules removed from repository (v2.0.0) | PLANNED |
### Migration Phases
#### Phase 1: Assessment (Current)
- Identify which code uses mailbox system
- Plan TodoWrite migration
- Create migration guides
#### Phase 2: Gradual Migration (Next)
- Update new code to use TodoWrite
- Migrate active projects
- Document lessons learned
#### Phase 3: Archive Cleanup (Q2 2025)
- Archive remaining mailbox references
- Keep code for historical reference
- Reduce maintenance burden
#### Phase 4: Final Removal (Q3 2025)
- Remove archived code from main repository
- Move to separate archive repository if needed
- Update all documentation
---
## Migration Checklist
Use this checklist when migrating code from mailbox to TodoWrite:
- [ ] Identify all `from sdk_workflow.core.mailbox import` statements
- [ ] Identify all `from sdk_workflow.communication.mailbox import` statements
- [ ] Identify all classes inheriting from `OrchestratorMailboxMixin`
- [ ] List all workflow phases and tasks
- [ ] Create TodoWrite todo list for phases
- [ ] Replace `self.report_status()` calls with todo updates
- [ ] Replace `self.check_mailbox()` calls with direct state checks
- [ ] Remove `self._init_mailbox()` initialization
- [ ] Remove `self.cleanup_mailbox()` calls
- [ ] Remove mailbox inheritance from class definition
- [ ] Test TodoWrite updates work correctly
- [ ] Update any documentation or comments referencing mailbox
- [ ] Run test suite to verify functionality
---
## Support & Getting Help
### Finding Migration Information
1. **TodoWrite Documentation**
   - Main SDK documentation
   - TodoWrite API reference
   - Integration examples
2. **This Guide**
   - See "Code Examples" section above
   - See "Common Patterns Translation" section
3. **Archived Code Reference**
   - View old implementations: `sdk_workflow/archive/mailbox_system/`
   - Study patterns in `mailbox_example.py`
   - Reference integration code in `mailbox_integration.py`
### Common Migration Questions
**Q: How do I send real-time progress updates?**
A: Update the `activeForm` field in your todo items:
```python
todo["activeForm"] = f"Processing file {current}/{total}"
TodoWrite(self.todos)
```
**Q: How do I handle errors with TodoWrite?**
A: Add error status or flag to your todos:
```python
todo["status"] = "pending"  # Mark as not yet attempted
# or add a flag
todo["error"] = str(exception)
TodoWrite(self.todos)
```
**Q: Do I need to clean up TodoWrite tasks?**
A: No, TodoWrite is managed by Claude Code automatically.
**Q: Can I send messages between orchestrators with TodoWrite?**
A: TodoWrite is for tracking workflow progress. For orchestrator communication, use direct function calls or integrate with your application's messaging layer directly.
**Q: Where can I find examples?**
A: See "Code Examples" section above for before/after patterns.
### Getting Help
For migration questions:
1. Check the code examples in this guide
2. Compare your code with patterns in "Common Patterns Translation"
3. Review archived code in `sdk_workflow/archive/` as reference
4. Check the TodoWrite API documentation
5. Consult the integration examples in archived directory
### Reporting Issues
If you encounter problems during migration:
1. Document the specific pattern you're trying to migrate
2. Note any errors or unexpected behavior
3. Include the old code and your migration attempt
4. Reference the relevant section of this guide
---
## Frequently Asked Questions (FAQ)
### Project Status Questions
**Q: Will my old mailbox code still work?**
A: Yes, but with deprecation warnings. Archived code is preserved in `sdk_workflow/archive/`. However, new code should use TodoWrite.
**Q: How long until mailbox is removed?**
A: Planned removal in Q3 2025 (version 2.0.0). Migration should be completed by Q2 2025.
**Q: Can I still use mailbox after the deprecation?**
A: After removal in v2.0.0, you can reference archived code on GitHub or in git history.
### Technical Questions
**Q: Why not just improve the mailbox system?**
A: TodoWrite is simpler, more direct, and directly integrated with Claude Code. It's the right tool for this job.
**Q: Is TodoWrite available in all Claude Code versions?**
A: Check the Claude Code documentation for version requirements.
**Q: Can I use both mailbox and TodoWrite together?**
A: Yes, but it's not recommended. Migrate completely to TodoWrite for clarity.
### Migration Questions
**Q: How long does migration take?**
A: Simple projects: 1-2 hours. Complex projects: 1-2 days. Mostly search-and-replace with testing.
**Q: Do I have to migrate right away?**
A: No, but plan to complete by Q2 2025. Deprecation warnings will become louder.
**Q: What if I have complex mailbox patterns?**
A: Review the archived code patterns and adapt them to TodoWrite structure. Most patterns map directly.
---
## Summary
The migration from mailbox to TodoWrite represents a shift toward:
- **Simplicity**: Fewer abstractions, clearer code
- **Directness**: Direct integration with Claude Code
- **Maintainability**: Less infrastructure to manage
- **Performance**: No file I/O overhead
- **Visibility**: Progress directly visible in Claude Code
For any questions or issues during migration, refer to the sections above or examine the archived code in `sdk_workflow/archive/` for reference implementations.
Happy migrating!
