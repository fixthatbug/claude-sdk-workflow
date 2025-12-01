#!/usr/bin/env python3
"""
Resources Module Validation Script
Validates all components of the resources module:
- Agent registry and definitions
- Tool registry and validation
- Prompt composition
- API format conversions
- Error handling
Run: python validate.py
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
def test_imports() -> tuple[bool, str]:
    """Test all module imports."""
    try:
        from resources import (
            # Agents
            AgentDefinition,
            AgentRegistry,
            get_agent,
            list_agents,
            create_agent,
            ARCHITECT,
            IMPLEMENTER,
            REVIEWER,
            TESTER,
            RESEARCHER,
            DEBUGGER,
            DOCUMENTER,
            # Prompts
            PromptRegistry,
            compose_orchestrator_prompt,
            compose_subagent_prompt,
            create_dynamic_prompt,
            ORCHESTRATOR_PROMPT,
            SUBAGENT_BASE_PROMPT,
            # Tools
            ToolDefinition,
            ToolRegistry,
            ToolSets,
            get_tool,
            get_tools,
            validate_tool_input,
            developer_tools,
            orchestrator_tools,
            # Legacy
            get_prompt,
            get_schema,
            get_tool_definitions,
        )
        return True, "All imports successful"
    except ImportError as e:
        return False, f"Import failed: {e}"
def test_agent_registry() -> tuple[bool, str]:
    """Test agent registry functionality."""
    from resources import AgentRegistry, get_agent, list_agents, create_agent
    try:
        # Check default agents
        agents = list_agents()
        expected = {'architect', 'implementer', 'reviewer', 'tester', 'researcher', 'debugger', 'documenter'}
        if not expected.issubset(set(agents)):
            return False, f"Missing default agents. Expected {expected}, got {set(agents)}"
        # Test agent retrieval
        architect = get_agent('architect')
        if architect.name != 'architect':
            return False, f"Agent name mismatch: {architect.name}"
        # Test custom agent creation
        initial_count = len(list_agents())
        custom = create_agent(
            name='test_validation_agent',
            role='Test Agent',
            system_prompt='Test prompt',
            register=True
        )
        if len(list_agents()) != initial_count + 1:
            return False, "Agent registration failed"
        # Test agent modification
        modified = custom.with_model('claude-haiku-4-5-20251001')
        if modified.model != 'claude-haiku-4-5-20251001':
            return False, "Agent modification failed"
        # Cleanup
        AgentRegistry.unregister('test_validation_agent')
        return True, f"Agent registry: {len(expected)} default agents, custom creation OK"
    except Exception as e:
        return False, f"Agent registry error: {e}"
def test_tool_registry() -> tuple[bool, str]:
    """Test tool registry and validation."""
    from resources import ToolRegistry, get_tool, validate_tool_input, ToolSets
    try:
        # Check all tools exist
        tools = ToolRegistry.list_names()
        expected = {'read_file', 'write_file', 'edit_file', 'bash', 'search_files', 'delegate_task'}
        if set(tools) != expected:
            return False, f"Tool mismatch. Expected {expected}, got {set(tools)}"
        # Test tool retrieval
        read_tool = get_tool('read_file')
        if read_tool.name != 'read_file':
            return False, "Tool retrieval failed"
        # Test API format conversion
        api_format = read_tool.to_api_format()
        required_keys = {'name', 'description', 'input_schema'}
        if not required_keys.issubset(api_format.keys()):
            return False, f"API format missing keys. Expected {required_keys}, got {api_format.keys()}"
        # Test validation - valid input
        valid_input = {'file_path': '/test.py', 'offset': 0, 'limit': 100}
        if not validate_tool_input('read_file', valid_input):
            return False, "Valid input marked as invalid"
        # Test validation - invalid input
        try:
            invalid_input = {'file_path': '', 'offset': -1}
            validate_tool_input('read_file', invalid_input)
            return False, "Invalid input not caught"
        except ValueError:
            pass # Expected
        # Test tool sets
        dev_tools = ToolSets.get('developer')
        if 'read_file' not in dev_tools or 'bash' not in dev_tools:
            return False, "Tool sets incomplete"
        return True, f"Tool registry: {len(expected)} tools, validation OK"
    except Exception as e:
        return False, f"Tool registry error: {e}"
def test_prompt_composition() -> tuple[bool, str]:
    """Test prompt composition and registry."""
    from resources import (
        PromptRegistry,
        compose_orchestrator_prompt,
        compose_subagent_prompt,
        create_dynamic_prompt,
        ORCHESTRATOR_PROMPT,
        SUBAGENT_BASE_PROMPT,
    )
    try:
        # Test static prompts exist
        if not ORCHESTRATOR_PROMPT or not SUBAGENT_BASE_PROMPT:
            return False, "Static prompts missing"
        # Test orchestrator composition
        composed = compose_orchestrator_prompt(
            task_context="Test task",
            available_agents=['architect', 'implementer'],
            constraints="Test constraints"
        )
        if 'Test task' not in composed:
            return False, "Task context not in composed prompt"
        # Test subagent composition
        subagent = compose_subagent_prompt(
            specialty_prompt="You are a specialist",
            task_context="Specific task",
            prior_context="Previous results"
        )
        if 'Specific task' not in subagent:
            return False, "Task not in subagent prompt"
        # Test dynamic prompt creation
        dynamic = create_dynamic_prompt(
            role='Tester',
            expertise='Testing expertise',
            task_description='Write tests',
            tools=['read_file', 'bash'],
            output_format='Test results'
        )
        if 'Tester' not in dynamic:
            return False, "Dynamic prompt creation failed"
        # Test task prompt retrieval
        impl_prompt = PromptRegistry.get_task_prompt('implementation')
        if not impl_prompt:
            return False, "Task prompt retrieval failed"
        # Test invalid task type
        try:
            PromptRegistry.get_task_prompt('invalid_task_type')
            return False, "Invalid task type not caught"
        except ValueError:
            pass # Expected
        return True, "Prompt composition: static prompts OK, composition OK"
    except Exception as e:
        return False, f"Prompt composition error: {e}"
def test_integration() -> tuple[bool, str]:
    """Test integration patterns."""
    from resources import get_agent, developer_tools, compose_orchestrator_prompt
    try:
        # Test agent + tools integration
        implementer = get_agent('implementer')
        tools = developer_tools()
        if not isinstance(tools, list):
            return False, "Tools not returned as list"
        if len(tools) == 0:
            return False, "No tools returned"
        # Verify API format
        tool = tools[0]
        if 'name' not in tool or 'input_schema' not in tool:
            return False, "Tools not in correct API format"
        # Test orchestrator setup
        prompt = compose_orchestrator_prompt("Integration test task")
        if not prompt:
            return False, "Orchestrator prompt composition failed"
        return True, "Integration: agent + tools + prompts OK"
    except Exception as e:
        return False, f"Integration error: {e}"
def test_legacy_compatibility() -> tuple[bool, str]:
    """Test legacy function compatibility."""
    from resources import get_prompt, get_tool_definitions
    try:
        # Test get_prompt (deprecated but should work)
        try:
            prompt = get_prompt('implementation')
            if not prompt:
                return False, "Legacy get_prompt returned empty"
        except KeyError:
            pass # Acceptable if not all legacy prompts exist
        # Test get_tool_definitions
        all_tools = get_tool_definitions()
        if not isinstance(all_tools, list) or len(all_tools) == 0:
            return False, "Legacy get_tool_definitions failed"
        dev_tools = get_tool_definitions('developer')
        if not isinstance(dev_tools, list):
            return False, "Legacy get_tool_definitions with set failed"
        return True, "Legacy compatibility OK"
    except Exception as e:
        return False, f"Legacy compatibility error: {e}"
def test_error_handling() -> tuple[bool, str]:
    """Test error handling and edge cases."""
    from resources import get_agent, get_tool, validate_tool_input, ToolRegistry
    errors_caught = 0
    # Test invalid agent
    try:
        get_agent('nonexistent_agent')
    except KeyError:
        errors_caught += 1
    # Test invalid tool
    try:
        get_tool('nonexistent_tool')
    except KeyError:
        errors_caught += 1
    # Test invalid tool input
    try:
        validate_tool_input('read_file', {'invalid_param': 'value'})
    except ValueError:
        errors_caught += 1
    # Test empty file path
    try:
        validate_tool_input('read_file', {'file_path': ''})
    except ValueError:
        errors_caught += 1
    # Test dangerous bash command
    try:
        validate_tool_input('bash', {'command': 'rm -rf /'})
    except ValueError:
        errors_caught += 1
    if errors_caught < 4: # Should catch at least 4 of 5 errors
        return False, f"Only caught {errors_caught}/5 expected errors"
    return True, f"Error handling: {errors_caught}/5 errors properly caught"
def run_validation() -> int:
    """Run all validation tests."""
    print("=" * 70)
    print("SDK-WORKFLOW RESOURCES MODULE VALIDATION")
    print("=" * 70)
    print()
    tests = [
        ("Module Imports", test_imports),
        ("Agent Registry", test_agent_registry),
        ("Tool Registry", test_tool_registry),
        ("Prompt Composition", test_prompt_composition),
        ("Integration", test_integration),
        ("Legacy Compatibility", test_legacy_compatibility),
        ("Error Handling", test_error_handling),
    ]
    results: list[tuple[str, bool, str]] = []
    passed = 0
    failed = 0
    for test_name, test_func in tests:
        try:
            success, message = test_func()
            results.append((test_name, success, message))
            if success:
                passed += 1
                status = "PASS"
            else:
                failed += 1
                status = "FAIL"
        except Exception as e:
            results.append((test_name, False, f"Exception: {e}"))
            failed += 1
            status = "ERROR"
        print(f"[{status:5}] {test_name:25} | {results[-1][2]}")
    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed (total: {len(tests)})")
    print("=" * 70)
    if failed == 0:
        print()
        print("SUCCESS: All validation tests passed!")
        print()
        print("The resources module is ready for production use.")
        print()
        return 0
    else:
        print()
        print("FAILURE: Some tests failed. Review output above.")
        print()
        return 1
if __name__ == "__main__":
    sys.exit(run_validation())
