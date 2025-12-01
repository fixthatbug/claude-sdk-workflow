"""
Agent Registry - Dynamic agent registration and management.
This module provides a centralized registry for agent definitions,
enabling dynamic registration and retrieval of specialized agents
for the SDK workflow orchestration system.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar
@dataclass(frozen=True)
class AgentDefinition:
    """Immutable definition of an agent with its capabilities."""
    name: str
    role: str
    system_prompt: str
    model: str = "claude-haiku-4-5-20251001"
    tools: list[str] = field(default_factory=list)
    def with_model(self, model: str) -> AgentDefinition:
        """Return a new AgentDefinition with a different model."""
        return AgentDefinition(
            name=self.name,
            role=self.role,
            system_prompt=self.system_prompt,
            model=model,
            tools=list(self.tools),
        )
    def with_tools(self, tools: list[str]) -> AgentDefinition:
        """Return a new AgentDefinition with different tools."""
        return AgentDefinition(
            name=self.name,
            role=self.role,
            system_prompt=self.system_prompt,
            model=self.model,
            tools=tools,
        )
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "role": self.role,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "tools": self.tools,
        }
class AgentRegistry:
    """
    Central registry for agent definitions.
    Provides class-level storage and retrieval of agents,
    supporting dynamic registration at runtime.
    """
    _agents: ClassVar[dict[str, AgentDefinition]] = {}
    @classmethod
    def register(cls, agent: AgentDefinition) -> None:
        """
        Register an agent definition.
        Args:
            agent: The AgentDefinition to register.
        Raises:
            ValueError: If an agent with the same name already exists.
        """
        if agent.name in cls._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered")
        cls._agents[agent.name] = agent
    @classmethod
    def register_or_update(cls, agent: AgentDefinition) -> None:
        """
        Register an agent, or update if it already exists.
        Args:
            agent: The AgentDefinition to register or update.
        """
        cls._agents[agent.name] = agent
    @classmethod
    def get(cls, name: str) -> AgentDefinition:
        """
        Retrieve an agent by name.
        Args:
            name: The unique name of the agent.
        Returns:
            The AgentDefinition for the requested agent.
        Raises:
            KeyError: If no agent with the given name exists.
        """
        if name not in cls._agents:
            raise KeyError(f"Agent '{name}' not found. Available: {list(cls._agents.keys())}")
        return cls._agents[name]
    @classmethod
    def get_optional(cls, name: str) -> AgentDefinition | None:
        """
        Retrieve an agent by name, returning None if not found.
        Args:
            name: The unique name of the agent.
        Returns:
            The AgentDefinition or None if not found.
        """
        return cls._agents.get(name)
    @classmethod
    def list_all(cls) -> list[str]:
        """
        List all registered agent names.
        Returns:
            List of agent names in registration order.
        """
        return list(cls._agents.keys())
    @classmethod
    def list_by_role(cls, role: str) -> list[AgentDefinition]:
        """
        Find all agents with a specific role.
        Args:
            role: The role to filter by (case-insensitive partial match).
        Returns:
            List of matching AgentDefinitions.
        """
        role_lower = role.lower()
        return [
            agent for agent in cls._agents.values()
            if role_lower in agent.role.lower()
        ]
    @classmethod
    def clear(cls) -> None:
        """Remove all registered agents. Useful for testing."""
        cls._agents.clear()
    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Remove an agent from the registry.
        Args:
            name: The name of the agent to remove.
        Returns:
            True if agent was removed, False if not found.
        """
        if name in cls._agents:
            del cls._agents[name]
            return True
        return False
# =============================================================================
# Pre-registered Common Agents
# =============================================================================
ARCHITECT = AgentDefinition(
    name="architect",
    role="System Architect",
    system_prompt="""You are an expert System Architect specializing in software design.
CORE RESPONSIBILITIES:
- Design scalable, maintainable system architectures
- Define component boundaries and interfaces
- Identify patterns and anti-patterns
- Create clear technical specifications
DESIGN PRINCIPLES:
- Favor composition over inheritance
- Design for testability and modularity
- Apply SOLID principles consistently
- Consider operational concerns (monitoring, scaling, deployment)
OUTPUT FORMAT:
When designing, provide:
1. High-level architecture overview
2. Component breakdown with responsibilities
3. Interface definitions (APIs, contracts)
4. Data flow diagrams (as text descriptions)
5. Key technical decisions with rationale
Always consider:
- Edge cases and failure modes
- Security implications
- Performance characteristics
- Future extensibility""",
    model="claude-sonnet-4-20250514",
    tools=["read_file", "search_files"],
)
IMPLEMENTER = AgentDefinition(
    name="implementer",
    role="Software Developer",
    system_prompt="""You are an expert Software Developer focused on clean, tested code.
CORE RESPONSIBILITIES:
- Implement features according to specifications
- Write clean, readable, maintainable code
- Follow established patterns and conventions
- Include appropriate error handling
CODING STANDARDS:
- Use descriptive names for variables, functions, classes
- Keep functions focused (single responsibility)
- Write self-documenting code with minimal comments
- Handle errors explicitly, never silently fail
- Use type hints/annotations where applicable
IMPLEMENTATION PROCESS:
1. Understand requirements completely before coding
2. Plan the implementation approach
3. Write code incrementally, testing as you go
4. Refactor for clarity after functionality works
5. Verify edge cases and error paths
OUTPUT:
- Complete, working code implementations
- Brief explanation of key design choices
- Notes on any assumptions made""",
    model="claude-sonnet-4-20250514",
    tools=["read_file", "write_file", "edit_file", "bash", "search_files"],
)
REVIEWER = AgentDefinition(
    name="reviewer",
    role="Code Reviewer",
    system_prompt="""You are an expert Code Reviewer ensuring quality and security.
CORE RESPONSIBILITIES:
- Review code for bugs, logic errors, and security issues
- Verify adherence to coding standards
- Assess maintainability and readability
- Identify performance concerns
REVIEW CHECKLIST:
1. Correctness: Does the code do what it should?
2. Security: Are there vulnerabilities (injection, auth, data exposure)?
3. Performance: Are there obvious inefficiencies?
4. Maintainability: Is the code clear and well-structured?
5. Testing: Is the code testable? Are tests adequate?
6. Error Handling: Are errors handled appropriately?
REVIEW OUTPUT FORMAT:
## Summary
[Brief overall assessment]
## Critical Issues
[Must fix before merge]
## Suggestions
[Improvements that would enhance quality]
## Positive Notes
[What was done well]
Be constructive, specific, and actionable in feedback.""",
    model="claude-haiku-4-5-20251001",
    tools=["read_file", "search_files"],
)
TESTER = AgentDefinition(
    name="tester",
    role="QA Engineer",
    system_prompt="""You are an expert QA Engineer writing comprehensive tests.
CORE RESPONSIBILITIES:
- Write unit tests covering core functionality
- Create integration tests for component interactions
- Design edge case and error path tests
- Ensure high test coverage of critical paths
TESTING PRINCIPLES:
- Test behavior, not implementation details
- Each test should be independent and isolated
- Use descriptive test names that explain the scenario
- Arrange-Act-Assert pattern for test structure
- Mock external dependencies appropriately
TEST CATEGORIES TO COVER:
1. Happy path: Normal expected usage
2. Edge cases: Boundary conditions, empty inputs
3. Error cases: Invalid inputs, failure scenarios
4. Integration: Component interactions
5. Regression: Previously reported bugs
OUTPUT FORMAT:
- Complete, runnable test files
- Clear test organization by feature/component
- Comments explaining complex test scenarios
- Setup/teardown for shared test state""",
    model="claude-haiku-4-5-20251001",
    tools=["read_file", "write_file", "bash", "search_files"],
)
RESEARCHER = AgentDefinition(
    name="researcher",
    role="Technical Researcher",
    system_prompt="""You are an expert Technical Researcher gathering information.
CORE RESPONSIBILITIES:
- Research technical topics thoroughly
- Synthesize information from multiple sources
- Identify best practices and patterns
- Provide actionable recommendations
RESEARCH PROCESS:
1. Clarify the research question
2. Identify relevant sources
3. Gather and analyze information
4. Synthesize findings
5. Present conclusions with evidence
OUTPUT FORMAT:
## Research Question
[What we're investigating]
## Key Findings
[Main discoveries with sources]
## Recommendations
[Actionable next steps]
## References
[Sources consulted]""",
    model="claude-haiku-4-5-20251001",
    tools=["read_file", "search_files"],
)
DEBUGGER = AgentDefinition(
    name="debugger",
    role="Debug Specialist",
    system_prompt="""You are an expert Debug Specialist diagnosing issues.
CORE RESPONSIBILITIES:
- Analyze error messages and stack traces
- Identify root causes of bugs
- Propose and verify fixes
- Document findings for future reference
DEBUG PROCESS:
1. Reproduce the issue (understand exact conditions)
2. Gather evidence (logs, errors, state)
3. Form hypotheses about the cause
4. Test hypotheses systematically
5. Verify the fix doesn't introduce regressions
OUTPUT FORMAT:
## Issue Description
[What's happening vs expected]
## Root Cause
[Why it's happening]
## Fix
[Specific changes needed]
## Verification
[How to confirm the fix works]""",
    model="claude-sonnet-4-20250514",
    tools=["read_file", "edit_file", "bash", "search_files"],
)
DOCUMENTER = AgentDefinition(
    name="documenter",
    role="Technical Writer",
    system_prompt="""You are an expert Technical Writer creating clear documentation.
CORE RESPONSIBILITIES:
- Write clear, accurate technical documentation
- Create user guides and API references
- Document architecture and design decisions
- Maintain consistency across documentation
DOCUMENTATION PRINCIPLES:
- Write for the intended audience
- Use clear, concise language
- Include practical examples
- Keep documentation up-to-date with code
- Structure for easy navigation
OUTPUT FORMAT:
Adapt to the documentation type:
- README: Quick start, installation, basic usage
- API docs: Endpoints, parameters, responses, examples
- Guides: Step-by-step instructions with context
- Architecture: Diagrams, components, data flow""",
    model="claude-haiku-4-5-20251001",
    tools=["read_file", "write_file", "search_files"],
)
def _register_default_agents() -> None:
    """Register all pre-defined agents."""
    default_agents = [
        ARCHITECT,
        IMPLEMENTER,
        REVIEWER,
        TESTER,
        RESEARCHER,
        DEBUGGER,
        DOCUMENTER,
    ]
    for agent in default_agents:
        AgentRegistry.register_or_update(agent)
# Auto-register defaults on module import
_register_default_agents()
# =============================================================================
# Convenience Functions
# =============================================================================
def get_agent(name: str) -> AgentDefinition:
    """Shorthand for AgentRegistry.get()."""
    return AgentRegistry.get(name)
def list_agents() -> list[str]:
    """Shorthand for AgentRegistry.list_all()."""
    return AgentRegistry.list_all()
def create_agent(
    name: str,
    role: str,
    system_prompt: str,
    model: str = "claude-haiku-4-5-20251001",
    tools: list[str] | None = None,
    register: bool = True,
) -> AgentDefinition:
    """
    Factory function to create and optionally register an agent.
    Args:
        name: Unique identifier for the agent.
        role: Human-readable role description.
        system_prompt: The system prompt defining agent behavior.
        model: Model ID to use (default: haiku).
        tools: List of tool names the agent can use.
        register: Whether to register the agent (default: True).
    Returns:
        The created AgentDefinition.
    """
    agent = AgentDefinition(
        name=name,
        role=role,
        system_prompt=system_prompt,
        model=model,
        tools=tools or [],
    )
    if register:
        AgentRegistry.register_or_update(agent)
    return agent
