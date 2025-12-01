# Archived Modules
This directory contains deprecated modules that have been removed from active development.
## Archived Components
### mailbox_system/
**Deprecated:** 2025-01-XX
**Reason:** Replaced by TodoWrite-based progress tracking
The mailbox system was an inter-agent communication mechanism that has been superseded by TodoWrite for progress tracking. The mailbox approach added complexity without providing significant benefits over TodoWrite's built-in progress tracking capabilities.
**Migration:** Use TodoWrite tool for all progress tracking. See `/docs/TODOWRITE_BEST_PRACTICES.md` and `/docs/TODOWRITE_EXAMPLES.md`.
**Files archived:**
- `mailbox.py` - Core mailbox implementation
- `mailbox_protocol.py` - Message protocol definitions
- `mailbox_integration.py` - Orchestrator integration mixin
- `mailbox_events.py` - Event-driven mailbox handlers
- `progress_mailbox.py` - Progress reporting via mailbox
- `session_mailbox.py` - Session-based mailbox management
- `mailbox_example.py` - Usage examples
- `mailbox_messagebus_integration_example.py` - Integration examples
- `test_mailbox.py` - Unit tests
### session_viewer/
**Deprecated:** 2025-01-XX
**Reason:** Limited utility, not actively maintained
The session parser was a utility for extracting text from Claude session JSONL files. It was not actively used in the SDK workflow and added minimal value.
**Files archived:**
- `session_parser.py` - Session JSONL parser
## Archive Policy
Archived modules:
- Are NOT maintained or updated
- May be removed entirely in future major versions
- Should NOT be imported or used in new code
- Are kept temporarily for reference and emergency recovery
**Do not use archived modules in production code.**
