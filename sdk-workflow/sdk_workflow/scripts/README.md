# SDK Workflow Utility Scripts
This directory contains utility scripts for maintaining and managing the SDK workflow project.
## Scripts
### system_cleanup.py
A comprehensive, modular cleanup infrastructure for maintaining the SDK workflow project. This production-ready script handles various cleanup operations including removing cache files, consolidating examples, organizing documentation, and restructuring the project layout.
#### Features
- **Modular Architecture**: Each cleanup operation is isolated in its own phase function
- **Dry-Run Mode**: Preview changes before applying them
- **Interactive Mode**: Confirm each operation before execution
- **Metrics Collection**: Detailed statistics on files moved, deleted, and space saved
- **Safety Features**: Automatic backups, path validation, error handling, and rollback capability
- **Progress Reporting**: Clear status updates with color-coded output
- **Report Generation**: JSON and text reports with comprehensive metrics
#### Cleanup Phases
1. **Phase 1: Clean Python Cache** - Remove `__pycache__` directories and `.pyc` files
2. **Phase 2: Consolidate Examples** - Move all example files to `examples/` directory
3. **Phase 3: Organize Documentation** - Organize markdown files into `docs/` with categorization
4. **Phase 4: Consolidate Tests** - Move all test files to `tests/` directory
5. **Phase 5: Organize Root** - Clean and organize root directory
6. **Phase 6: Analyze Managers** - Analyze and report on manager module usage
7. **Phase 7: Organize Scripts** - Organize utility scripts into `scripts/` directory
#### Usage
Run scripts from the project root:
```bash
# Show help and usage information
python sdk_workflow/scripts/system_cleanup.py --help
# Run all phases in dry-run mode (safe preview)
python sdk_workflow/scripts/system_cleanup.py --all --dry-run
# Run a specific phase
python sdk_workflow/scripts/system_cleanup.py --phase 1
# Run multiple phases interactively
python sdk_workflow/scripts/system_cleanup.py --phase 1 --phase 2 --interactive
# Generate analysis report only
python sdk_workflow/scripts/system_cleanup.py --report
# Run all phases and save detailed reports
python sdk_workflow/scripts/system_cleanup.py --all --output ./my_reports
# Run cleanup live (make actual changes)
python sdk_workflow/scripts/system_cleanup.py --all
```
#### Command-Line Options
- `--phase N` - Run specific phase (1-7). Can be specified multiple times
- `--all` - Run all phases sequentially
- `--dry-run` - Show what would be done without making changes
- `--report` - Generate metrics report only (no changes)
- `--interactive` - Prompt before each change
- `--output DIR` - Save reports to specific directory
#### Output
The script provides:
- **Real-time progress updates** with color-coded status messages
- **Summary table** showing metrics for each phase
- **Detailed reports** saved as JSON and text files in `cleanup_reports/` directory
- **Backup files** in `backup/` directory (when making actual changes)
#### Example Output
```
================================================================================
                            SYSTEM CLEANUP - DRY RUN
================================================================================
Project root: C:\Users\Ray\.claude\sdk-workflow
Phases to run: 1
================================================================================
                          PHASE 1: Clean Python Cache
================================================================================
>>> Found 12 __pycache__ directories
>>> Found 47 .pyc files
>>> Total size to be freed: 1.27 MB
[OK] Phase 1 completed in 0.02s
[OK] Freed: 1.27 MB
================================================================================
                                CLEANUP SUMMARY
================================================================================
Phase      Name                           Files      Moved      Deleted    Size
-------------------------------------------------------------------------------------
1          Clean Python Cache             59         0          47         1.27 MB
-------------------------------------------------------------------------------------
TOTAL                                     59                               1.27 MB
[OK] Cleanup completed successfully!
```
#### Safety Features
1. **Automatic Backups**: Files are backed up before deletion/movement
2. **Dry-Run Mode**: Preview all changes before applying them
3. **Interactive Mode**: Confirm each operation
4. **Path Validation**: Checks paths before operations
5. **Error Handling**: Graceful error handling with detailed messages
6. **Protected Files**: Preserves important files (README.md, LICENSE, etc.)
#### Report Files
Reports are saved in `cleanup_reports/` directory:
- `cleanup_report_YYYYMMDD_HHMMSS.json` - Machine-readable JSON format
- `cleanup_report_YYYYMMDD_HHMMSS.txt` - Human-readable text format
Each report includes:
- Timestamp and execution mode
- Metrics for each phase executed
- Files affected, moved, deleted
- Space saved
- Warnings and errors
- Duration statistics
#### Architecture
The script follows a modular design:
```
system_cleanup.py
├── Constants & Configuration
├── Data Classes (PhaseMetrics, CleanupReport)
├── Utility Functions
│   ├── Print functions (with color coding)
│   ├── File operations (safe_move, safe_delete, safe_backup)
│   └── Helper functions (format_size, count_lines, etc.)
├── Cleanup Phases (7 phase functions)
├── Report Generation
└── Main Execution & CLI Interface
```
#### Best Practices
1. **Always run with --dry-run first** to preview changes
2. **Review the output** before running in live mode
3. **Use --interactive** for careful, step-by-step execution
4. **Keep backups** until you verify changes are correct
5. **Run phases incrementally** rather than all at once initially
6. **Check reports** for warnings about potential issues
#### Development
The script is designed to be extended with additional phases. To add a new phase:
1. Create a new phase function following the naming pattern `phase_N_description()`
2. Return a `PhaseMetrics` object with collected statistics
3. Add the phase to the `all_phases` dictionary in `run_cleanup()`
4. Update this README with the new phase documentation
#### Requirements
- Python 3.7+
- Standard library only (no external dependencies)
- Cross-platform compatible (Windows, Linux, macOS)
#### Exit Codes
- `0` - Success
- `1` - Error occurred during execution
- `130` - Cancelled by user (Ctrl+C)
## Contributing
When adding new scripts to this directory:
1. Follow PEP 8 style guidelines
2. Include comprehensive docstrings
3. Add type hints for all functions
4. Implement proper error handling
5. Update this README with usage documentation
6. Make scripts executable with proper shebang (`#!/usr/bin/env python3`)
## License
Same license as the SDK Workflow project.
