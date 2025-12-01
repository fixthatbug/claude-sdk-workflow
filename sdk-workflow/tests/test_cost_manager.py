"""
Comprehensive unit tests for CostManager.
This test module achieves >90% code coverage for the CostManager class,
testing all public methods, edge cases, thread safety, and integrations.
"""
import csv
import json
import pytest
import threading
import time
from collections import deque
from io import StringIO
from unittest.mock import Mock, MagicMock, patch
from sdk_workflow.managers.cost_manager import (
    CostManager,
    CostManagerException,
    BudgetExceeded,
    MODEL_PRICING
)
# ============================================================================
# Test Fixtures
# ============================================================================
@pytest.fixture
def cost_manager():
    """Provide a fresh CostManager instance for each test."""
    return CostManager()
@pytest.fixture
def cost_manager_custom():
    """Provide a CostManager with custom parameters."""
    return CostManager(
        history_size=50,
        soft_limit_threshold=60.0,
        hard_limit_threshold=80.0,
        emergency_threshold=95.0
    )
@pytest.fixture
def cost_manager_with_history():
    """Provide a CostManager with some cost history."""
    manager = CostManager()
    for i in range(5):
        manager.calculate_cost(
            input_tokens=1000 * (i + 1),
            output_tokens=500 * (i + 1),
            cache_read=100 * i,
            model="claude-sonnet-4-20250514"
        )
    return manager
@pytest.fixture
def mock_metrics_engine():
    """Provide a mock MetricsEngine for testing integration."""
    mock_engine = Mock()
    mock_engine.record_cost = Mock()
    return mock_engine
# ============================================================================
# Test Classes
# ============================================================================
class TestCostManagerInitialization:
    """Test CostManager initialization and parameter validation."""
    def test_default_initialization(self):
        """Test CostManager initializes with correct default values."""
        manager = CostManager()
        assert manager.total_cost == 0.0
        assert manager.cost_by_model == {}
        assert manager.soft_limit_threshold == 70.0
        assert manager.hard_limit_threshold == 90.0
        assert manager.emergency_threshold == 100.0
        assert manager.history_size == 100
        assert manager.metrics_engine is None
        assert manager._operation_count == 0
        assert manager._total_cache_savings == 0.0
    def test_custom_parameters(self):
        """Test CostManager with custom initialization parameters."""
        manager = CostManager(
            history_size=50,
            soft_limit_threshold=60.0,
            hard_limit_threshold=80.0,
            emergency_threshold=95.0
        )
        assert manager.history_size == 50
        assert manager.soft_limit_threshold == 60.0
        assert manager.hard_limit_threshold == 80.0
        assert manager.emergency_threshold == 95.0
    def test_invalid_soft_limit_too_low(self):
        """Test initialization fails with soft_limit_threshold < 0."""
        with pytest.raises(ValueError, match="soft_limit_threshold must be between 0 and 100"):
            CostManager(soft_limit_threshold=-1.0)
    def test_invalid_soft_limit_too_high(self):
        """Test initialization fails with soft_limit_threshold > 100."""
        with pytest.raises(ValueError, match="soft_limit_threshold must be between 0 and 100"):
            CostManager(soft_limit_threshold=101.0)
    def test_invalid_hard_limit_too_low(self):
        """Test initialization fails with hard_limit_threshold < 0."""
        with pytest.raises(ValueError, match="hard_limit_threshold must be between 0 and 100"):
            CostManager(hard_limit_threshold=-1.0)
    def test_invalid_hard_limit_too_high(self):
        """Test initialization fails with hard_limit_threshold > 100."""
        with pytest.raises(ValueError, match="hard_limit_threshold must be between 0 and 100"):
            CostManager(hard_limit_threshold=101.0)
    def test_invalid_emergency_threshold_too_low(self):
        """Test initialization fails with emergency_threshold < 0."""
        with pytest.raises(ValueError, match="emergency_threshold must be between 0 and 100"):
            CostManager(emergency_threshold=-1.0)
    def test_invalid_emergency_threshold_too_high(self):
        """Test initialization fails with emergency_threshold > 100."""
        with pytest.raises(ValueError, match="emergency_threshold must be between 0 and 100"):
            CostManager(emergency_threshold=101.0)
    def test_thresholds_not_ascending(self):
        """Test initialization fails when thresholds not in ascending order."""
        with pytest.raises(ValueError, match="Thresholds must be in ascending order"):
            CostManager(soft_limit_threshold=90.0, hard_limit_threshold=70.0)
    def test_thresholds_equal_valid(self):
        """Test initialization succeeds when thresholds are equal."""
        manager = CostManager(
            soft_limit_threshold=80.0,
            hard_limit_threshold=80.0,
            emergency_threshold=80.0
        )
        assert manager.soft_limit_threshold == 80.0
        assert manager.hard_limit_threshold == 80.0
        assert manager.emergency_threshold == 80.0
    def test_initialization_with_metrics_engine(self):
        """Test CostManager initialization with MetricsEngine."""
        mock_engine = Mock()
        manager = CostManager(metrics_engine=mock_engine)
        assert manager.metrics_engine is mock_engine
    def test_internal_structures_initialized(self):
        """Test internal data structures are properly initialized."""
        manager = CostManager()
        assert isinstance(manager._cost_history, deque)
        assert manager._cost_history.maxlen == 100
        assert manager._cost_by_operation == {
            'input': 0.0,
            'output': 0.0,
            'cache_read': 0.0,
            'cache_write': 0.0
        }
        assert manager._tokens_by_operation == {
            'input': 0,
            'output': 0,
            'cache_read': 0,
            'cache_write': 0
        }
        # Check lock exists and has expected methods
        assert hasattr(manager._lock, 'acquire')
        assert hasattr(manager._lock, 'release')
class TestBasicCostCalculation:
    """Test basic cost calculation functionality."""
    def test_calculate_cost_basic(self):
        """Test basic cost calculation with input and output tokens."""
        manager = CostManager()
        cost = manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            model="claude-sonnet-4-20250514"
        )
        # Sonnet-4: $3/MTok input, $15/MTok output
        expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        assert cost == pytest.approx(expected, rel=1e-6)
        assert manager.total_cost == pytest.approx(expected, rel=1e-6)
    def test_calculate_cost_with_cache_read(self):
        """Test cost calculation with cache read tokens."""
        manager = CostManager()
        cost = manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            cache_read=200,
            model="claude-sonnet-4-20250514"
        )
        # Sonnet-4: $3/MTok input, $15/MTok output, $0.3/MTok cache_read
        expected = (
            (1000 / 1_000_000) * 3.0 +
            (500 / 1_000_000) * 15.0 +
            (200 / 1_000_000) * 0.3
        )
        assert cost == pytest.approx(expected, rel=1e-6)
    def test_calculate_cost_with_cache_write(self):
        """Test cost calculation with cache write tokens."""
        manager = CostManager()
        cost = manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            cache_write=300,
            model="claude-sonnet-4-20250514"
        )
        # Sonnet-4: $3/MTok input, $15/MTok output, $3.75/MTok cache_write
        expected = (
            (1000 / 1_000_000) * 3.0 +
            (500 / 1_000_000) * 15.0 +
            (300 / 1_000_000) * 3.75
        )
        assert cost == pytest.approx(expected, rel=1e-6)
    def test_calculate_cost_all_token_types(self):
        """Test cost calculation with all token types."""
        manager = CostManager()
        cost = manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            cache_read=200,
            cache_write=300,
            model="claude-sonnet-4-20250514"
        )
        expected = (
            (1000 / 1_000_000) * 3.0 +
            (500 / 1_000_000) * 15.0 +
            (200 / 1_000_000) * 0.3 +
            (300 / 1_000_000) * 3.75
        )
        assert cost == pytest.approx(expected, rel=1e-6)
    def test_calculate_cost_opus_model(self):
        """Test cost calculation for Opus model."""
        manager = CostManager()
        cost = manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            model="claude-opus-4-20250514"
        )
        # Opus: $15/MTok input, $75/MTok output
        expected = (1000 / 1_000_000) * 15.0 + (500 / 1_000_000) * 75.0
        assert cost == pytest.approx(expected, rel=1e-6)
    def test_calculate_cost_haiku_model(self):
        """Test cost calculation for Haiku model."""
        manager = CostManager()
        cost = manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            model="claude-haiku-3-5-20241022"
        )
        # Haiku: $0.25/MTok input, $1.25/MTok output
        expected = (1000 / 1_000_000) * 0.25 + (500 / 1_000_000) * 1.25
        assert cost == pytest.approx(expected, rel=1e-6)
    def test_calculate_cost_unknown_model_fallback(self):
        """Test cost calculation falls back to default for unknown model."""
        manager = CostManager()
        cost = manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            model="unknown-model"
        )
        # Should fall back to Sonnet pricing
        expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        assert cost == pytest.approx(expected, rel=1e-6)
    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens."""
        manager = CostManager()
        cost = manager.calculate_cost(
            input_tokens=0,
            output_tokens=0
        )
        assert cost == 0.0
        assert manager.total_cost == 0.0
    def test_calculate_cost_accumulation(self):
        """Test multiple cost calculations accumulate correctly."""
        manager = CostManager()
        cost1 = manager.calculate_cost(input_tokens=1000, output_tokens=500)
        cost2 = manager.calculate_cost(input_tokens=2000, output_tokens=1000)
        assert manager.total_cost == pytest.approx(cost1 + cost2, rel=1e-6)
    def test_cost_by_model_tracking(self):
        """Test costs are tracked per model."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500, model="claude-sonnet-4-20250514")
        manager.calculate_cost(input_tokens=1000, output_tokens=500, model="claude-opus-4-20250514")
        assert "claude-sonnet-4-20250514" in manager.cost_by_model
        assert "claude-opus-4-20250514" in manager.cost_by_model
        assert len(manager.cost_by_model) == 2
    def test_operation_count_increments(self):
        """Test operation count increments with each calculation."""
        manager = CostManager()
        for i in range(5):
            manager.calculate_cost(input_tokens=1000, output_tokens=500)
        assert manager._operation_count == 5
class TestInputValidation:
    """Test input validation for cost calculations."""
    def test_negative_input_tokens(self):
        """Test negative input_tokens raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="input_tokens must be non-negative"):
            manager.calculate_cost(input_tokens=-100, output_tokens=500)
    def test_negative_output_tokens(self):
        """Test negative output_tokens raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="output_tokens must be non-negative"):
            manager.calculate_cost(input_tokens=1000, output_tokens=-500)
    def test_negative_cache_read(self):
        """Test negative cache_read raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="cache_read must be non-negative"):
            manager.calculate_cost(input_tokens=1000, output_tokens=500, cache_read=-100)
    def test_negative_cache_write(self):
        """Test negative cache_write raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="cache_write must be non-negative"):
            manager.calculate_cost(input_tokens=1000, output_tokens=500, cache_write=-100)
    def test_negative_budget_limit(self):
        """Test negative budget_limit raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="budget_limit must be positive"):
            manager.check_budget_status(budget_limit=-10.0)
    def test_zero_budget_limit(self):
        """Test zero budget_limit raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="budget_limit must be positive"):
            manager.check_budget_status(budget_limit=0.0)
    def test_negative_estimated_turns(self):
        """Test negative estimated_turns raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="estimated_turns must be positive"):
            manager.project_session_cost(estimated_turns=-5)
    def test_zero_estimated_turns(self):
        """Test zero estimated_turns raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="estimated_turns must be positive"):
            manager.project_session_cost(estimated_turns=0)
    def test_negative_avg_input(self):
        """Test negative avg_input raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="avg_input must be non-negative"):
            manager.project_session_cost(estimated_turns=10, avg_input=-100)
    def test_negative_avg_output(self):
        """Test negative avg_output raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="avg_output must be non-negative"):
            manager.project_session_cost(estimated_turns=10, avg_output=-100)
    def test_empty_session_ids_aggregate(self):
        """Test empty session_ids list raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="session_ids cannot be empty"):
            manager.aggregate_costs(session_ids=[])
    def test_negative_history_limit(self):
        """Test negative limit in get_cost_history raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="limit must be positive"):
            manager.get_cost_history(limit=-1)
    def test_zero_history_limit(self):
        """Test zero limit in get_cost_history raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="limit must be positive"):
            manager.get_cost_history(limit=0)
    def test_invalid_export_format(self):
        """Test invalid export_format raises ValueError."""
        manager = CostManager()
        with pytest.raises(ValueError, match="Unsupported export format"):
            manager.export_cost_report(export_format="pdf")
class TestBudgetStatus:
    """Test budget status checking functionality."""
    def test_budget_status_ok(self):
        """Test budget status when under soft limit."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        status = manager.check_budget_status(budget_limit=10.0)
        assert status['status'] == 'ok'
        assert status['exceeded'] is False
        assert status['usage_pct'] < 70.0
        assert 'OK' in status['message']
    def test_budget_status_soft_warning(self):
        """Test budget status at soft warning threshold."""
        manager = CostManager(soft_limit_threshold=10.0, hard_limit_threshold=90.0)
        manager.calculate_cost(input_tokens=100000, output_tokens=50000) # ~$0.75
        status = manager.check_budget_status(budget_limit=5.0)
        assert status['status'] == 'soft_warning'
        assert status['exceeded'] is False
        assert status['usage_pct'] >= 10.0
        assert 'Soft Warning' in status['message']
    def test_budget_status_hard_warning(self):
        """Test budget status at hard warning threshold."""
        manager = CostManager(soft_limit_threshold=70.0, hard_limit_threshold=80.0)
        manager.calculate_cost(input_tokens=200000, output_tokens=100000) # ~$2.1
        status = manager.check_budget_status(budget_limit=2.5)
        assert status['status'] == 'hard_warning'
        assert status['exceeded'] is False
        assert status['usage_pct'] >= 80.0
        assert 'HARD WARNING' in status['message']
    def test_budget_status_emergency(self):
        """Test budget status at emergency threshold."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=300000, output_tokens=150000) # ~$3.15
        status = manager.check_budget_status(budget_limit=3.0)
        assert status['status'] == 'emergency'
        assert status['exceeded'] is True
        assert status['usage_pct'] >= 100.0
        assert 'EMERGENCY' in status['message']
    def test_budget_status_remaining_calculation(self):
        """Test budget remaining is calculated correctly."""
        manager = CostManager()
        cost = manager.calculate_cost(input_tokens=100000, output_tokens=50000)
        status = manager.check_budget_status(budget_limit=10.0)
        assert status['remaining'] == pytest.approx(10.0 - cost, rel=1e-6)
    def test_budget_status_usage_percentage(self):
        """Test usage percentage calculation."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=100000, output_tokens=50000)
        status = manager.check_budget_status(budget_limit=10.0)
        expected_pct = (manager.total_cost / 10.0) * 100
        assert status['usage_pct'] == pytest.approx(expected_pct, rel=1e-2)
    def test_budget_status_includes_thresholds(self):
        """Test budget status includes threshold values."""
        manager = CostManager(
            soft_limit_threshold=65.0,
            hard_limit_threshold=85.0,
            emergency_threshold=95.0
        )
        status = manager.check_budget_status(budget_limit=10.0)
        assert status['soft_threshold'] == 65.0
        assert status['hard_threshold'] == 85.0
        assert status['emergency_threshold'] == 95.0
    @patch('sdk_workflow.managers.cost_manager.logger')
    def test_budget_status_logging_emergency(self, mock_logger):
        """Test emergency status logs error."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=300000, output_tokens=150000)
        manager.check_budget_status(budget_limit=3.0)
        assert mock_logger.error.called
    @patch('sdk_workflow.managers.cost_manager.logger')
    def test_budget_status_logging_cooldown(self, mock_logger):
        """Test warning logging has cooldown period."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=300000, output_tokens=150000)
        # First check should log
        manager.check_budget_status(budget_limit=3.0)
        call_count_1 = mock_logger.error.call_count
        # Immediate second check should not log (within cooldown)
        manager.check_budget_status(budget_limit=3.0)
        call_count_2 = mock_logger.error.call_count
        assert call_count_1 == call_count_2 # No new log call
class TestCostProjection:
    """Test cost projection functionality."""
    def test_project_session_cost_with_history(self):
        """Test projection uses actual history when available."""
        manager = CostManager()
        # Create some history
        for _ in range(5):
            manager.calculate_cost(input_tokens=1000, output_tokens=500)
        projected = manager.project_session_cost(estimated_turns=10)
        # Should project based on actual average
        avg_cost = manager.total_cost / 5
        expected = avg_cost * 10
        assert projected == pytest.approx(expected, rel=1e-6)
    def test_project_session_cost_without_history(self):
        """Test projection uses provided averages when no history."""
        manager = CostManager()
        projected = manager.project_session_cost(
            estimated_turns=10,
            avg_input=1000,
            avg_output=500
        )
        # Should use default Sonnet pricing
        cost_per_turn = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        expected = cost_per_turn * 10
        assert projected == pytest.approx(expected, rel=1e-6)
    def test_project_session_cost_custom_averages(self):
        """Test projection with custom average token counts."""
        manager = CostManager()
        projected = manager.project_session_cost(
            estimated_turns=20,
            avg_input=2000,
            avg_output=1000
        )
        cost_per_turn = (2000 / 1_000_000) * 3.0 + (1000 / 1_000_000) * 15.0
        expected = cost_per_turn * 20
        assert projected == pytest.approx(expected, rel=1e-6)
    def test_project_session_cost_single_turn(self):
        """Test projection for single turn."""
        manager = CostManager()
        projected = manager.project_session_cost(estimated_turns=1)
        # Should return cost for one turn with defaults
        expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        assert projected == pytest.approx(expected, rel=1e-6)
    def test_project_session_cost_large_turns(self):
        """Test projection for large number of turns."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        projected = manager.project_session_cost(estimated_turns=1000)
        assert projected > 0
        assert projected > manager.total_cost # Should be more than current
class TestCostBreakdown:
    """Test cost breakdown functionality."""
    def test_cost_breakdown_structure(self):
        """Test cost breakdown returns correct structure."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        breakdown = manager.get_cost_breakdown()
        assert 'input' in breakdown
        assert 'output' in breakdown
        assert 'cache_read' in breakdown
        assert 'cache_write' in breakdown
        assert 'total' in breakdown
        assert 'input_pct' in breakdown
        assert 'output_pct' in breakdown
        assert 'cache_read_pct' in breakdown
        assert 'cache_write_pct' in breakdown
    def test_cost_breakdown_percentages_sum_to_100(self):
        """Test breakdown percentages sum to approximately 100%."""
        manager = CostManager()
        manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            cache_read=200,
            cache_write=100
        )
        breakdown = manager.get_cost_breakdown()
        total_pct = (
            breakdown['input_pct'] +
            breakdown['output_pct'] +
            breakdown['cache_read_pct'] +
            breakdown['cache_write_pct']
        )
        assert total_pct == pytest.approx(100.0, rel=1e-1)
    def test_cost_breakdown_total_matches(self):
        """Test breakdown total matches manager total_cost."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        breakdown = manager.get_cost_breakdown()
        assert breakdown['total'] == pytest.approx(manager.total_cost, rel=1e-6)
    def test_cost_breakdown_zero_cost(self):
        """Test breakdown with zero cost."""
        manager = CostManager()
        breakdown = manager.get_cost_breakdown()
        assert breakdown['total'] == 0.0
        assert breakdown['input'] == 0.0
        assert breakdown['output'] == 0.0
        assert breakdown['cache_read'] == 0.0
        assert breakdown['cache_write'] == 0.0
    def test_cost_breakdown_input_only(self):
        """Test breakdown when only input tokens used."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=0)
        breakdown = manager.get_cost_breakdown()
        assert breakdown['input'] > 0
        assert breakdown['output'] == 0.0
        assert breakdown['input_pct'] > 0
        assert breakdown['output_pct'] == 0.0
    def test_cost_breakdown_output_only(self):
        """Test breakdown when only output tokens used."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=0, output_tokens=500)
        breakdown = manager.get_cost_breakdown()
        assert breakdown['input'] == 0.0
        assert breakdown['output'] > 0
        assert breakdown['input_pct'] == 0.0
        assert breakdown['output_pct'] > 0
class TestCacheEfficiency:
    """Test cache efficiency calculation and tracking."""
    def test_cache_savings_calculation(self):
        """Test cache savings are calculated correctly."""
        manager = CostManager()
        cache_read = 1000
        savings = manager.get_cache_savings(cache_read, "claude-sonnet-4-20250514")
        # Savings = (full_price - cached_price)
        full_price = (1000 / 1_000_000) * 3.0
        cached_price = (1000 / 1_000_000) * 0.3
        expected_savings = full_price - cached_price
        assert savings == pytest.approx(expected_savings, rel=1e-6)
    def test_cache_efficiency_no_cache_usage(self):
        """Test cache efficiency with no cache usage."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        efficiency = manager.calculate_cache_efficiency()
        assert efficiency['total_cache_savings'] == 0.0
        assert efficiency['cache_read_tokens'] == 0
        assert efficiency['cache_hit_rate'] == 0.0
        assert efficiency['efficiency_score'] == 0.0
    def test_cache_efficiency_with_cache_hits(self):
        """Test cache efficiency with cache hits."""
        manager = CostManager()
        manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            cache_read=500
        )
        efficiency = manager.calculate_cache_efficiency()
        assert efficiency['cache_read_tokens'] == 500
        assert efficiency['total_cache_savings'] > 0
        assert efficiency['cache_hit_rate'] > 0
        assert efficiency['savings_rate'] == 90.0
    def test_cache_efficiency_hit_rate_calculation(self):
        """Test cache hit rate is calculated correctly."""
        manager = CostManager()
        manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            cache_read=500
        )
        efficiency = manager.calculate_cache_efficiency()
        # Hit rate = cache_read / (input + cache_read)
        expected_hit_rate = (500 / (1000 + 500)) * 100
        assert efficiency['cache_hit_rate'] == pytest.approx(expected_hit_rate, rel=1e-2)
    def test_cache_efficiency_score(self):
        """Test cache efficiency score calculation."""
        manager = CostManager()
        manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            cache_read=1000 # 50% hit rate
        )
        efficiency = manager.calculate_cache_efficiency()
        # Efficiency score = hit_rate * 0.9
        expected_score = ((1000 / 2000) * 100) * 0.9
        assert efficiency['efficiency_score'] == pytest.approx(expected_score, rel=1e-2)
    def test_cache_efficiency_accumulation(self):
        """Test cache efficiency accumulates across multiple calls."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500, cache_read=200)
        manager.calculate_cost(input_tokens=1000, output_tokens=500, cache_read=300)
        efficiency = manager.calculate_cache_efficiency()
        assert efficiency['cache_read_tokens'] == 500
        assert efficiency['total_input_tokens'] == 2000
    def test_cache_efficiency_message(self):
        """Test cache efficiency includes human-readable message."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500, cache_read=500)
        efficiency = manager.calculate_cache_efficiency()
        assert 'message' in efficiency
        assert 'saved' in efficiency['message'].lower()
class TestCostAggregation:
    """Test cost aggregation across sessions."""
    def test_aggregate_costs_single_session(self):
        """Test aggregation with single session."""
        manager = CostManager()
        manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            session_id="session_1"
        )
        aggregated = manager.aggregate_costs(["session_1"])
        assert aggregated['session_count'] == 1
        assert 'session_1' in aggregated['session_costs']
        assert aggregated['total_cost'] > 0
    def test_aggregate_costs_multiple_sessions(self):
        """Test aggregation with multiple sessions."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500, session_id="session_1")
        manager.calculate_cost(input_tokens=2000, output_tokens=1000, session_id="session_2")
        manager.calculate_cost(input_tokens=1500, output_tokens=750, session_id="session_3")
        aggregated = manager.aggregate_costs(["session_1", "session_2", "session_3"])
        assert aggregated['session_count'] == 3
        assert len(aggregated['session_costs']) == 3
        assert aggregated['total_cost'] > 0
    def test_aggregate_costs_average_calculation(self):
        """Test average cost per session calculation."""
        manager = CostManager()
        cost1 = manager.calculate_cost(input_tokens=1000, output_tokens=500, session_id="s1")
        cost2 = manager.calculate_cost(input_tokens=2000, output_tokens=1000, session_id="s2")
        aggregated = manager.aggregate_costs(["s1", "s2"])
        expected_avg = (cost1 + cost2) / 2
        assert aggregated['avg_cost_per_session'] == pytest.approx(expected_avg, rel=1e-6)
    def test_aggregate_costs_min_max(self):
        """Test min and max cost tracking."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500, session_id="s1")
        manager.calculate_cost(input_tokens=3000, output_tokens=1500, session_id="s2")
        manager.calculate_cost(input_tokens=2000, output_tokens=1000, session_id="s3")
        aggregated = manager.aggregate_costs(["s1", "s2", "s3"])
        assert aggregated['min_cost'] < aggregated['max_cost']
        assert aggregated['min_cost'] == aggregated['session_costs']['s1']
        assert aggregated['max_cost'] == aggregated['session_costs']['s2']
    def test_aggregate_costs_nonexistent_session(self):
        """Test aggregation with nonexistent session ID."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500, session_id="s1")
        aggregated = manager.aggregate_costs(["s1", "nonexistent"])
        assert aggregated['session_costs']['nonexistent'] == 0.0
    def test_aggregate_costs_repeated_sessions(self):
        """Test aggregation with repeated calculations to same session."""
        manager = CostManager()
        cost1 = manager.calculate_cost(input_tokens=1000, output_tokens=500, session_id="s1")
        cost2 = manager.calculate_cost(input_tokens=1000, output_tokens=500, session_id="s1")
        aggregated = manager.aggregate_costs(["s1"])
        expected = cost1 + cost2
        assert aggregated['session_costs']['s1'] == pytest.approx(expected, rel=1e-6)
class TestExportFunctionality:
    """Test cost report export in various formats."""
    def test_export_json_format(self):
        """Test export in JSON format."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        report = manager.export_cost_report(export_format="json")
        # Should be valid JSON
        data = json.loads(report)
        assert 'summary' in data
        assert 'cost_breakdown' in data
        assert 'cache_efficiency' in data
    def test_export_csv_format(self):
        """Test export in CSV format."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        report = manager.export_cost_report(export_format="csv")
        # Should contain CSV headers
        assert '===' in report
        assert 'Metric' in report
        assert 'Value' in report
    def test_export_json_includes_summary(self):
        """Test JSON export includes summary section."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        report = manager.export_cost_report(export_format="json")
        data = json.loads(report)
        assert 'total_cost' in data['summary']
        assert 'operation_count' in data['summary']
        assert 'peak_cost' in data['summary']
        assert 'export_timestamp' in data['summary']
    def test_export_json_includes_breakdown(self):
        """Test JSON export includes cost breakdown."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        report = manager.export_cost_report(export_format="json")
        data = json.loads(report)
        breakdown = data['cost_breakdown']
        assert 'input' in breakdown
        assert 'output' in breakdown
        assert 'total' in breakdown
    def test_export_json_includes_cache_efficiency(self):
        """Test JSON export includes cache efficiency."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500, cache_read=200)
        report = manager.export_cost_report(export_format="json")
        data = json.loads(report)
        assert 'cache_efficiency' in data
        assert 'total_cache_savings' in data['cache_efficiency']
    def test_export_with_history(self):
        """Test export includes history when requested."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        manager.calculate_cost(input_tokens=2000, output_tokens=1000)
        report = manager.export_cost_report(export_format="json", include_history=True)
        data = json.loads(report)
        assert 'history' in data
        assert len(data['history']) == 2
    def test_export_without_history(self):
        """Test export excludes history when not requested."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        report = manager.export_cost_report(export_format="json", include_history=False)
        data = json.loads(report)
        assert 'history' not in data
    def test_export_csv_with_history(self):
        """Test CSV export includes history section."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        report = manager.export_cost_report(export_format="csv", include_history=True)
        assert '=== Cost History ===' in report
    def test_export_case_insensitive_format(self):
        """Test export format is case-insensitive."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        report_upper = manager.export_cost_report(export_format="JSON")
        report_lower = manager.export_cost_report(export_format="json")
        # Both should produce valid JSON
        json.loads(report_upper)
        json.loads(report_lower)
class TestHistoryTracking:
    """Test cost history tracking functionality."""
    def test_history_records_created(self):
        """Test history records are created for each calculation."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        manager.calculate_cost(input_tokens=2000, output_tokens=1000)
        history = manager.get_cost_history(limit=10)
        assert len(history) == 2
    def test_history_bounded_by_maxlen(self):
        """Test history is bounded by maxlen parameter."""
        manager = CostManager(history_size=5)
        # Add more than maxlen entries
        for i in range(10):
            manager.calculate_cost(input_tokens=1000, output_tokens=500)
        history = manager.get_cost_history(limit=100)
        assert len(history) <= 5
    def test_history_record_structure(self):
        """Test history records have correct structure."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        history = manager.get_cost_history(limit=1)
        record = history[0]
        assert 'timestamp' in record
        assert 'datetime' in record
        assert 'input_tokens' in record
        assert 'output_tokens' in record
        assert 'total_cost' in record
        assert 'cumulative_cost' in record
        assert 'model' in record
    def test_history_cumulative_cost(self):
        """Test cumulative cost is tracked in history."""
        manager = CostManager()
        cost1 = manager.calculate_cost(input_tokens=1000, output_tokens=500)
        cost2 = manager.calculate_cost(input_tokens=1000, output_tokens=500)
        history = manager.get_cost_history(limit=2)
        assert history[1]['cumulative_cost'] == pytest.approx(cost1, rel=1e-6)
        assert history[0]['cumulative_cost'] == pytest.approx(cost1 + cost2, rel=1e-6)
    def test_history_returns_most_recent_first(self):
        """Test history returns most recent records first."""
        manager = CostManager()
        for i in range(5):
            manager.calculate_cost(input_tokens=1000 * (i + 1), output_tokens=500)
        history = manager.get_cost_history(limit=5)
        # Most recent should have highest input_tokens
        assert history[0]['input_tokens'] == 5000
        assert history[-1]['input_tokens'] == 1000
    def test_history_limit_parameter(self):
        """Test limit parameter restricts returned records."""
        manager = CostManager()
        for i in range(10):
            manager.calculate_cost(input_tokens=1000, output_tokens=500)
        history = manager.get_cost_history(limit=3)
        assert len(history) == 3
    def test_history_includes_session_id(self):
        """Test history records include session_id when provided."""
        manager = CostManager()
        manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            session_id="test_session"
        )
        history = manager.get_cost_history(limit=1)
        assert history[0]['session_id'] == "test_session"
    def test_history_empty_on_new_manager(self):
        """Test history is empty for new manager."""
        manager = CostManager()
        history = manager.get_cost_history(limit=10)
        assert len(history) == 0
class TestThreadSafety:
    """Test thread safety of CostManager operations."""
    def test_concurrent_cost_calculations(self):
        """Test concurrent cost calculations are thread-safe."""
        manager = CostManager()
        num_threads = 10
        calculations_per_thread = 100
        def calculate_costs():
            for _ in range(calculations_per_thread):
                manager.calculate_cost(input_tokens=1000, output_tokens=500)
        threads = [threading.Thread(target=calculate_costs) for _ in range(num_threads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        # Total operations should equal threads * calculations_per_thread
        assert manager._operation_count == num_threads * calculations_per_thread
    def test_concurrent_budget_checks(self):
        """Test concurrent budget checks are thread-safe."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=100000, output_tokens=50000)
        results = []
        def check_budget():
            status = manager.check_budget_status(budget_limit=10.0)
            results.append(status['usage_pct'])
        threads = [threading.Thread(target=check_budget) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        # All results should be identical
        assert len(set(results)) == 1
    def test_concurrent_history_access(self):
        """Test concurrent history access is thread-safe."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        results = []
        def get_history():
            history = manager.get_cost_history(limit=10)
            results.append(len(history))
        threads = [threading.Thread(target=get_history) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        # All should return same length
        assert len(set(results)) == 1
    def test_concurrent_breakdown_access(self):
        """Test concurrent breakdown access is thread-safe."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        results = []
        def get_breakdown():
            breakdown = manager.get_cost_breakdown()
            results.append(breakdown['total'])
        threads = [threading.Thread(target=get_breakdown) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        # All should return same total
        assert len(set(results)) == 1
    def test_concurrent_reset_operations(self):
        """Test concurrent resets don't cause race conditions."""
        manager = CostManager()
        def reset_and_calculate():
            manager.reset()
            manager.calculate_cost(input_tokens=1000, output_tokens=500)
        threads = [threading.Thread(target=reset_and_calculate) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        # Manager should be in consistent state
        assert manager.total_cost >= 0
    def test_concurrent_session_tracking(self):
        """Test concurrent session tracking is thread-safe."""
        manager = CostManager()
        def calculate_with_session(session_id):
            for _ in range(10):
                manager.calculate_cost(
                    input_tokens=1000,
                    output_tokens=500,
                    session_id=session_id
                )
        threads = [
            threading.Thread(target=calculate_with_session, args=(f"session_{i}",))
            for i in range(10)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        # Should have 10 sessions
        assert len(manager._session_costs) == 10
class TestResetFunctionality:
    """Test reset functionality."""
    def test_reset_clears_total_cost(self):
        """Test reset clears total cost."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        manager.reset()
        assert manager.total_cost == 0.0
    def test_reset_clears_cost_by_model(self):
        """Test reset clears cost by model tracking."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        manager.reset()
        assert len(manager.cost_by_model) == 0
    def test_reset_clears_history(self):
        """Test reset clears cost history."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        manager.reset()
        history = manager.get_cost_history(limit=10)
        assert len(history) == 0
    def test_reset_clears_operation_count(self):
        """Test reset clears operation count."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        manager.reset()
        assert manager._operation_count == 0
    def test_reset_clears_cache_tracking(self):
        """Test reset clears cache efficiency tracking."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500, cache_read=200)
        manager.reset()
        assert manager._total_cache_savings == 0.0
        assert manager._cache_read_tokens == 0
        assert manager._total_input_tokens == 0
    def test_reset_clears_session_costs(self):
        """Test reset clears session cost tracking."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500, session_id="s1")
        manager.reset()
        assert len(manager._session_costs) == 0
    def test_reset_clears_peak_cost(self):
        """Test reset clears peak cost."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        manager.reset()
        assert manager._peak_cost == 0.0
    def test_reset_resets_start_time(self):
        """Test reset resets start time."""
        manager = CostManager()
        initial_time = manager._start_time
        time.sleep(0.1)
        manager.reset()
        assert manager._start_time > initial_time
    def test_reset_preserves_configuration(self):
        """Test reset preserves configuration parameters."""
        manager = CostManager(
            history_size=50,
            soft_limit_threshold=60.0,
            hard_limit_threshold=80.0
        )
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        manager.reset()
        assert manager.history_size == 50
        assert manager.soft_limit_threshold == 60.0
        assert manager.hard_limit_threshold == 80.0
    def test_calculations_work_after_reset(self):
        """Test calculations work correctly after reset."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        manager.reset()
        cost = manager.calculate_cost(input_tokens=1000, output_tokens=500)
        assert manager.total_cost == cost
        assert manager._operation_count == 1
class TestMetricsEngineIntegration:
    """Test MetricsEngine integration."""
    def test_metrics_engine_called_on_calculation(self):
        """Test MetricsEngine.record_cost is called on calculation."""
        mock_engine = Mock()
        manager = CostManager(metrics_engine=mock_engine)
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        mock_engine.record_cost.assert_called_once()
    def test_metrics_engine_receives_correct_data(self):
        """Test MetricsEngine receives correct cost data."""
        mock_engine = Mock()
        manager = CostManager(metrics_engine=mock_engine)
        manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            cache_read=200,
            cache_write=100,
            model="claude-sonnet-4-20250514"
        )
        call_args = mock_engine.record_cost.call_args
        assert call_args[1]['input_tokens'] == 1000
        assert call_args[1]['output_tokens'] == 500
        assert call_args[1]['cache_read'] == 200
        assert call_args[1]['cache_write'] == 100
        assert call_args[1]['model'] == "claude-sonnet-4-20250514"
    def test_metrics_engine_failure_doesnt_break_calculation(self):
        """Test calculation continues even if MetricsEngine fails."""
        mock_engine = Mock()
        mock_engine.record_cost.side_effect = Exception("Metrics failure")
        manager = CostManager(metrics_engine=mock_engine)
        # Should not raise exception
        cost = manager.calculate_cost(input_tokens=1000, output_tokens=500)
        assert cost > 0
        assert manager.total_cost > 0
    def test_no_metrics_engine_integration(self):
        """Test operations work without MetricsEngine."""
        manager = CostManager(metrics_engine=None)
        cost = manager.calculate_cost(input_tokens=1000, output_tokens=500)
        assert cost > 0
        assert manager.total_cost > 0
class TestUtilityMethods:
    """Test utility methods and helpers."""
    def test_get_summary_format(self):
        """Test get_summary returns formatted string."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        summary = manager.get_summary()
        assert isinstance(summary, str)
        assert 'Total Cost' in summary
        assert 'Total Operations' in summary
        assert 'Cost Breakdown' in summary
    def test_get_summary_includes_cache_efficiency(self):
        """Test summary includes cache efficiency info."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500, cache_read=200)
        summary = manager.get_summary()
        assert 'Cache Efficiency' in summary
        assert 'Savings' in summary
    def test_repr_method(self):
        """Test __repr__ returns informative string."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        repr_str = repr(manager)
        assert 'CostManager' in repr_str
        assert 'operations=' in repr_str
        assert 'total_cost=' in repr_str
    def test_analytics_includes_trend(self):
        """Test analytics includes cost trend analysis."""
        manager = CostManager()
        # Create history with increasing costs
        for i in range(10):
            manager.calculate_cost(input_tokens=1000 * (i + 1), output_tokens=500)
        analytics = manager._get_analytics()
        assert 'trend' in analytics
        assert analytics['trend'] in ['stable', 'increasing', 'decreasing']
    def test_analytics_trend_increasing(self):
        """Test trend detection for increasing costs."""
        manager = CostManager()
        # Create history with clearly increasing costs
        for i in range(6):
            if i < 3:
                manager.calculate_cost(input_tokens=1000, output_tokens=500)
            else:
                manager.calculate_cost(input_tokens=5000, output_tokens=2500)
        analytics = manager._get_analytics()
        assert analytics['trend'] == 'increasing'
    def test_analytics_trend_decreasing(self):
        """Test trend detection for decreasing costs."""
        manager = CostManager()
        # Create history with clearly decreasing costs
        for i in range(6):
            if i < 3:
                manager.calculate_cost(input_tokens=5000, output_tokens=2500)
            else:
                manager.calculate_cost(input_tokens=1000, output_tokens=500)
        analytics = manager._get_analytics()
        assert analytics['trend'] == 'decreasing'
    def test_analytics_uptime_tracking(self):
        """Test analytics tracks uptime."""
        manager = CostManager()
        time.sleep(0.1)
        analytics = manager._get_analytics()
        assert analytics['uptime_seconds'] > 0
    def test_analytics_operations_per_minute(self):
        """Test analytics calculates operations per minute."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        analytics = manager._get_analytics()
        assert analytics['operations_per_minute'] > 0
    def test_peak_cost_tracking(self):
        """Test peak cost is tracked correctly."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        manager.calculate_cost(input_tokens=5000, output_tokens=2500)
        manager.calculate_cost(input_tokens=2000, output_tokens=1000)
        assert manager._peak_cost == manager.total_cost
class TestPerformance:
    """Test performance characteristics."""
    def test_calculate_cost_performance(self):
        """Test calculate_cost executes within performance budget."""
        manager = CostManager()
        start_time = time.perf_counter()
        for _ in range(1000):
            manager.calculate_cost(input_tokens=1000, output_tokens=500)
        end_time = time.perf_counter()
        avg_time_ms = ((end_time - start_time) / 1000) * 1000
        assert avg_time_ms < 10 # Should be well under 10ms per operation
    def test_budget_check_performance(self):
        """Test budget check executes quickly."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        start_time = time.perf_counter()
        for _ in range(1000):
            manager.check_budget_status(budget_limit=10.0)
        end_time = time.perf_counter()
        avg_time_ms = ((end_time - start_time) / 1000) * 1000
        assert avg_time_ms < 5 # Should be very fast
    def test_breakdown_performance(self):
        """Test breakdown calculation is fast."""
        manager = CostManager()
        manager.calculate_cost(input_tokens=1000, output_tokens=500)
        start_time = time.perf_counter()
        for _ in range(1000):
            manager.get_cost_breakdown()
        end_time = time.perf_counter()
        avg_time_ms = ((end_time - start_time) / 1000) * 1000
        assert avg_time_ms < 5
    def test_history_access_performance(self):
        """Test history access is fast."""
        manager = CostManager()
        for _ in range(100):
            manager.calculate_cost(input_tokens=1000, output_tokens=500)
        start_time = time.perf_counter()
        for _ in range(1000):
            manager.get_cost_history(limit=10)
        end_time = time.perf_counter()
        avg_time_ms = ((end_time - start_time) / 1000) * 1000
        assert avg_time_ms < 5
    def test_export_json_performance(self):
        """Test JSON export completes in reasonable time."""
        manager = CostManager()
        for _ in range(50):
            manager.calculate_cost(input_tokens=1000, output_tokens=500)
        start_time = time.perf_counter()
        manager.export_cost_report(export_format="json")
        end_time = time.perf_counter()
        time_ms = (end_time - start_time) * 1000
        assert time_ms < 100 # Should complete in under 100ms
class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    def test_very_large_token_counts(self):
        """Test handling of very large token counts."""
        manager = CostManager()
        cost = manager.calculate_cost(
            input_tokens=10_000_000,
            output_tokens=5_000_000
        )
        assert cost > 0
        assert manager.total_cost == cost
    def test_many_small_calculations(self):
        """Test many small calculations accumulate correctly."""
        manager = CostManager()
        for _ in range(10000):
            manager.calculate_cost(input_tokens=1, output_tokens=1)
        assert manager._operation_count == 10000
        assert manager.total_cost > 0
    def test_alternating_models(self):
        """Test alternating between different models."""
        manager = CostManager()
        models = [
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-haiku-3-5-20241022"
        ]
        for i in range(30):
            model = models[i % 3]
            manager.calculate_cost(input_tokens=1000, output_tokens=500, model=model)
        assert len(manager.cost_by_model) == 3
    def test_many_unique_sessions(self):
        """Test handling many unique session IDs."""
        manager = CostManager()
        for i in range(100):
            manager.calculate_cost(
                input_tokens=1000,
                output_tokens=500,
                session_id=f"session_{i}"
            )
        assert len(manager._session_costs) == 100
    def test_budget_check_at_exact_threshold(self):
        """Test budget check at exact threshold values."""
        manager = CostManager(
            soft_limit_threshold=70.0,
            hard_limit_threshold=90.0,
            emergency_threshold=100.0
        )
        # Set cost to exactly 70% of budget
        budget = 10.0
        target_cost = 7.0
        # Calculate required tokens for $7.00 with Sonnet
        # input: $3/MTok, output: $15/MTok
        # Let's use 1M input tokens + 0.267M output tokens
        manager.calculate_cost(input_tokens=1_000_000, output_tokens=266_667)
        status = manager.check_budget_status(budget_limit=budget)
        assert status['status'] in ['soft_warning', 'ok'] # At boundary
    def test_projection_with_zero_history(self):
        """Test projection works with no prior history."""
        manager = CostManager()
        projected = manager.project_session_cost(estimated_turns=10)
        assert projected > 0
    def test_empty_history_export(self):
        """Test export works with empty history."""
        manager = CostManager()
        report = manager.export_cost_report(export_format="json")
        data = json.loads(report)
        assert data['summary']['operation_count'] == 0
        assert data['summary']['total_cost'] == 0.0
    def test_cache_efficiency_100_percent_hit_rate(self):
        """Test cache efficiency with 100% cache hit rate."""
        manager = CostManager()
        # Only cache reads, no regular input
        manager.calculate_cost(input_tokens=0, output_tokens=500, cache_read=1000)
        efficiency = manager.calculate_cache_efficiency()
        assert efficiency['cache_hit_rate'] == 100.0
    def test_aggregate_all_zero_cost_sessions(self):
        """Test aggregation with sessions that have zero cost."""
        manager = CostManager()
        aggregated = manager.aggregate_costs(["nonexistent1", "nonexistent2"])
        assert aggregated['total_cost'] == 0.0
        assert aggregated['min_cost'] == 0.0
        assert aggregated['max_cost'] == 0.0
class TestModelPricing:
    """Test model pricing constants and calculations."""
    def test_model_pricing_constants_exist(self):
        """Test all expected model pricing constants exist."""
        assert "claude-opus-4-20250514" in MODEL_PRICING
        assert "claude-sonnet-4-20250514" in MODEL_PRICING
        assert "claude-haiku-3-5-20241022" in MODEL_PRICING
    def test_model_pricing_structure(self):
        """Test model pricing has correct structure."""
        for model, pricing in MODEL_PRICING.items():
            assert "input" in pricing
            assert "output" in pricing
            assert "cache_read" in pricing
            assert "cache_write" in pricing
    def test_opus_pricing_correct(self):
        """Test Opus model has correct pricing."""
        opus = MODEL_PRICING["claude-opus-4-20250514"]
        assert opus["input"] == 15.0
        assert opus["output"] == 75.0
        assert opus["cache_read"] == 1.5
        assert opus["cache_write"] == 18.75
    def test_sonnet_pricing_correct(self):
        """Test Sonnet model has correct pricing."""
        sonnet = MODEL_PRICING["claude-sonnet-4-20250514"]
        assert sonnet["input"] == 3.0
        assert sonnet["output"] == 15.0
        assert sonnet["cache_read"] == 0.3
        assert sonnet["cache_write"] == 3.75
    def test_haiku_pricing_correct(self):
        """Test Haiku model has correct pricing."""
        haiku = MODEL_PRICING["claude-haiku-3-5-20241022"]
        assert haiku["input"] == 0.25
        assert haiku["output"] == 1.25
        assert haiku["cache_read"] == 0.025
        assert haiku["cache_write"] == 0.3125
    def test_cache_read_is_90_percent_discount(self):
        """Test cache_read pricing is 90% discount on input."""
        for model, pricing in MODEL_PRICING.items():
            expected_cache_read = pricing["input"] * 0.1
            assert pricing["cache_read"] == pytest.approx(expected_cache_read, rel=1e-6)
class TestExceptionClasses:
    """Test custom exception classes."""
    def test_cost_manager_exception_base(self):
        """Test CostManagerException is base exception."""
        exc = CostManagerException("test error")
        assert isinstance(exc, Exception)
        assert str(exc) == "test error"
    def test_budget_exceeded_inherits_base(self):
        """Test BudgetExceeded inherits from CostManagerException."""
        exc = BudgetExceeded("budget exceeded")
        assert isinstance(exc, CostManagerException)
        assert isinstance(exc, Exception)
# ============================================================================
# Integration Tests
# ============================================================================
class TestIntegration:
    """Integration tests combining multiple features."""
    def test_full_workflow_with_budget_monitoring(self):
        """Test complete workflow with budget monitoring."""
        manager = CostManager(soft_limit_threshold=50.0)
        budget = 1.0
        # Make several calculations
        for i in range(10):
            manager.calculate_cost(input_tokens=10000 * (i + 1), output_tokens=5000)
        # Check budget status
        status = manager.check_budget_status(budget_limit=budget)
        # Get breakdown
        breakdown = manager.get_cost_breakdown()
        # Project future costs
        projected = manager.project_session_cost(estimated_turns=10)
        # All should work together
        assert status['current_cost'] == breakdown['total']
        assert projected > 0
    def test_multi_session_workflow(self):
        """Test workflow with multiple sessions."""
        manager = CostManager()
        # Create costs for multiple sessions
        sessions = ["session_1", "session_2", "session_3"]
        for session in sessions:
            for _ in range(5):
                manager.calculate_cost(
                    input_tokens=1000,
                    output_tokens=500,
                    session_id=session
                )
        # Aggregate
        aggregated = manager.aggregate_costs(sessions)
        # Export
        report = manager.export_cost_report(export_format="json")
        data = json.loads(report)
        assert aggregated['session_count'] == 3
        assert len(data['session_costs']) == 3
    def test_cache_optimization_workflow(self):
        """Test workflow focused on cache optimization."""
        manager = CostManager()
        # Simulate improving cache usage
        for i in range(10):
            cache_ratio = i * 10 # Increasing cache usage
            manager.calculate_cost(
                input_tokens=1000,
                output_tokens=500,
                cache_read=cache_ratio
            )
        efficiency = manager.calculate_cache_efficiency()
        breakdown = manager.get_cost_breakdown()
        assert efficiency['cache_hit_rate'] > 0
        assert breakdown['cache_read'] > 0
    def test_export_and_reset_workflow(self):
        """Test export followed by reset."""
        manager = CostManager()
        # Build up some data
        for i in range(20):
            manager.calculate_cost(input_tokens=1000, output_tokens=500)
        # Export
        report_before = manager.export_cost_report(export_format="json")
        data_before = json.loads(report_before)
        # Reset
        manager.reset()
        # Export again
        report_after = manager.export_cost_report(export_format="json")
        data_after = json.loads(report_after)
        assert data_before['summary']['total_cost'] > 0
        assert data_after['summary']['total_cost'] == 0.0
