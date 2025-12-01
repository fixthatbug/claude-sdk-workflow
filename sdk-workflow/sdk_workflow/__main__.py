"""
Entry point for running sdk-workflow as a module.
Usage:
    python -m sdk_workflow --mode oneshot --task "Extract function names"
    python -m sdk_workflow --mode streaming --task "Refactor code" &
    python -m sdk_workflow --mode orchestrator --task "Build feature" --background
Can also be run directly:
    cd ~/.claude/sdk-workflow
    python __main__.py --help
"""
import sys
from pathlib import Path
# Add the sdk-workflow directory to sys.path so imports work
_sdk_root = Path(__file__).parent.absolute()
if str(_sdk_root) not in sys.path:
    sys.path.insert(0, str(_sdk_root))
# Now import and run
from cli.main import main
if __name__ == "__main__":
    sys.exit(main())
