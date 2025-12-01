# Session ID Capture and Resume - Usage Guide
## Overview
The SDK workflow now supports capturing Claude SDK session IDs and resuming previous sessions. This enables:
1. **Session continuity** - Resume conversations across restarts
2. **State recovery** - Restore context from previous interactions
3. **Long-running workflows** - Pause and resume complex tasks
## Architecture
### Components Modified
1. **agent_client.py**
   - `AgentClientManager._current_session_id` - Stores captured SDK session ID
   - `capture_session_id()` - Extracts session ID from SDK messages
   - `get_current_session_id()` - Returns current session ID
   - `clear_session_id()` - Clears session state
   - `create_options(resume=...)` - Accepts session ID for resume
2. **state.py**
   - `Session.sdk_session_id` - New field to store SDK session ID
   - `Session.save_to_file()` - Instance method to save session to JSON
   - `Session.load_from_file()` - Class method to load session from JSON
   - `SessionManager.create(sdk_session_id=...)` - Accepts SDK session ID
   - `SessionManager.update(sdk_session_id=...)` - Updates SDK session ID
3. **streaming.py**
   - `StreamingExecutor._sdk_session_id` - Stores captured session ID
   - `StreamingExecutor._resume_session_id` - Session ID to resume from
   - `get_sdk_session_id()` - Returns captured session ID
   - Session ID capture during streaming execution
## Usage Examples
### Example 1: Basic Session Capture
```python
from core.state import SessionManager
from executors.streaming import StreamingExecutor
# Create session manager
manager = SessionManager()
# Create executor
executor = StreamingExecutor()
executor.setup()
# Execute task (SDK session ID captured automatically)
result = executor.execute(
    task="Analyze this codebase",
    system_prompt="You are a code analyst"
)
# Get the captured SDK session ID
sdk_session_id = executor.get_sdk_session_id()
# Store in session manager
session = manager.create(
    mode="streaming",
    task="Analyze this codebase",
    model="claude-sonnet-4-20250514",
    sdk_session_id=sdk_session_id
)
print(f"Session created: {session.id}")
print(f"SDK session ID: {session.sdk_session_id}")
```
### Example 2: Resume Previous Session
```python
from core.state import SessionManager
from executors.streaming import StreamingExecutor
# Load previous session
manager = SessionManager()
previous_session = manager.get("sess_abc123")
if previous_session and previous_session.sdk_session_id:
    # Create executor with resume capability
    executor = StreamingExecutor(
        resume_session_id=previous_session.sdk_session_id
    )
    executor.setup()
    # Continue conversation
    result = executor.execute(
        task="Continue from where we left off",
        system_prompt=previous_session.system_prompt or ""
    )
    # Update session with new messages
    manager.update(
        previous_session.id,
        status="completed",
        append_message={
            "role": "assistant",
            "content": result.content
        }
    )
```
### Example 3: Session Persistence
```python
from pathlib import Path
from core.state import Session, SessionStatus
# Create a session
session = Session(
    id="sess_example",
    mode="streaming",
    task="Long-running analysis",
    status=SessionStatus.RUNNING.value,
    model="claude-sonnet-4-20250514",
    created_at="2025-01-01T00:00:00",
    updated_at="2025-01-01T00:05:00",
    sdk_session_id="sdk_abc123xyz"
)
# Save to custom location
save_path = Path("./my_sessions/important_session.json")
session.save_to_file(save_path)
# Later, load from file
loaded_session = Session.load_from_file(save_path)
print(f"Resumed session {loaded_session.id}")
print(f"SDK session: {loaded_session.sdk_session_id}")
```
### Example 4: CLI Integration
```bash
# First execution - creates session
python -m sdk_workflow --mode streaming \
  --task "Start analyzing project structure" \
  --save-session my_analysis
# Session ID captured and stored in:
# ~/.claude/sdk-workflow/sessions/my_analysis.json
# Resume later
python -m sdk_workflow --mode streaming \
  --task "Continue the analysis" \
  --resume-session my_analysis
```
## Data Flow
```
1. User initiates streaming execution
   ↓
2. StreamingExecutor creates ClaudeAgentOptions
   ├─ If resume_session_id provided → pass to options.resume
   └─ If new session → no resume parameter
   ↓
3. SDK returns messages with init subtype
   ├─ Contains session_id in message.data
   └─ extract_session_id_from_message() captures it
   ↓
4. StreamingExecutor stores SDK session ID
   ├─ Sets self._sdk_session_id
   └─ Updates SessionManager if available
   ↓
5. Session persisted to JSON with sdk_session_id field
   ↓
6. Future executions can resume by loading sdk_session_id
```
## Session State Schema
```json
{
  "id": "sess_abc123",
  "mode": "streaming",
  "task": "Analyze codebase",
  "status": "running",
  "model": "claude-sonnet-4-20250514",
  "created_at": "2025-01-01T00:00:00",
  "updated_at": "2025-01-01T00:05:00",
  "system_prompt": "You are a code analyst",
  "messages": [...],
  "metadata": {},
  "error": null,
  "result": null,
  "sdk_session_id": "sdk_abc123xyz"  // NEW FIELD
}
```
## API Reference
### AgentClientManager
```python
class AgentClientManager:
    def capture_session_id(self, message: AssistantMessage) -> None:
        """Capture session ID from SDK message."""
    def get_current_session_id(self) -> Optional[str]:
        """Get current SDK session ID."""
    def clear_session_id(self) -> None:
        """Clear session state."""
    def create_options(
        self,
        ...,
        resume: Optional[str] = None,
        ...
    ) -> ClaudeAgentOptions:
        """Create options with resume support."""
```
### Session
```python
@dataclass
class Session:
    ...
    sdk_session_id: Optional[str] = None
    def save_to_file(self, file_path: Path) -> None:
        """Save session to JSON file."""
    @classmethod
    def load_from_file(cls, file_path: Path) -> "Session":
        """Load session from JSON file."""
```
### SessionManager
```python
class SessionManager:
    def create(
        self,
        ...,
        sdk_session_id: Optional[str] = None
    ) -> Session:
        """Create session with SDK session ID."""
    def update(
        self,
        session_id: str,
        ...,
        sdk_session_id: Optional[str] = None
    ) -> Optional[Session]:
        """Update SDK session ID."""
```
### StreamingExecutor
```python
class StreamingExecutor:
    def __init__(
        self,
        ...,
        resume_session_id: Optional[str] = None
    ):
        """Initialize with resume capability."""
    def get_sdk_session_id(self) -> Optional[str]:
        """Get captured SDK session ID."""
```
## Testing
Run the test suite to verify implementation:
```bash
cd ~/.claude/sdk-workflow
python test_session_resume.py
```
Expected output:
```
============================================================
Session ID Capture and Resume - Test Suite
============================================================
Testing Session persistence...
 Saved session to test_session.json
 Loaded session from test_session.json
 Session data matches
 Test file cleaned up
 Session persistence test PASSED
Testing SessionManager...
 Created session sess_xxx
 SDK session ID stored correctly
 SDK session ID updated correctly
 Test storage cleaned up
 SessionManager test PASSED
Testing AgentClientManager session capture...
 Initial state correct
 Session ID clearing works
 create_options accepts resume parameter
 AgentClientManager test PASSED
============================================================
ALL TESTS PASSED
============================================================
```
## Backward Compatibility
All changes are backward compatible:
1. `sdk_session_id` is Optional - existing sessions work without it
2. `resume` parameter defaults to None - no resume by default
3. Existing code without resume continues to function
4. Session persistence maintains existing fields
5. New methods don't break existing APIs
## Future Enhancements
Potential improvements:
1. **Automatic resume detection** - Detect interrupted sessions and offer resume
2. **Session branching** - Fork sessions for parallel exploration
3. **Session merging** - Combine insights from multiple sessions
4. **Session search** - Find sessions by task content or metadata
5. **Session analytics** - Track usage patterns and success rates
