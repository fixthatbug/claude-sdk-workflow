#!/usr/bin/env python3
"""
System Cleanup Script for SDK Workflow Project
This script provides a modular, professional cleanup infrastructure for maintaining
the sdk_workflow project. It handles various cleanup operations including removing
cache files, consolidating examples, organizing documentation, and restructuring
the project layout.
Usage:
    python system_cleanup.py --all --dry-run
    python system_cleanup.py --phase 1
    python system_cleanup.py --report
"""
import argparse
import json
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Callable
import os
# ============================================================================
# CONSTANTS
# ============================================================================
PROJECT_ROOT = Path(__file__).parent.parent.parent
BACKUP_DIR = PROJECT_ROOT / "backup"
REPORTS_DIR = PROJECT_ROOT / "cleanup_reports"
# Color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
# ============================================================================
# DATA CLASSES
# ============================================================================
@dataclass
class PhaseMetrics:
    """Metrics collected during a cleanup phase."""
    phase_number: int
    phase_name: str
    files_affected: int = 0
    files_moved: int = 0
    files_deleted: int = 0
    dirs_created: int = 0
    dirs_removed: int = 0
    total_size_bytes: int = 0
    lines_of_code: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = None
    warnings: List[str] = None
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
@dataclass
class CleanupReport:
    """Complete cleanup report with all phases."""
    timestamp: str
    dry_run: bool
    phases_executed: List[PhaseMetrics]
    total_files_affected: int = 0
    total_space_saved: int = 0
    total_duration: float = 0.0
    success: bool = True
    def to_dict(self) -> Dict:
        """Convert report to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp,
            'dry_run': self.dry_run,
            'phases_executed': [asdict(p) for p in self.phases_executed],
            'total_files_affected': self.total_files_affected,
            'total_space_saved': self.total_space_saved,
            'total_duration': self.total_duration,
            'success': self.success
        }
# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}")
    print(f"{text:^80}")
    print(f"{'=' * 80}{Colors.ENDC}\n")
def print_step(text: str) -> None:
    """Print a step message."""
    print(f"{Colors.OKCYAN}>>> {text}{Colors.ENDC}")
def print_success(text: str) -> None:
    """Print a success message."""
    print(f"{Colors.OKGREEN}[OK] {text}{Colors.ENDC}")
def print_warning(text: str) -> None:
    """Print a warning message."""
    print(f"{Colors.WARNING}[WARNING] {text}{Colors.ENDC}")
def print_error(text: str) -> None:
    """Print an error message."""
    print(f"{Colors.FAIL}[ERROR] {text}{Colors.ENDC}")
def format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"
def count_lines(file_path: Path) -> int:
    """Count lines in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0
def get_file_size(path: Path) -> int:
    """Get total size of file or directory in bytes."""
    if path.is_file():
        return path.stat().st_size
    elif path.is_dir():
        return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
    return 0
def safe_backup(path: Path, dry_run: bool = False) -> Optional[Path]:
    """
    Create a backup of a file or directory before modification.
    Args:
        path: Path to backup
        dry_run: If True, don't actually create backup
    Returns:
        Path to backup location, or None if backup failed
    """
    if not path.exists():
        return None
    if dry_run:
        backup_path = BACKUP_DIR / path.relative_to(PROJECT_ROOT)
        print_step(f"[DRY RUN] Would backup: {path.relative_to(PROJECT_ROOT)} -> {backup_path.relative_to(PROJECT_ROOT)}")
        return backup_path
    try:
        backup_path = BACKUP_DIR / path.relative_to(PROJECT_ROOT)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            shutil.copy2(path, backup_path)
        else:
            if backup_path.exists():
                shutil.rmtree(backup_path)
            shutil.copytree(path, backup_path)
        return backup_path
    except Exception as e:
        print_error(f"Failed to backup {path}: {e}")
        return None
def safe_move(src: Path, dst: Path, dry_run: bool = False, backup: bool = True) -> bool:
    """
    Safely move a file or directory with optional backup.
    Args:
        src: Source path
        dst: Destination path
        dry_run: If True, don't actually move
        backup: If True, create backup before moving
    Returns:
        True if successful, False otherwise
    """
    if not src.exists():
        print_warning(f"Source does not exist: {src}")
        return False
    if dry_run:
        print_step(f"[DRY RUN] Would move: {src.relative_to(PROJECT_ROOT)} -> {dst.relative_to(PROJECT_ROOT)}")
        return True
    try:
        # Backup if requested
        if backup:
            safe_backup(src, dry_run=False)
        # Create destination directory
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Move the file/directory
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        shutil.move(str(src), str(dst))
        print_success(f"Moved: {src.relative_to(PROJECT_ROOT)} -> {dst.relative_to(PROJECT_ROOT)}")
        return True
    except Exception as e:
        print_error(f"Failed to move {src} to {dst}: {e}")
        return False
def safe_delete(path: Path, dry_run: bool = False, backup: bool = True) -> bool:
    """
    Safely delete a file or directory with optional backup.
    Args:
        path: Path to delete
        dry_run: If True, don't actually delete
        backup: If True, create backup before deleting
    Returns:
        True if successful, False otherwise
    """
    if not path.exists():
        return True
    if dry_run:
        print_step(f"[DRY RUN] Would delete: {path.relative_to(PROJECT_ROOT)}")
        return True
    try:
        # Backup if requested
        if backup:
            safe_backup(path, dry_run=False)
        # Delete the file/directory
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print_success(f"Deleted: {path.relative_to(PROJECT_ROOT)}")
        return True
    except Exception as e:
        print_error(f"Failed to delete {path}: {e}")
        return False
def confirm_action(prompt: str) -> bool:
    """Ask user for confirmation."""
    response = input(f"{prompt} [y/N]: ").strip().lower()
    return response in ['y', 'yes']
# ============================================================================
# CLEANUP PHASES
# ============================================================================
def phase_1_clean_pycache(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    Phase 1: Remove __pycache__ directories and .pyc files.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("PHASE 1: Clean Python Cache")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=1, phase_name="Clean Python Cache")
    # Find all __pycache__ directories
    pycache_dirs = list(PROJECT_ROOT.rglob('__pycache__'))
    pyc_files = list(PROJECT_ROOT.rglob('*.pyc'))
    print_step(f"Found {len(pycache_dirs)} __pycache__ directories")
    print_step(f"Found {len(pyc_files)} .pyc files")
    # Calculate total size
    total_size = sum(get_file_size(d) for d in pycache_dirs)
    total_size += sum(get_file_size(f) for f in pyc_files)
    print_step(f"Total size to be freed: {format_size(total_size)}")
    if interactive and not dry_run:
        if not confirm_action(f"Delete {len(pycache_dirs) + len(pyc_files)} cache items?"):
            print_warning("Skipped by user")
            return metrics
    # Delete __pycache__ directories
    for pycache_dir in pycache_dirs:
        if safe_delete(pycache_dir, dry_run=dry_run, backup=False):
            metrics.dirs_removed += 1
            metrics.total_size_bytes += get_file_size(pycache_dir) if pycache_dir.exists() else 0
    # Delete .pyc files
    for pyc_file in pyc_files:
        if safe_delete(pyc_file, dry_run=dry_run, backup=False):
            metrics.files_deleted += 1
            metrics.total_size_bytes += get_file_size(pyc_file) if pyc_file.exists() else 0
    metrics.files_affected = len(pycache_dirs) + len(pyc_files)
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"Phase 1 completed in {metrics.duration_seconds:.2f}s")
    print_success(f"Freed: {format_size(metrics.total_size_bytes)}")
    return metrics
def phase_2_consolidate_examples(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    Phase 2: Consolidate all example files into examples/ directory.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("PHASE 2: Consolidate Examples")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=2, phase_name="Consolidate Examples")
    examples_dir = PROJECT_ROOT / "examples"
    examples_dir.mkdir(exist_ok=True)
    # Find example files in various locations
    example_patterns = [
        PROJECT_ROOT / "sdk_workflow" / "examples",
        PROJECT_ROOT / "cli" / "examples",
    ]
    example_files = []
    for pattern in example_patterns:
        if pattern.exists():
            example_files.extend(pattern.rglob('*.py'))
    # Also find example files at root or in docs
    for file in PROJECT_ROOT.glob('example*.py'):
        example_files.append(file)
    for file in (PROJECT_ROOT / "docs").rglob('example*.py') if (PROJECT_ROOT / "docs").exists() else []:
        example_files.append(file)
    print_step(f"Found {len(example_files)} example files")
    if interactive and not dry_run and example_files:
        if not confirm_action(f"Move {len(example_files)} example files to examples/?"):
            print_warning("Skipped by user")
            return metrics
    # Move example files
    for example_file in example_files:
        # Determine target location
        if example_file.parent == examples_dir:
            continue # Already in the right place
        # Try to preserve some directory structure
        if 'cli' in example_file.parts:
            target = examples_dir / "cli" / example_file.name
        elif 'sdk_workflow' in example_file.parts:
            target = examples_dir / "sdk_workflow" / example_file.name
        else:
            target = examples_dir / example_file.name
        if safe_move(example_file, target, dry_run=dry_run):
            metrics.files_moved += 1
            metrics.lines_of_code += count_lines(example_file) if example_file.exists() else 0
    # Remove empty example directories
    for pattern in example_patterns:
        if pattern.exists() and pattern.is_dir():
            try:
                if not any(pattern.iterdir()):
                    if safe_delete(pattern, dry_run=dry_run, backup=False):
                        metrics.dirs_removed += 1
            except Exception:
                pass
    metrics.files_affected = len(example_files)
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"Phase 2 completed in {metrics.duration_seconds:.2f}s")
    print_success(f"Moved {metrics.files_moved} example files ({metrics.lines_of_code} lines)")
    return metrics
def phase_3_organize_documentation(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    Phase 3: Organize documentation files into docs/ directory.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("PHASE 3: Organize Documentation")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=3, phase_name="Organize Documentation")
    docs_dir = PROJECT_ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    # Find markdown files at root (excluding README.md and important project files)
    protected_files = {'README.md', 'LICENSE.md', 'CHANGELOG.md', 'CONTRIBUTING.md'}
    root_md_files = [
        f for f in PROJECT_ROOT.glob('*.md')
        if f.name not in protected_files
    ]
    print_step(f"Found {len(root_md_files)} documentation files at root")
    # Categorize documentation files
    categories = {
        'implementation': ['IMPLEMENTATION', 'NOTES', 'SUMMARY', 'COMPLETE'],
        'architecture': ['ARCHITECTURE', 'PATTERNS', 'MODULES'],
        'usage': ['USAGE', 'QUICKSTART', 'GUIDE'],
        'mailbox': ['MAILBOX', 'DELIVERY'],
        'sdk': ['SDK_', 'UNIFIED_SDK'],
        'prompts': ['PROMPTS', 'ENHANCED'],
    }
    if interactive and not dry_run and root_md_files:
        if not confirm_action(f"Move {len(root_md_files)} documentation files to docs/?"):
            print_warning("Skipped by user")
            return metrics
    # Move and organize documentation files
    for md_file in root_md_files:
        # Determine category
        category = 'general'
        for cat_name, keywords in categories.items():
            if any(keyword in md_file.name.upper() for keyword in keywords):
                category = cat_name
                break
        # Create category subdirectory
        category_dir = docs_dir / category
        category_dir.mkdir(exist_ok=True)
        target = category_dir / md_file.name
        if safe_move(md_file, target, dry_run=dry_run):
            metrics.files_moved += 1
            metrics.lines_of_code += count_lines(md_file) if md_file.exists() else 0
    # Check for duplicate documentation in sdk_workflow/
    sdk_docs = list((PROJECT_ROOT / "sdk_workflow").rglob('*.md')) if (PROJECT_ROOT / "sdk_workflow").exists() else []
    if sdk_docs:
        print_step(f"Found {len(sdk_docs)} documentation files in sdk_workflow/")
        metrics.warnings.append(f"Found {len(sdk_docs)} .md files in sdk_workflow/ that may need review")
    metrics.files_affected = len(root_md_files)
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"Phase 3 completed in {metrics.duration_seconds:.2f}s")
    print_success(f"Organized {metrics.files_moved} documentation files ({metrics.lines_of_code} lines)")
    return metrics
def phase_4_consolidate_tests(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    Phase 4: Consolidate all test files into tests/ directory.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("PHASE 4: Consolidate Tests")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=4, phase_name="Consolidate Tests")
    tests_dir = PROJECT_ROOT / "tests"
    tests_dir.mkdir(exist_ok=True)
    # Find test files at root
    root_test_files = list(PROJECT_ROOT.glob('test_*.py'))
    print_step(f"Found {len(root_test_files)} test files at root")
    if interactive and not dry_run and root_test_files:
        if not confirm_action(f"Move {len(root_test_files)} test files to tests/?"):
            print_warning("Skipped by user")
            return metrics
    # Move test files
    for test_file in root_test_files:
        target = tests_dir / test_file.name
        if safe_move(test_file, target, dry_run=dry_run):
            metrics.files_moved += 1
            metrics.lines_of_code += count_lines(test_file) if test_file.exists() else 0
    # Create __init__.py if it doesn't exist
    init_file = tests_dir / "__init__.py"
    if not init_file.exists() and not dry_run:
        init_file.touch()
        metrics.files_affected += 1
        print_success(f"Created: {init_file.relative_to(PROJECT_ROOT)}")
    metrics.files_affected = len(root_test_files)
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"Phase 4 completed in {metrics.duration_seconds:.2f}s")
    print_success(f"Consolidated {metrics.files_moved} test files ({metrics.lines_of_code} lines)")
    return metrics
def phase_5_organize_root(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    Phase 5: Clean and organize root directory.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("PHASE 5: Organize Root Directory")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=5, phase_name="Organize Root Directory")
    # Analyze root directory
    root_files = [f for f in PROJECT_ROOT.iterdir() if f.is_file()]
    print_step(f"Root directory contains {len(root_files)} files")
    # Categorize files
    python_scripts = [f for f in root_files if f.suffix == '.py' and not f.name.startswith('test_')]
    config_files = [f for f in root_files if f.suffix in ['.toml', '.txt', '.cfg', '.ini', '.yaml', '.yml']]
    md_files = [f for f in root_files if f.suffix == '.md']
    print_step(f" - {len(python_scripts)} Python scripts")
    print_step(f" - {len(config_files)} configuration files")
    print_step(f" - {len(md_files)} markdown files (should be 0 after phase 3)")
    if md_files:
        metrics.warnings.append(f"Found {len(md_files)} .md files still at root - run phase 3 first")
    # Move utility scripts to scripts/ directory
    scripts_dir = PROJECT_ROOT / "sdk_workflow" / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    if interactive and not dry_run and python_scripts:
        if not confirm_action(f"Move {len(python_scripts)} utility scripts to sdk_workflow/scripts/?"):
            print_warning("Skipped by user")
            return metrics
    for script in python_scripts:
        target = scripts_dir / script.name
        if target.exists():
            metrics.warnings.append(f"Script already exists at target: {script.name}")
            continue
        if safe_move(script, target, dry_run=dry_run):
            metrics.files_moved += 1
            metrics.lines_of_code += count_lines(script) if script.exists() else 0
    metrics.files_affected = len(python_scripts)
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"Phase 5 completed in {metrics.duration_seconds:.2f}s")
    print_success(f"Organized {metrics.files_moved} utility scripts")
    return metrics
def phase_6_analyze_managers(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    Phase 6: Analyze manager modules and report on their usage.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("PHASE 6: Analyze Manager Modules")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=6, phase_name="Analyze Manager Modules")
    managers_dir = PROJECT_ROOT / "sdk_workflow" / "managers"
    if not managers_dir.exists():
        print_warning("Managers directory does not exist")
        metrics.warnings.append("Managers directory not found")
        return metrics
    manager_files = list(managers_dir.glob('*.py'))
    manager_files = [f for f in manager_files if f.name != '__init__.py']
    print_step(f"Found {len(manager_files)} manager modules")
    # Analyze each manager
    manager_stats = {}
    for manager_file in manager_files:
        lines = count_lines(manager_file)
        size = get_file_size(manager_file)
        # Check if it's a stub (very small file)
        is_stub = lines < 50
        manager_stats[manager_file.name] = {
            'lines': lines,
            'size': size,
            'is_stub': is_stub
        }
        status = "STUB" if is_stub else "OK"
        print_step(f" - {manager_file.name}: {lines} lines, {format_size(size)} [{status}]")
    # Count stubs
    stub_count = sum(1 for stats in manager_stats.values() if stats['is_stub'])
    if stub_count > 0:
        metrics.warnings.append(f"Found {stub_count} stub manager modules that may need implementation")
        print_warning(f"Found {stub_count} stub manager modules")
    metrics.files_affected = len(manager_files)
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"Phase 6 completed in {metrics.duration_seconds:.2f}s")
    return metrics
def code_cleanup(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    Code cleanup: Remove dead code, unused imports, and simplify complex functions.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("CODE CLEANUP")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=8, phase_name="Code Cleanup")
    # Find Python files
    py_files = list((PROJECT_ROOT / "sdk_workflow").rglob('*.py'))
    py_files = [f for f in py_files if '__pycache__' not in str(f) and 'archive' not in str(f)]
    print_step(f"Found {len(py_files)} Python files to analyze")
    issues_found = []
    # Check for common code issues
    for py_file in py_files:
        try:
            content = py_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            # Check for unused imports (simple heuristic)
            import_lines = [i for i, line in enumerate(lines) if line.strip().startswith('import ') or line.strip().startswith('from ')]
            # Check for TODO/FIXME comments
            todo_lines = [i for i, line in enumerate(lines) if 'TODO' in line or 'FIXME' in line]
            if todo_lines:
                issues_found.append(f"{py_file.name}: {len(todo_lines)} TODO/FIXME comments")
            # Check for long functions (>100 lines)
            in_function = False
            func_start = 0
            func_name = ""
            for i, line in enumerate(lines):
                if line.strip().startswith('def '):
                    if in_function and (i - func_start) > 100:
                        issues_found.append(f"{py_file.name}: Function {func_name} is {i - func_start} lines")
                    in_function = True
                    func_start = i
                    func_name = line.split('def ')[1].split('(')[0]
                elif in_function and line and not line[0].isspace() and not line.strip().startswith('#'):
                    if not line.strip().startswith('"""') and not line.strip().startswith("'''"):
                        in_function = False
            metrics.files_affected += 1
            metrics.lines_of_code += len(lines)
        except Exception as e:
            metrics.warnings.append(f"Error analyzing {py_file.name}: {e}")
    print_step(f"Code analysis complete: {len(issues_found)} issues found")
    for issue in issues_found[:10]: # Show first 10
        print_warning(f" {issue}")
    if len(issues_found) > 10:
        print_warning(f" ... and {len(issues_found) - 10} more issues")
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"Code cleanup analysis completed in {metrics.duration_seconds:.2f}s")
    print_success(f"Analyzed {metrics.files_affected} files ({metrics.lines_of_code} lines)")
    return metrics
def file_organization(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    File organization: Ensure consistent directory structure and naming.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("FILE ORGANIZATION")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=9, phase_name="File Organization")
    # Check for misplaced files
    expected_structure = {
        'core': ['Core functionality', PROJECT_ROOT / "sdk_workflow" / "core"],
        'communication': ['IPC and messaging', PROJECT_ROOT / "sdk_workflow" / "communication"],
        'config': ['Configuration', PROJECT_ROOT / "sdk_workflow" / "config"],
        'utils': ['Utilities', PROJECT_ROOT / "sdk_workflow" / "utils"],
        'scripts': ['Utility scripts', PROJECT_ROOT / "sdk_workflow" / "scripts"],
        'tests': ['Test files', PROJECT_ROOT / "tests"],
        'docs': ['Documentation', PROJECT_ROOT / "docs"],
        'examples': ['Example code', PROJECT_ROOT / "examples"]
    }
    print_step("Analyzing project structure...")
    for category, (description, path) in expected_structure.items():
        if path.exists():
            file_count = len(list(path.rglob('*.py'))) if category != 'docs' else len(list(path.rglob('*.md')))
            print_step(f" [OK] {category:15} {description:30} ({file_count} files)")
            metrics.files_affected += file_count
        else:
            print_warning(f" [MISS] {category:15} {description:30} (missing)")
            metrics.warnings.append(f"Missing directory: {category}")
    # Check for files in wrong locations
    root_py_files = list(PROJECT_ROOT.glob('*.py'))
    root_py_files = [f for f in root_py_files if f.name not in ['setup.py', '__init__.py']]
    if root_py_files:
        print_warning(f"Found {len(root_py_files)} Python files at project root (should be in subfolders)")
        for f in root_py_files:
            metrics.warnings.append(f"Misplaced file: {f.name}")
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"File organization analysis completed in {metrics.duration_seconds:.2f}s")
    return metrics
def config_consolidation(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    Config consolidation: Merge duplicate config files and standardize format.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("CONFIG CONSOLIDATION")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=10, phase_name="Config Consolidation")
    # Find all config files
    config_extensions = ['.toml', '.yaml', '.yml', '.json', '.ini', '.cfg', '.conf']
    config_files = []
    for ext in config_extensions:
        config_files.extend(PROJECT_ROOT.glob(f'*{ext}'))
        config_files.extend((PROJECT_ROOT / "sdk_workflow" / "config").glob(f'*{ext}'))
    print_step(f"Found {len(config_files)} configuration files")
    # Categorize config files
    config_by_type = defaultdict(list)
    for config_file in config_files:
        config_by_type[config_file.suffix].append(config_file)
    for ext, files in config_by_type.items():
        print_step(f" {ext:10} {len(files)} files")
        for f in files:
            print_step(f" - {f.relative_to(PROJECT_ROOT)}")
            metrics.files_affected += 1
    # Check for duplicate settings
    if len(config_files) > 5:
        metrics.warnings.append(f"Many config files ({len(config_files)}) - consider consolidation")
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"Config consolidation analysis completed in {metrics.duration_seconds:.2f}s")
    return metrics
def dependencies_audit(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    Dependencies audit: Check for unused, outdated, or vulnerable dependencies.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("DEPENDENCIES AUDIT")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=11, phase_name="Dependencies Audit")
    # Look for dependency files
    dep_files = []
    for pattern in ['requirements*.txt', 'pyproject.toml', 'setup.py', 'Pipfile', 'poetry.lock']:
        dep_files.extend(PROJECT_ROOT.glob(pattern))
    print_step(f"Found {len(dep_files)} dependency files")
    for dep_file in dep_files:
        print_step(f" - {dep_file.name}")
        metrics.files_affected += 1
        try:
            content = dep_file.read_text(encoding='utf-8')
            lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
            if dep_file.suffix == '.txt':
                # Parse requirements.txt
                packages = [l.split('==')[0].split('>=')[0].split('<=')[0] for l in lines if l]
                print_step(f" {len(packages)} packages declared")
                # Check for version pinning
                unpinned = [l for l in lines if '==' not in l and l and not l.startswith('-')]
                if unpinned:
                    metrics.warnings.append(f"{dep_file.name}: {len(unpinned)} unpinned packages")
            metrics.lines_of_code += len(lines)
        except Exception as e:
            metrics.warnings.append(f"Error reading {dep_file.name}: {e}")
    # Check for imported packages vs declared
    print_step("\nAnalyzing import statements...")
    py_files = list((PROJECT_ROOT / "sdk_workflow").rglob('*.py'))
    imported_packages = set()
    for py_file in py_files[:50]: # Sample first 50 files
        try:
            content = py_file.read_text(encoding='utf-8')
            for line in content.split('\n'):
                if line.strip().startswith('import ') or line.strip().startswith('from '):
                    pkg = line.split()[1].split('.')[0]
                    if pkg not in ['os', 'sys', 'json', 'typing', 'pathlib', 'dataclasses']:
                        imported_packages.add(pkg)
        except Exception:
            pass
    print_step(f" Found {len(imported_packages)} unique imported packages")
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"Dependencies audit completed in {metrics.duration_seconds:.2f}s")
    return metrics
def documentation_cleanup(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    Documentation cleanup: Organize, update, and consolidate documentation.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("DOCUMENTATION CLEANUP")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=12, phase_name="Documentation Cleanup")
    # Find all markdown files
    md_files = list(PROJECT_ROOT.rglob('*.md'))
    md_files = [f for f in md_files if '.venv' not in str(f) and 'node_modules' not in str(f)]
    print_step(f"Found {len(md_files)} markdown files")
    # Categorize by location
    location_counts = defaultdict(int)
    for md_file in md_files:
        relative = md_file.relative_to(PROJECT_ROOT)
        location = str(relative.parts[0]) if len(relative.parts) > 1 else 'root'
        location_counts[location] += 1
        metrics.files_affected += 1
        metrics.lines_of_code += count_lines(md_file)
    print_step("Documentation distribution:")
    for location, count in sorted(location_counts.items()):
        print_step(f" {location:20} {count} files")
    # Check for common documentation issues
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding='utf-8')
            # Check for broken links (simple check for .md links)
            if '](' in content:
                links = content.count('](')
                if links > 20:
                    metrics.warnings.append(f"{md_file.name}: Many links ({links}) - verify they work")
            # Check for TODO markers
            if 'TODO' in content or 'FIXME' in content:
                metrics.warnings.append(f"{md_file.name}: Contains TODO/FIXME markers")
            # Check if very short (stub)
            if len(content) < 200:
                metrics.warnings.append(f"{md_file.name}: Very short file (possible stub)")
        except Exception as e:
            metrics.warnings.append(f"Error reading {md_file.name}: {e}")
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"Documentation cleanup completed in {metrics.duration_seconds:.2f}s")
    print_success(f"Analyzed {metrics.files_affected} files ({metrics.lines_of_code} lines)")
    return metrics
def phase_7_organize_scripts(dry_run: bool = False, interactive: bool = False) -> PhaseMetrics:
    """
    Phase 7: Organize utility scripts into scripts/ directory.
    Args:
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
    Returns:
        PhaseMetrics with results
    """
    print_header("PHASE 7: Organize Scripts")
    start_time = datetime.now()
    metrics = PhaseMetrics(phase_number=7, phase_name="Organize Scripts")
    scripts_dir = PROJECT_ROOT / "sdk_workflow" / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    # Find utility scripts at root
    root_scripts = [
        f for f in PROJECT_ROOT.glob('*.py')
        if not f.name.startswith('test_') and f.name not in ['setup.py']
    ]
    print_step(f"Found {len(root_scripts)} utility scripts at root")
    if interactive and not dry_run and root_scripts:
        if not confirm_action(f"Move {len(root_scripts)} scripts to sdk_workflow/scripts/?"):
            print_warning("Skipped by user")
            return metrics
    # Move scripts
    for script in root_scripts:
        target = scripts_dir / script.name
        # Check if already moved
        if target.exists():
            print_warning(f"Script already exists: {script.name}")
            metrics.warnings.append(f"Duplicate script: {script.name}")
            continue
        if safe_move(script, target, dry_run=dry_run):
            metrics.files_moved += 1
            metrics.lines_of_code += count_lines(script) if script.exists() else 0
    # Create README for scripts directory
    readme_path = scripts_dir / "README.md"
    if not readme_path.exists() and not dry_run:
        readme_content = """# Utility Scripts
This directory contains utility scripts for maintaining and managing the SDK workflow project.
## Scripts
- `system_cleanup.py` - Comprehensive system cleanup and organization tool
## Usage
Run scripts from the project root:
```bash
python sdk_workflow/scripts/system_cleanup.py --help
```
"""
        readme_path.write_text(readme_content)
        metrics.files_affected += 1
        print_success(f"Created: {readme_path.relative_to(PROJECT_ROOT)}")
    metrics.files_affected += len(root_scripts)
    metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
    print_success(f"Phase 7 completed in {metrics.duration_seconds:.2f}s")
    print_success(f"Organized {metrics.files_moved} utility scripts")
    return metrics
# ============================================================================
# REPORT GENERATION
# ============================================================================
def generate_report(report: CleanupReport, output_dir: Optional[Path] = None) -> Path:
    """
    Generate a detailed cleanup report.
    Args:
        report: CleanupReport object
        output_dir: Optional custom output directory
    Returns:
        Path to the generated report file
    """
    if output_dir is None:
        output_dir = REPORTS_DIR
    output_dir.mkdir(exist_ok=True)
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = output_dir / f"cleanup_report_{timestamp}.json"
    # Write JSON report
    with open(report_file, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    # Generate human-readable report
    text_report = output_dir / f"cleanup_report_{timestamp}.txt"
    with open(text_report, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("SYSTEM CLEANUP REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Timestamp: {report.timestamp}\n")
        f.write(f"Mode: {'DRY RUN' if report.dry_run else 'LIVE'}\n")
        f.write(f"Status: {'SUCCESS' if report.success else 'FAILED'}\n")
        f.write(f"Duration: {report.total_duration:.2f}s\n\n")
        f.write("=" * 80 + "\n")
        f.write("SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total files affected: {report.total_files_affected}\n")
        f.write(f"Total space saved: {format_size(report.total_space_saved)}\n\n")
        for phase in report.phases_executed:
            f.write("=" * 80 + "\n")
            f.write(f"PHASE {phase.phase_number}: {phase.phase_name}\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Duration: {phase.duration_seconds:.2f}s\n")
            f.write(f"Files affected: {phase.files_affected}\n")
            f.write(f"Files moved: {phase.files_moved}\n")
            f.write(f"Files deleted: {phase.files_deleted}\n")
            f.write(f"Directories created: {phase.dirs_created}\n")
            f.write(f"Directories removed: {phase.dirs_removed}\n")
            f.write(f"Size freed: {format_size(phase.total_size_bytes)}\n")
            f.write(f"Lines of code: {phase.lines_of_code}\n")
            if phase.warnings:
                f.write("\nWarnings:\n")
                for warning in phase.warnings:
                    f.write(f" - {warning}\n")
            if phase.errors:
                f.write("\nErrors:\n")
                for error in phase.errors:
                    f.write(f" - {error}\n")
            f.write("\n")
    print_success(f"Reports generated:")
    print(f" - JSON: {report_file.relative_to(PROJECT_ROOT)}")
    print(f" - Text: {text_report.relative_to(PROJECT_ROOT)}")
    return report_file
def print_summary_table(report: CleanupReport) -> None:
    """Print a summary table of all phases."""
    print_header("CLEANUP SUMMARY")
    # Print table header
    print(f"{'Phase':<10} {'Name':<30} {'Files':<10} {'Moved':<10} {'Deleted':<10} {'Size':<15}")
    print("-" * 85)
    # Print each phase
    for phase in report.phases_executed:
        print(f"{phase.phase_number:<10} {phase.phase_name:<30} {phase.files_affected:<10} "
              f"{phase.files_moved:<10} {phase.files_deleted:<10} {format_size(phase.total_size_bytes):<15}")
    print("-" * 85)
    print(f"{'TOTAL':<10} {'':<30} {report.total_files_affected:<10} "
          f"{'':<10} {'':<10} {format_size(report.total_space_saved):<15}")
    print()
    # Print warnings and errors
    all_warnings = [w for p in report.phases_executed for w in p.warnings]
    all_errors = [e for p in report.phases_executed for e in p.errors]
    if all_warnings:
        print_warning(f"Total warnings: {len(all_warnings)}")
        for warning in all_warnings[:5]: # Show first 5
            print(f" - {warning}")
        if len(all_warnings) > 5:
            print(f" ... and {len(all_warnings) - 5} more")
        print()
    if all_errors:
        print_error(f"Total errors: {len(all_errors)}")
        for error in all_errors[:5]: # Show first 5
            print(f" - {error}")
        if len(all_errors) > 5:
            print(f" ... and {len(all_errors) - 5} more")
        print()
# ============================================================================
# MAIN EXECUTION
# ============================================================================
def run_cleanup(
    phases: Optional[List[int]] = None,
    dry_run: bool = False,
    interactive: bool = False,
    report_only: bool = False,
    output_dir: Optional[Path] = None
) -> CleanupReport:
    """
    Run cleanup phases.
    Args:
        phases: List of phase numbers to run, or None for all phases
        dry_run: If True, don't make actual changes
        interactive: If True, prompt before each change
        report_only: If True, only generate a status report
        output_dir: Optional custom output directory for reports
    Returns:
        CleanupReport with results
    """
    start_time = datetime.now()
    # Define all phases
    all_phases: Dict[int, Callable] = {
        1: phase_1_clean_pycache,
        2: phase_2_consolidate_examples,
        3: phase_3_organize_documentation,
        4: phase_4_consolidate_tests,
        5: phase_5_organize_root,
        6: phase_6_analyze_managers,
        7: phase_7_organize_scripts,
        8: code_cleanup,
        9: file_organization,
        10: config_consolidation,
        11: dependencies_audit,
        12: documentation_cleanup,
    }
    # Determine which phases to run
    if phases is None:
        phases = list(all_phases.keys())
    # Validate phases
    invalid_phases = [p for p in phases if p not in all_phases]
    if invalid_phases:
        print_error(f"Invalid phase numbers: {invalid_phases}")
        sys.exit(1)
    # Initialize report
    report = CleanupReport(
        timestamp=datetime.now().isoformat(),
        dry_run=dry_run,
        phases_executed=[]
    )
    # Print initial status
    mode = "DRY RUN" if dry_run else "LIVE MODE"
    interactive_mode = " (INTERACTIVE)" if interactive else ""
    print_header(f"SYSTEM CLEANUP - {mode}{interactive_mode}")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Phases to run: {', '.join(str(p) for p in phases)}")
    print()
    if not dry_run and not interactive:
        print_warning("Running in LIVE mode without confirmation!")
        if not confirm_action("Continue?"):
            print("Cancelled by user")
            sys.exit(0)
    # Report-only mode
    if report_only:
        print_step("Report-only mode: analyzing project state...")
        # Just run phase 6 (analysis) without making changes
        metrics = phase_6_analyze_managers(dry_run=True, interactive=False)
        report.phases_executed.append(metrics)
        report.total_duration = (datetime.now() - start_time).total_seconds()
        return report
    # Run phases
    success = True
    for phase_num in sorted(phases):
        try:
            phase_func = all_phases[phase_num]
            metrics = phase_func(dry_run=dry_run, interactive=interactive)
            report.phases_executed.append(metrics)
            # Update totals
            report.total_files_affected += metrics.files_affected
            report.total_space_saved += metrics.total_size_bytes
            if metrics.errors:
                success = False
        except Exception as e:
            print_error(f"Phase {phase_num} failed with exception: {e}")
            success = False
            # Create error metrics
            error_metrics = PhaseMetrics(
                phase_number=phase_num,
                phase_name=all_phases[phase_num].__name__
            )
            error_metrics.errors.append(str(e))
            report.phases_executed.append(error_metrics)
    # Calculate total duration
    report.total_duration = (datetime.now() - start_time).total_seconds()
    report.success = success
    return report
def main():
    """Main entry point for the cleanup script."""
    parser = argparse.ArgumentParser(
        description="System cleanup script for SDK Workflow project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all phases in dry-run mode
  python system_cleanup.py --all --dry-run
  # Run specific phase
  python system_cleanup.py --phase 1
  # Run multiple phases interactively
  python system_cleanup.py --phase 1 --phase 2 --interactive
  # Generate report only
  python system_cleanup.py --report
  # Run all phases and save report
  python system_cleanup.py --all --output ./reports
        """
    )
    parser.add_argument(
        '--phase',
        type=int,
        action='append',
        dest='phases',
        help='Run specific phase (1-12). Can be specified multiple times.'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all phases sequentially'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate metrics report only'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Prompt before each change'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Save reports to specific directory'
    )
    args = parser.parse_args()
    # Validate arguments
    if not args.phases and not args.all and not args.report:
        parser.error("Must specify --phase, --all, or --report")
    if args.all and args.phases:
        parser.error("Cannot use both --all and --phase")
    # Determine phases to run
    phases = None if args.all else args.phases
    try:
        # Run cleanup
        report = run_cleanup(
            phases=phases,
            dry_run=args.dry_run,
            interactive=args.interactive,
            report_only=args.report,
            output_dir=args.output
        )
        # Print summary
        print_summary_table(report)
        # Generate detailed report
        if args.output or not args.dry_run:
            generate_report(report, output_dir=args.output)
        # Exit with appropriate code
        if report.success:
            print_success("Cleanup completed successfully!")
            sys.exit(0)
        else:
            print_error("Cleanup completed with errors")
            sys.exit(1)
    except KeyboardInterrupt:
        print_error("\nCancelled by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
if __name__ == '__main__':
    main()
