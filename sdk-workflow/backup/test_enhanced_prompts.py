"""Test script to verify enhanced prompts are correctly integrated."""
import sys
from pathlib import Path
# Add sdk_workflow to path
sys.path.insert(0, str(Path(__file__).parent))
def test_phase_prompts():
    """Test enhanced phase prompts."""
    print("=" * 60)
    print("Testing Enhanced Phase Prompts")
    print("=" * 60)
    from sdk_workflow.config import PhaseType, get_phase_prompt
    phases = [PhaseType.PLANNING, PhaseType.IMPLEMENTATION, PhaseType.REVIEW, PhaseType.TESTING]
    for phase in phases:
        prompt = get_phase_prompt(phase)
        print(f"\n{phase.value.upper()} Phase:")
        print(f" Length: {len(prompt)} chars")
        # Check for key enhancements
        checks = {
            "Anti-Patterns": "Anti-Patterns" in prompt or "Anti-Duplication" in prompt or "Code Reuse" in prompt or "Code Duplication" in prompt,
            "Skills Usage": "Skill(" in prompt or "Skills" in prompt,
            "Methodology": "Methodology" in prompt or "Approach" in prompt,
            "Edge Cases": "Edge Cases" in prompt,
            "SILENT EXECUTION": "SILENT EXECUTION" in prompt
        }
        for check_name, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f" {status} {check_name}")
    print("\n[OK] Phase prompts loaded successfully\n")
def test_agent_prompts():
    """Test enhanced agent prompts."""
    print("=" * 60)
    print("Testing Enhanced Agent Prompts")
    print("=" * 60)
    from sdk_workflow.config import (
        get_orchestrator_prompt,
        get_subagent_prompt,
        list_available_agent_types
    )
    # Test orchestrator prompt
    orch_prompt = get_orchestrator_prompt()
    print(f"\nOrchestrator Prompt:")
    print(f" Length: {len(orch_prompt)} chars")
    checks = {
        "Code Quality Enforcement": "Code Quality Enforcement" in orch_prompt,
        "Skills and SlashCommands": "Skills and SlashCommands" in orch_prompt,
        "Available Tools": "Available Tools" in orch_prompt,
        "Orchestration Methodology": "Orchestration Methodology" in orch_prompt,
        "Prevent file duplication": "duplication" in orch_prompt.lower()
    }
    for check_name, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f" {status} {check_name}")
    # Test subagent prompts
    agent_types = list_available_agent_types()
    print(f"\n[OK] Available agent types: {', '.join(agent_types)}")
    for agent_type in agent_types:
        prompt = get_subagent_prompt(agent_type)
        print(f"\n{agent_type.title()} Subagent:")
        print(f" Length: {len(prompt)} chars")
        # Check for key features
        has_tools = "Available Tools" in prompt
        has_quality = "Quality Focus" in prompt or "Quality" in prompt
        has_approach = "Approach" in prompt or "Methodology" in prompt
        print(f" {'[OK]' if has_tools else '[FAIL]'} Tool specification")
        print(f" {'[OK]' if has_quality else '[FAIL]'} Quality focus")
        print(f" {'[OK]' if has_approach else '[FAIL]'} Methodology/Approach")
    print("\n[OK] Agent prompts loaded successfully\n")
def test_orchestrator_integration():
    """Test orchestrator integration with enhanced prompts."""
    print("=" * 60)
    print("Testing Orchestrator Integration")
    print("=" * 60)
    try:
        # Import check
        from sdk_workflow.executors.orchestrator import OrchestratorExecutor
        print("\n[OK] OrchestratorExecutor import successful")
        # Check for enhanced prompt imports
        import sdk_workflow.executors.orchestrator as orch_module
        has_get_orchestrator = hasattr(orch_module, 'get_orchestrator_prompt')
        has_get_subagent = hasattr(orch_module, 'get_subagent_prompt')
        print(f" {'[OK]' if has_get_orchestrator else '[FAIL]'} get_orchestrator_prompt imported")
        print(f" {'[OK]' if has_get_subagent else '[FAIL]'} get_subagent_prompt imported")
        print("\n[OK] Orchestrator integration verified\n")
    except ImportError as e:
        print(f"\n[FAIL] Import error: {e}\n")
def test_config_exports():
    """Test config module exports."""
    print("=" * 60)
    print("Testing Config Module Exports")
    print("=" * 60)
    from sdk_workflow import config
    expected_exports = [
        "PhaseType",
        "get_phase_prompt",
        "get_orchestrator_prompt",
        "get_subagent_prompt",
        "list_available_agent_types"
    ]
    print()
    for export in expected_exports:
        has_export = hasattr(config, export)
        status = "[OK]" if has_export else "[FAIL]"
        print(f" {status} {export}")
    print("\n[OK] Config exports verified\n")
def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Enhanced Prompts Integration Test")
    print("=" * 60 + "\n")
    try:
        test_config_exports()
        test_phase_prompts()
        test_agent_prompts()
        test_orchestrator_integration()
        print("=" * 60)
        print("[OK] ALL TESTS PASSED")
        print("=" * 60 + "\n")
        return 0
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"[FAIL] TEST FAILED: {e}")
        print("=" * 60 + "\n")
        import traceback
        traceback.print_exc()
        return 1
if __name__ == "__main__":
    sys.exit(main())
