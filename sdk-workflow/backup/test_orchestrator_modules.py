"""Integration test for orchestrator modules.
Tests OutputManager, OrchestratedSession, and PhaseResult working together.
"""
from datetime import datetime
from sdk_workflow.utils import OutputManager, SessionManifest
from sdk_workflow.models import OrchestratedSession, PhaseResult
from sdk_workflow.config import PhaseType, get_phase_prompt
from sdk_workflow.core.types import ExecutionMode, TokenUsage, CostBreakdown
def test_orchestrator_integration():
    """Test full workflow: session creation, phase execution, output management."""
    print("=" * 60)
    print("Testing Orchestrator Module Integration")
    print("=" * 60)
    # 1. Create orchestrated session
    print("\n1. Creating orchestrated session...")
    session = OrchestratedSession.create(
        mode=ExecutionMode.ORCHESTRATOR,
        task="Implement user authentication system",
        model="sonnet",
        system_prompt="You are a helpful coding assistant.",
    )
    print(f" [OK] Session created: {session.session_id}")
    print(f" [OK] Mode: {session.mode.value}")
    print(f" [OK] Task: {session.metadata.get('task')}")
    # 2. Create output manager and session directory
    print("\n2. Setting up output management...")
    output_mgr = OutputManager()
    session_dir = output_mgr.create_session_dir(
        session.session_id, metadata={"task": session.metadata.get("task")}
    )
    print(f" [OK] Output directory created: {session_dir}")
    # 3. Simulate planning phase
    print("\n3. Simulating planning phase...")
    planning_start = datetime.now()
    # Get phase prompt
    phase_prompt = get_phase_prompt(PhaseType.PLANNING)
    print(f" [OK] Phase prompt retrieved ({len(phase_prompt)} chars)")
    # Create planning result
    planning_result = PhaseResult(
        phase_name="planning",
        status="success",
        started_at=planning_start.isoformat(),
        completed_at=datetime.now().isoformat(),
        duration_ms=1250.5,
        output={
            "phase": "planning",
            "tasks": [
                {"id": "task_1", "description": "Design auth schema", "dependencies": []},
                {"id": "task_2", "description": "Implement login", "dependencies": ["task_1"]},
            ],
            "architecture": {"components": ["AuthService", "UserModel"], "approach": "JWT-based"},
        },
        usage=TokenUsage(input_tokens=1000, output_tokens=500),
        cost=CostBreakdown(input_cost=0.003, output_cost=0.0075),
        artifacts=["/src/auth/schema.py", "/src/auth/service.py"],
    )
    # Add to session
    session.add_phase_result(planning_result)
    print(f" [OK] Planning phase completed")
    print(f" [OK] Total tokens: {session.total_usage.total_tokens}")
    print(f" [OK] Total cost: ${session.total_cost.total_cost:.4f}")
    # Write planning output
    output_path = output_mgr.write_phase_output(
        session_id=session.session_id,
        phase="planning",
        filename="plan.json",
        content=planning_result.output,
    )
    print(f" [OK] Planning output saved: {output_path}")
    # 4. Create checkpoint
    print("\n4. Creating checkpoint...")
    checkpoint_name = session.create_checkpoint(
        name="post-planning", description="After successful planning phase"
    )
    print(f" [OK] Checkpoint created: {checkpoint_name}")
    print(f" [OK] Session status: {session.status.value}")
    # 5. Simulate implementation phase
    print("\n5. Simulating implementation phase...")
    impl_start = datetime.now()
    impl_result = PhaseResult(
        phase_name="implementation",
        status="success",
        started_at=impl_start.isoformat(),
        completed_at=datetime.now().isoformat(),
        duration_ms=3500.2,
        output={
            "phase": "implementation",
            "files_modified": [
                {"path": "/src/auth/schema.py", "action": "created", "lines_changed": 45},
                {"path": "/src/auth/service.py", "action": "created", "lines_changed": 120},
            ],
            "completion_status": "success",
        },
        usage=TokenUsage(input_tokens=2000, output_tokens=1500),
        cost=CostBreakdown(input_cost=0.006, output_cost=0.0225),
        artifacts=["/src/auth/schema.py", "/src/auth/service.py", "/tests/test_auth.py"],
    )
    session.add_phase_result(impl_result)
    print(f" [OK] Implementation phase completed")
    print(f" [OK] Total tokens: {session.total_usage.total_tokens}")
    print(f" [OK] Total cost: ${session.total_cost.total_cost:.4f}")
    output_mgr.write_phase_output(
        session_id=session.session_id, phase="implementation", filename="result.json", content=impl_result.output
    )
    # 6. Save session
    print("\n6. Saving session...")
    session_path = session.save()
    print(f" [OK] Session saved: {session_path}")
    # 7. Test session loading
    print("\n7. Testing session load/resume...")
    loaded_session = OrchestratedSession.load(session.session_id)
    print(f" [OK] Session loaded: {loaded_session.session_id}")
    print(f" [OK] Phases completed: {len(loaded_session.phase_results)}")
    print(f" [OK] Checkpoints: {len(loaded_session.named_checkpoints)}")
    # Test checkpoint resume
    success = loaded_session.resume_from_checkpoint("post-planning")
    print(f" [OK] Resumed from checkpoint: {success}")
    # 8. Test output reading
    print("\n8. Testing output retrieval...")
    planning_data = output_mgr.read_phase_output(
        session_id=session.session_id, phase="planning", filename="plan.json"
    )
    print(f" [OK] Planning data retrieved: {len(planning_data.get('tasks', []))} tasks")
    # 9. Get manifest
    print("\n9. Checking session manifest...")
    manifest = output_mgr.get_manifest(session.session_id)
    print(f" [OK] Manifest retrieved")
    print(f" [OK] Phases tracked: {', '.join(manifest.phases)}")
    print(f" [OK] Total files: {manifest.total_files}")
    print(f" [OK] Total size: {manifest.total_size_bytes} bytes")
    # 10. Summary
    print("\n" + "=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)
    print(f"Session ID: {session.session_id}")
    print(f"Phases completed: {len(session.phase_results)}")
    print(f" - {', '.join([r.phase_name for r in session.phase_results])}")
    print(f"Checkpoints created: {len(session.named_checkpoints)}")
    print(f" - {', '.join(session.named_checkpoints.keys())}")
    print(f"Total tokens: {session.total_usage.total_tokens:,}")
    print(f"Total cost: ${session.total_cost.total_cost:.4f}")
    print(f"Output files: {manifest.total_files}")
    print(f"Output size: {manifest.total_size_bytes:,} bytes")
    print("=" * 60)
    print("\n[SUCCESS] All integration tests passed!")
if __name__ == "__main__":
    test_orchestrator_integration()
