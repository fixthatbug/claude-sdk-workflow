# Orchestrator Module Documentation
This document describes the three new modules created for the SDK workflow delegation orchestrator system.
## Files Created
### 1. `utils/output_manager.py` - Session-based Output Directory Management
**Purpose**: Manages structured output directories with session isolation and phase-based organization.
**Key Components**:
- **`SessionManifest`** dataclass
  - Tracks session metadata, phases, files, and sizes
  - Provides `to_dict()` and `from_dict()` for JSON persistence
- **`OutputManager`** class
  - Session-based directory structure: `outputs/{session_id}/{phase}/`
  - Thread-safe operations with `threading.Lock`
  - Config-injectable design (base_dir customizable)
**Key Methods**:
```python
# Create session directory
create_session_dir(session_id, metadata) -> Path
# Write phase output (JSON or text)
write_phase_output(session_id, phase, filename, content, is_json=True) -> Path
# Read phase output
read_phase_output(session_id, phase, filename, is_json=True) -> Any
# Get session manifest with metadata
get_manifest(session_id) -> SessionManifest
# List all outputs for a phase
list_phase_outputs(session_id, phase) -> List[Path]
# Cleanup old sessions
cleanup_old_sessions(days=7) -> int
```
**Usage Example**:
```python
from sdk_workflow.utils import OutputManager
manager = OutputManager()
session_dir = manager.create_session_dir("sess_abc123")
# Write planning output
manager.write_phase_output(
    session_id="sess_abc123",
    phase="planning",
    filename="plan.json",
    content={"tasks": [...]}
)
# Read it back
plan = manager.read_phase_output("sess_abc123", "planning", "plan.json")
# Get manifest
manifest = manager.get_manifest("sess_abc123")
print(f"Total files: {manifest.total_files}")
```
---
### 2. `models/session.py` - Orchestrated Session with Checkpoint/Resume
**Purpose**: Extended session model for multi-phase orchestrated workflows with checkpoint support.
**Key Components**:
- **`PhaseResult`** dataclass
  - Captures complete phase execution results
  - Tracks status, duration, output, usage, cost, messages, artifacts, errors
  - Provides `to_dict()` and `from_dict()` for persistence
- **`OrchestratedSession`** class (extends `SessionState`)
  - Phase execution tracking with `PhaseResult` history
  - Named checkpoints for recovery points
  - Config injection for model/budget management
  - Enhanced persistence with phase history
**Key Methods**:
```python
# Factory method to create session
@classmethod
create(mode, task, model, system_prompt, ...) -> OrchestratedSession
# Add completed phase result
add_phase_result(result: PhaseResult) -> None
# Create named checkpoint
create_checkpoint(name, description, include_phase_results=True) -> str
# Resume from checkpoint
resume_from_checkpoint(name) -> bool
# List all checkpoints
list_checkpoints() -> List[Dict]
# Get latest phase result
get_latest_phase_result(phase_name=None) -> PhaseResult
# Persistence
save(storage_dir=None) -> Path
@classmethod
load(session_id, storage_dir=None, config=None) -> OrchestratedSession
```
**Usage Example**:
```python
from sdk_workflow.models import OrchestratedSession, PhaseResult
from sdk_workflow.core.types import ExecutionMode
# Create session
session = OrchestratedSession.create(
    mode=ExecutionMode.ORCHESTRATOR,
    task="Implement user dashboard",
    model="sonnet"
)
# Execute phase and add result
planning_result = PhaseResult(
    phase_name="planning",
    status="success",
    started_at=start.isoformat(),
    completed_at=end.isoformat(),
    duration_ms=1250.5,
    output={"tasks": [...]},
    usage=TokenUsage(...),
    cost=CostBreakdown(...)
)
session.add_phase_result(planning_result)
# Create checkpoint
session.create_checkpoint("post-planning", "After successful planning")
# Save session
session.save()
# Later: Load and resume
loaded = OrchestratedSession.load(session.session_id)
loaded.resume_from_checkpoint("post-planning")
```
---
### 3. `config/__init__.py` - Module Exports for Presets
**Purpose**: Central export point for phase presets and configuration utilities.
**Exports**:
- `PhaseType` - Enum of workflow phases (PLANNING, IMPLEMENTATION, REVIEW, TESTING)
- `PHASE_PROMPTS` - Dict mapping phases to system prompts
- `get_phase_prompt()` - Function to retrieve phase-specific prompts
- `list_available_phases()` - Function to list all available phases
**Usage Example**:
```python
from sdk_workflow.config import PhaseType, get_phase_prompt
# Get planning phase prompt
prompt = get_phase_prompt(PhaseType.PLANNING)
# List all phases
from sdk_workflow.config import list_available_phases
phases = list_available_phases()
```
---
## Design Patterns Used
### 1. **Dataclasses with Persistence**
All data models use `@dataclass` with `to_dict()` and `from_dict()` methods:
```python
@dataclass
class PhaseResult:
    def to_dict(self) -> Dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhaseResult": ...
```
### 2. **Config Injection**
Components accept optional `Config` instance for settings:
```python
def __init__(self, config: Optional[Config] = None):
    self.config = config or get_config()
```
### 3. **Factory Methods**
Convenient creation with sensible defaults:
```python
@classmethod
def create(cls, mode, task, ...) -> OrchestratedSession:
    return cls(...)
```
### 4. **Thread-Safe Operations**
Critical sections protected with `threading.Lock`:
```python
def __init__(self):
    self._lock = threading.Lock()
def write_phase_output(...):
    with self._lock:
        # ... critical section
```
### 5. **Optional Storage Paths**
All storage locations are customizable with sensible defaults:
```python
def __init__(self, base_dir: Optional[Path] = None):
    self.base_dir = base_dir or Path.home() / ".claude" / "sdk-workflow" / "outputs"
```
---
## Integration
All three modules work together seamlessly:
```python
from sdk_workflow.models import OrchestratedSession, PhaseResult
from sdk_workflow.utils import OutputManager
from sdk_workflow.config import PhaseType, get_phase_prompt
from sdk_workflow.core.types import ExecutionMode
# 1. Create session
session = OrchestratedSession.create(
    mode=ExecutionMode.ORCHESTRATOR,
    task="Build authentication system"
)
# 2. Setup output management
output_mgr = OutputManager()
output_mgr.create_session_dir(session.session_id)
# 3. Execute phase with config prompt
phase_prompt = get_phase_prompt(PhaseType.PLANNING)
# ... execute with phase_prompt ...
# 4. Save phase result
planning_result = PhaseResult(...)
session.add_phase_result(planning_result)
# 5. Save outputs
output_mgr.write_phase_output(
    session.session_id,
    "planning",
    "plan.json",
    planning_result.output
)
# 6. Create checkpoint
session.create_checkpoint("post-planning")
# 7. Persist session
session.save()
```
---
## Directory Structure
```
~/.claude/sdk-workflow/
├── outputs/                          # OutputManager
│   └── {session_id}/
│       ├── manifest.json
│       ├── planning/
│       │   └── plan.json
│       ├── implementation/
│       │   └── result.json
│       └── review/
│           └── review.json
│
└── sessions/
    └── orchestrated/                 # OrchestratedSession
        └── {session_id}.json
```
---
## Testing
Run the integration test to verify all modules:
```bash
python test_orchestrator_modules.py
```
This test demonstrates:
- Session creation and management
- Phase execution tracking
- Output directory management
- Checkpoint creation and resume
- Session persistence and loading
- Manifest generation
---
## Summary
These three modules provide a complete foundation for orchestrated workflow execution:
1. **`OutputManager`** - Structured, session-isolated output management
2. **`OrchestratedSession`** - Stateful session with phase tracking and checkpoints
3. **`config`** - Phase presets and configuration exports
All modules follow existing codebase patterns:
- Dataclasses with `to_dict`/`from_dict`
- Config injection
- Factory methods
- Thread-safe operations
- Optional paths with sensible defaults
- Comprehensive error handling
- Full type hints
