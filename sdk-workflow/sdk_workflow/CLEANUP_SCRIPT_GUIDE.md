# System Cleanup Script Guide
**Script Location:** sdk_workflow/scripts/system_cleanup.py
**Version:** 1.0
**Last Updated:** December 1, 2025
---
## Overview
The system_cleanup.py script is an automated utility designed to help organize and maintain the SDK Workflow project structure. It provides phased cleanup operations that can be run individually or combined, with built-in safety features like dry-run mode and backups.
### What It Does
The script performs seven distinct cleanup phases:
1. **Phase 1:** Clean Python cache (__pycache__, .pyc files)
2. **Phase 2:** Consolidate duplicate example files
3. **Phase 3:** Organize documentation files
4. **Phase 4:** Consolidate test files
5. **Phase 5:** Organize root directory
6. **Phase 6:** Analyze manager modules
7. **Phase 7:** Organize script files
### Why Use It
- Automated: Reduces manual work and human error
- Safe: Dry-run mode and backups prevent accidental data loss
- Flexible: Run individual phases or all phases at once
- Transparent: Detailed reports show what changed and why
- Reversible: Automatic backups enable rollback if needed
---
## Prerequisites & Installation
### Requirements
- Python 3.8 or higher
- Write permissions to project root directory
- 50 MB free disk space (for backups during cleanup)
- No open file locks in project directories
### Setup
Make the script executable (on Unix/Linux/Mac):
```bash
chmod +x sdk_workflow/scripts/system_cleanup.py
```
Verify it works:
```bash
python sdk_workflow/scripts/system_cleanup.py --help
```
---
## Usage Examples
### Dry-Run Mode (Safe Preview)
Preview all changes without modifying anything:
```bash
python sdk_workflow/scripts/system_cleanup.py --all --dry-run
```
### Single Phase Execution
Clean Python cache only:
```bash
python sdk_workflow/scripts/system_cleanup.py --phase 1
```
### All Phases at Once
Execute all cleanup phases sequentially:
```bash
python sdk_workflow/scripts/system_cleanup.py --all
```
### Interactive Mode
Run with confirmations before each operation:
```bash
python sdk_workflow/scripts/system_cleanup.py --all --interactive
```
### Report-Only Mode
Generate a detailed report without making changes:
```bash
python sdk_workflow/scripts/system_cleanup.py --report
```
---
## Safety Features
### Dry-Run Mode
Preview changes without modification by using the --dry-run flag.
### Interactive Mode
Pause for confirmation before each operation by using the --interactive flag.
### Automatic Backups
Script creates backups in Backup/ directory before executing cleanup.
### Detailed Reporting
Generate comprehensive change report using the --report flag.
---
## Best Practices
### Before Running Cleanup
1. Commit your code
2. Run dry-run mode first
3. Review the output carefully
### During Cleanup
1. Use interactive mode for first-time use
2. Do not interrupt the process
3. Wait for final status
### After Cleanup
1. Run tests immediately
2. Check imports
3. Commit results
---
## FAQ
**Q: Will cleanup break my code?**
A: No, cleanup only reorganizes files. Code functionality is not changed. Backups allow rollback if needed.
**Q: How long does cleanup take?**
A: Typically 2-5 minutes depending on project size.
**Q: Can I undo cleanup?**
A: Yes! Backups are created automatically in the Backup/ directory.
**Q: Do I need to run all phases?**
A: No, you can run individual phases as needed.
---
## Related Documents
- [CLEANUP_STATUS.md](./CLEANUP_STATUS.md) - Current cleanup progress
- [CLEANUP_ROADMAP.md](./CLEANUP_ROADMAP.md) - Multi-phase cleanup strategy
- [system_cleanup.py](./scripts/system_cleanup.py) - Script source code
