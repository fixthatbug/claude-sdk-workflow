"""Workflow Management - Workflow integration and batch processing."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    """A step in a workflow."""
    name: str
    handler: Callable
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: float = 300.0
    retries: int = 3


@dataclass
class WorkflowResult:
    """Result of workflow execution."""
    success: bool
    steps_completed: int
    total_steps: int
    results: Dict[str, Any]
    errors: List[str]
    duration_seconds: float


class WorkflowModeIntegrator:
    """Integrate different execution modes into workflows."""
    
    def __init__(self):
        self._steps: Dict[str, WorkflowStep] = {}
        self._results: Dict[str, Any] = {}
        self._errors: List[str] = []
    
    def add_step(self, step: WorkflowStep) -> None:
        """Add a step to the workflow."""
        self._steps[step.name] = step
    
    def _get_execution_order(self) -> List[str]:
        """Get topologically sorted execution order."""
        visited = set()
        order = []
        
        def visit(name: str):
            if name in visited:
                return
            visited.add(name)
            step = self._steps.get(name)
            if step:
                for dep in step.dependencies:
                    visit(dep)
                order.append(name)
        
        for name in self._steps:
            visit(name)
        
        return order
    
    async def execute(self, context: Optional[Dict] = None) -> WorkflowResult:
        """Execute the workflow."""
        start = datetime.now()
        context = context or {}
        self._results.clear()
        self._errors.clear()
        
        order = self._get_execution_order()
        completed = 0
        
        for step_name in order:
            step = self._steps[step_name]
            try:
                # Gather dependency results
                dep_results = {d: self._results.get(d) for d in step.dependencies}
                
                # Execute with timeout
                result = await asyncio.wait_for(
                    self._run_step(step, context, dep_results),
                    timeout=step.timeout_seconds
                )
                self._results[step_name] = result
                completed += 1
                
            except asyncio.TimeoutError:
                self._errors.append(f"{step_name}: timeout")
            except Exception as e:
                self._errors.append(f"{step_name}: {str(e)}")
        
        return WorkflowResult(
            success=len(self._errors) == 0,
            steps_completed=completed,
            total_steps=len(order),
            results=self._results.copy(),
            errors=self._errors.copy(),
            duration_seconds=(datetime.now() - start).total_seconds()
        )
    
    async def _run_step(
        self,
        step: WorkflowStep,
        context: Dict,
        dep_results: Dict
    ) -> Any:
        """Run a single step with retries."""
        last_error = None
        
        for attempt in range(step.retries):
            try:
                if asyncio.iscoroutinefunction(step.handler):
                    return await step.handler(context, dep_results)
                return step.handler(context, dep_results)
            except Exception as e:
                last_error = e
                if attempt < step.retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
        
        raise last_error or Exception("Unknown error")


@dataclass
class BatchItem:
    """An item in a batch."""
    id: str
    data: Any
    result: Optional[Any] = None
    error: Optional[str] = None


class BatchProcessor:
    """Process items in batches."""
    
    def __init__(
        self,
        batch_size: int = 10,
        concurrency: int = 5,
        on_progress: Optional[Callable[[int, int], None]] = None
    ):
        self.batch_size = batch_size
        self.concurrency = concurrency
        self.on_progress = on_progress
    
    async def process(
        self,
        items: List[Any],
        processor: Callable[[Any], Any]
    ) -> List[BatchItem]:
        """Process all items in batches."""
        results = []
        total = len(items)
        completed = 0
        
        for i in range(0, total, self.batch_size):
            batch = items[i:i + self.batch_size]
            batch_items = [BatchItem(id=str(i + j), data=item) for j, item in enumerate(batch)]
            
            # Process batch with concurrency limit
            semaphore = asyncio.Semaphore(self.concurrency)
            
            async def process_item(item: BatchItem):
                async with semaphore:
                    try:
                        if asyncio.iscoroutinefunction(processor):
                            item.result = await processor(item.data)
                        else:
                            item.result = processor(item.data)
                    except Exception as e:
                        item.error = str(e)
                    return item
            
            batch_results = await asyncio.gather(*[process_item(item) for item in batch_items])
            results.extend(batch_results)
            
            completed += len(batch)
            if self.on_progress:
                self.on_progress(completed, total)
        
        return results


__all__ = [
    'WorkflowStep',
    'WorkflowResult',
    'WorkflowModeIntegrator',
    'BatchItem',
    'BatchProcessor',
]
