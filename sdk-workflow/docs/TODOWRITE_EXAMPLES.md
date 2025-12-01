# TodoWrite Examples: Real-World SDK Workflow Scenarios
This document provides 7 concrete, realistic examples of TodoWrite in action across common SDK development scenarios. Each example shows the initial task list, progressive updates, and final completion state.
## Table of Contents
1. [Example 1: Simple Multi-Step Implementation](#example-1-simple-multi-step-implementation)
2. [Example 2: Bug Investigation and Fix](#example-2-bug-investigation-and-fix)
3. [Example 3: Refactoring Multiple Files](#example-3-refactoring-multiple-files)
4. [Example 4: Testing Workflow](#example-4-testing-workflow)
5. [Example 5: Documentation and Examples](#example-5-documentation-and-examples)
6. [Example 6: Complex Feature with Dependencies](#example-6-complex-feature-with-dependencies)
7. [Example 7: Error Handling and Blocked Tasks](#example-7-error-handling-and-blocked-tasks)
---
## Example 1: Simple Multi-Step Implementation
**Scenario:** Add a new `ConfigValidator` class to validate executor configurations before initialization.
### Initial TodoWrite Call
```json
[
  {
    "content": "Design ConfigValidator interface and validation rules",
    "status": "in_progress",
    "activeForm": "Designing ConfigValidator interface and validation rules"
  },
  {
    "content": "Implement ConfigValidator with common validation rules",
    "status": "pending",
    "activeForm": "Implementing ConfigValidator with common validation rules"
  },
  {
    "content": "Add ConfigValidator integration to Executor base class",
    "status": "pending",
    "activeForm": "Adding ConfigValidator integration to Executor base class"
  },
  {
    "content": "Write unit tests for ConfigValidator",
    "status": "pending",
    "activeForm": "Writing unit tests for ConfigValidator"
  }
]
```
### Progress Update 1: Design Complete
```json
[
  {
    "content": "Design ConfigValidator interface and validation rules",
    "status": "completed",
    "activeForm": "Designed ConfigValidator interface and validation rules"
  },
  {
    "content": "Implement ConfigValidator with common validation rules",
    "status": "in_progress",
    "activeForm": "Implementing ConfigValidator with common validation rules"
  },
  {
    "content": "Add ConfigValidator integration to Executor base class",
    "status": "pending",
    "activeForm": "Adding ConfigValidator integration to Executor base class"
  },
  {
    "content": "Write unit tests for ConfigValidator",
    "status": "pending",
    "activeForm": "Writing unit tests for ConfigValidator"
  }
]
```
### Progress Update 2: Implementation and Integration Done
```json
[
  {
    "content": "Design ConfigValidator interface and validation rules",
    "status": "completed",
    "activeForm": "Designed ConfigValidator interface and validation rules"
  },
  {
    "content": "Implement ConfigValidator with common validation rules",
    "status": "completed",
    "activeForm": "Implemented ConfigValidator with common validation rules"
  },
  {
    "content": "Add ConfigValidator integration to Executor base class",
    "status": "completed",
    "activeForm": "Added ConfigValidator integration to Executor base class"
  },
  {
    "content": "Write unit tests for ConfigValidator",
    "status": "in_progress",
    "activeForm": "Writing unit tests for ConfigValidator"
  }
]
```
### Final State: All Tasks Complete
```json
[
  {
    "content": "Design ConfigValidator interface and validation rules",
    "status": "completed",
    "activeForm": "Designed ConfigValidator interface and validation rules"
  },
  {
    "content": "Implement ConfigValidator with common validation rules",
    "status": "completed",
    "activeForm": "Implemented ConfigValidator with common validation rules"
  },
  {
    "content": "Add ConfigValidator integration to Executor base class",
    "status": "completed",
    "activeForm": "Added ConfigValidator integration to Executor base class"
  },
  {
    "content": "Write unit tests for ConfigValidator",
    "status": "completed",
    "activeForm": "Wrote unit tests for ConfigValidator"
  }
]
```
### Key Takeaways
- Tasks progressed sequentially from pending → in_progress → completed
- Each task marked complete immediately after finishing
- Only one task in_progress at any time
- Clear progression showing steady work completion
---
## Example 2: Bug Investigation and Fix
**Scenario:** Investigating and fixing a memory leak in the MailboxExecutor cleanup routine.
### Initial TodoWrite Call
User reports: "The MailboxExecutor isn't properly cleaning up resources. Memory usage keeps increasing."
```json
[
  {
    "content": "Reproduce memory leak with test case",
    "status": "in_progress",
    "activeForm": "Reproducing memory leak with test case"
  },
  {
    "content": "Identify root cause in cleanup logic",
    "status": "pending",
    "activeForm": "Identifying root cause in cleanup logic"
  },
  {
    "content": "Implement fix for resource cleanup",
    "status": "pending",
    "activeForm": "Implementing fix for resource cleanup"
  },
  {
    "content": "Verify fix resolves memory leak",
    "status": "pending",
    "activeForm": "Verifying fix resolves memory leak"
  },
  {
    "content": "Add regression test to prevent recurrence",
    "status": "pending",
    "activeForm": "Adding regression test to prevent recurrence"
  }
]
```
### Progress Update 1: Issue Reproduced
Created test case that clearly demonstrates the memory leak. Resource count increases on each executor lifecycle.
```json
[
  {
    "content": "Reproduce memory leak with test case",
    "status": "completed",
    "activeForm": "Reproduced memory leak with test case"
  },
  {
    "content": "Identify root cause in cleanup logic",
    "status": "in_progress",
    "activeForm": "Identifying root cause in cleanup logic"
  },
  {
    "content": "Implement fix for resource cleanup",
    "status": "pending",
    "activeForm": "Implementing fix for resource cleanup"
  },
  {
    "content": "Verify fix resolves memory leak",
    "status": "pending",
    "activeForm": "Verifying fix resolves memory leak"
  },
  {
    "content": "Add regression test to prevent recurrence",
    "status": "pending",
    "activeForm": "Adding regression test to prevent recurrence"
  }
]
```
### Progress Update 2: Root Cause Found
Analysis revealed that event listeners weren't being unregistered in the shutdown sequence. The mailbox message bus holds references to executor callbacks.
```json
[
  {
    "content": "Reproduce memory leak with test case",
    "status": "completed",
    "activeForm": "Reproduced memory leak with test case"
  },
  {
    "content": "Identify root cause in cleanup logic",
    "status": "completed",
    "activeForm": "Identified root cause in cleanup logic"
  },
  {
    "content": "Implement fix for resource cleanup",
    "status": "in_progress",
    "activeForm": "Implementing fix for resource cleanup"
  },
  {
    "content": "Verify fix resolves memory leak",
    "status": "pending",
    "activeForm": "Verifying fix resolves memory leak"
  },
  {
    "content": "Add regression test to prevent recurrence",
    "status": "pending",
    "activeForm": "Adding regression test to prevent recurrence"
  }
]
```
### Progress Update 3: Fix Implemented and Verified
Added explicit unregistration of all event listeners during executor cleanup. Test case now shows no memory leak.
```json
[
  {
    "content": "Reproduce memory leak with test case",
    "status": "completed",
    "activeForm": "Reproduced memory leak with test case"
  },
  {
    "content": "Identify root cause in cleanup logic",
    "status": "completed",
    "activeForm": "Identified root cause in cleanup logic"
  },
  {
    "content": "Implement fix for resource cleanup",
    "status": "completed",
    "activeForm": "Implemented fix for resource cleanup"
  },
  {
    "content": "Verify fix resolves memory leak",
    "status": "completed",
    "activeForm": "Verified fix resolves memory leak"
  },
  {
    "content": "Add regression test to prevent recurrence",
    "status": "in_progress",
    "activeForm": "Adding regression test to prevent recurrence"
  }
]
```
### Final State: Complete with Regression Test
All work done. New regression test added to ensure event listener cleanup is always verified.
```json
[
  {
    "content": "Reproduce memory leak with test case",
    "status": "completed",
    "activeForm": "Reproduced memory leak with test case"
  },
  {
    "content": "Identify root cause in cleanup logic",
    "status": "completed",
    "activeForm": "Identified root cause in cleanup logic"
  },
  {
    "content": "Implement fix for resource cleanup",
    "status": "completed",
    "activeForm": "Implemented fix for resource cleanup"
  },
  {
    "content": "Verify fix resolves memory leak",
    "status": "completed",
    "activeForm": "Verified fix resolves memory leak"
  },
  {
    "content": "Add regression test to prevent recurrence",
    "status": "completed",
    "activeForm": "Added regression test to prevent recurrence"
  }
]
```
### Key Takeaways
- Started with symptom (memory leak) and worked backwards to root cause
- Each investigation step marked complete before moving forward
- Tests drove the debugging process
- Regression test ensures the fix remains in place
---
## Example 3: Refactoring Multiple Files
**Scenario:** Consolidate error handling across multiple executor implementations into a single centralized error handler.
### Initial TodoWrite Call
```json
[
  {
    "content": "Identify all error handling patterns across executors",
    "status": "in_progress",
    "activeForm": "Identifying all error handling patterns across executors"
  },
  {
    "content": "Create centralized ErrorHandler utility module",
    "status": "pending",
    "activeForm": "Creating centralized ErrorHandler utility module"
  },
  {
    "content": "Refactor BashExecutor to use centralized error handler",
    "status": "pending",
    "activeForm": "Refactoring BashExecutor to use centralized error handler"
  },
  {
    "content": "Refactor PythonExecutor to use centralized error handler",
    "status": "pending",
    "activeForm": "Refactoring PythonExecutor to use centralized error handler"
  },
  {
    "content": "Refactor DockerExecutor to use centralized error handler",
    "status": "pending",
    "activeForm": "Refactoring DockerExecutor to use centralized error handler"
  },
  {
    "content": "Run full test suite and verify no regressions",
    "status": "pending",
    "activeForm": "Running full test suite and verifying no regressions"
  },
  {
    "content": "Update documentation for error handling",
    "status": "pending",
    "activeForm": "Updating documentation for error handling"
  }
]
```
### Progress Update 1: Analysis Complete
Identified 3 main error patterns: timeout handling, connection failures, and execution errors. Each pattern currently duplicated across 3 executors.
```json
[
  {
    "content": "Identify all error handling patterns across executors",
    "status": "completed",
    "activeForm": "Identified all error handling patterns across executors"
  },
  {
    "content": "Create centralized ErrorHandler utility module",
    "status": "in_progress",
    "activeForm": "Creating centralized ErrorHandler utility module"
  },
  {
    "content": "Refactor BashExecutor to use centralized error handler",
    "status": "pending",
    "activeForm": "Refactoring BashExecutor to use centralized error handler"
  },
  {
    "content": "Refactor PythonExecutor to use centralized error handler",
    "status": "pending",
    "activeForm": "Refactoring PythonExecutor to use centralized error handler"
  },
  {
    "content": "Refactor DockerExecutor to use centralized error handler",
    "status": "pending",
    "activeForm": "Refactoring DockerExecutor to use centralized error handler"
  },
  {
    "content": "Run full test suite and verify no regressions",
    "status": "pending",
    "activeForm": "Running full test suite and verifying no regressions"
  },
  {
    "content": "Update documentation for error handling",
    "status": "pending",
    "activeForm": "Updating documentation for error handling"
  }
]
```
### Progress Update 2: ErrorHandler Created
```json
[
  {
    "content": "Identify all error handling patterns across executors",
    "status": "completed",
    "activeForm": "Identified all error handling patterns across executors"
  },
  {
    "content": "Create centralized ErrorHandler utility module",
    "status": "completed",
    "activeForm": "Created centralized ErrorHandler utility module"
  },
  {
    "content": "Refactor BashExecutor to use centralized error handler",
    "status": "in_progress",
    "activeForm": "Refactoring BashExecutor to use centralized error handler"
  },
  {
    "content": "Refactor PythonExecutor to use centralized error handler",
    "status": "pending",
    "activeForm": "Refactoring PythonExecutor to use centralized error handler"
  },
  {
    "content": "Refactor DockerExecutor to use centralized error handler",
    "status": "pending",
    "activeForm": "Refactoring DockerExecutor to use centralized error handler"
  },
  {
    "content": "Run full test suite and verify no regressions",
    "status": "pending",
    "activeForm": "Running full test suite and verifying no regressions"
  },
  {
    "content": "Update documentation for error handling",
    "status": "pending",
    "activeForm": "Updating documentation for error handling"
  }
]
```
### Progress Update 3: First Executor Refactored
```json
[
  {
    "content": "Identify all error handling patterns across executors",
    "status": "completed",
    "activeForm": "Identified all error handling patterns across executors"
  },
  {
    "content": "Create centralized ErrorHandler utility module",
    "status": "completed",
    "activeForm": "Created centralized ErrorHandler utility module"
  },
  {
    "content": "Refactor BashExecutor to use centralized error handler",
    "status": "completed",
    "activeForm": "Refactored BashExecutor to use centralized error handler"
  },
  {
    "content": "Refactor PythonExecutor to use centralized error handler",
    "status": "in_progress",
    "activeForm": "Refactoring PythonExecutor to use centralized error handler"
  },
  {
    "content": "Refactor DockerExecutor to use centralized error handler",
    "status": "pending",
    "activeForm": "Refactoring DockerExecutor to use centralized error handler"
  },
  {
    "content": "Run full test suite and verify no regressions",
    "status": "pending",
    "activeForm": "Running full test suite and verifying no regressions"
  },
  {
    "content": "Update documentation for error handling",
    "status": "pending",
    "activeForm": "Updating documentation for error handling"
  }
]
```
### Progress Update 4: All Executors Refactored
```json
[
  {
    "content": "Identify all error handling patterns across executors",
    "status": "completed",
    "activeForm": "Identified all error handling patterns across executors"
  },
  {
    "content": "Create centralized ErrorHandler utility module",
    "status": "completed",
    "activeForm": "Created centralized ErrorHandler utility module"
  },
  {
    "content": "Refactor BashExecutor to use centralized error handler",
    "status": "completed",
    "activeForm": "Refactored BashExecutor to use centralized error handler"
  },
  {
    "content": "Refactor PythonExecutor to use centralized error handler",
    "status": "completed",
    "activeForm": "Refactored PythonExecutor to use centralized error handler"
  },
  {
    "content": "Refactor DockerExecutor to use centralized error handler",
    "status": "completed",
    "activeForm": "Refactored DockerExecutor to use centralized error handler"
  },
  {
    "content": "Run full test suite and verify no regressions",
    "status": "in_progress",
    "activeForm": "Running full test suite and verifying no regressions"
  },
  {
    "content": "Update documentation for error handling",
    "status": "pending",
    "activeForm": "Updating documentation for error handling"
  }
]
```
### Final State: Complete with Documentation
```json
[
  {
    "content": "Identify all error handling patterns across executors",
    "status": "completed",
    "activeForm": "Identified all error handling patterns across executors"
  },
  {
    "content": "Create centralized ErrorHandler utility module",
    "status": "completed",
    "activeForm": "Created centralized ErrorHandler utility module"
  },
  {
    "content": "Refactor BashExecutor to use centralized error handler",
    "status": "completed",
    "activeForm": "Refactored BashExecutor to use centralized error handler"
  },
  {
    "content": "Refactor PythonExecutor to use centralized error handler",
    "status": "completed",
    "activeForm": "Refactored PythonExecutor to use centralized error handler"
  },
  {
    "content": "Refactor DockerExecutor to use centralized error handler",
    "status": "completed",
    "activeForm": "Refactored DockerExecutor to use centralized error handler"
  },
  {
    "content": "Run full test suite and verify no regressions",
    "status": "completed",
    "activeForm": "Ran full test suite and verified no regressions"
  },
  {
    "content": "Update documentation for error handling",
    "status": "completed",
    "activeForm": "Updated documentation for error handling"
  }
]
```
### Key Takeaways
- Refactoring of multiple files broken into distinct per-file tasks
- Systematic progression through codebase
- Testing performed only after all refactoring complete to ensure no issues introduced
- Documentation updated at the end
---
## Example 4: Testing Workflow
**Scenario:** Add comprehensive test coverage for the new CacheManager feature.
### Initial TodoWrite Call
```json
[
  {
    "content": "Write unit tests for CacheManager initialization and cleanup",
    "status": "in_progress",
    "activeForm": "Writing unit tests for CacheManager initialization and cleanup"
  },
  {
    "content": "Write unit tests for cache operations (get, set, delete)",
    "status": "pending",
    "activeForm": "Writing unit tests for cache operations (get, set, delete)"
  },
  {
    "content": "Write tests for cache expiration and TTL handling",
    "status": "pending",
    "activeForm": "Writing tests for cache expiration and TTL handling"
  },
  {
    "content": "Write tests for concurrent access and thread safety",
    "status": "pending",
    "activeForm": "Writing tests for concurrent access and thread safety"
  },
  {
    "content": "Run full test suite and fix any failures",
    "status": "pending",
    "activeForm": "Running full test suite and fixing any failures"
  },
  {
    "content": "Verify code coverage meets 80% threshold",
    "status": "pending",
    "activeForm": "Verifying code coverage meets 80% threshold"
  }
]
```
### Progress Update 1: Basic Unit Tests Complete
```json
[
  {
    "content": "Write unit tests for CacheManager initialization and cleanup",
    "status": "completed",
    "activeForm": "Wrote unit tests for CacheManager initialization and cleanup"
  },
  {
    "content": "Write unit tests for cache operations (get, set, delete)",
    "status": "in_progress",
    "activeForm": "Writing unit tests for cache operations (get, set, delete)"
  },
  {
    "content": "Write tests for cache expiration and TTL handling",
    "status": "pending",
    "activeForm": "Writing tests for cache expiration and TTL handling"
  },
  {
    "content": "Write tests for concurrent access and thread safety",
    "status": "pending",
    "activeForm": "Writing tests for concurrent access and thread safety"
  },
  {
    "content": "Run full test suite and fix any failures",
    "status": "pending",
    "activeForm": "Running full test suite and fixing any failures"
  },
  {
    "content": "Verify code coverage meets 80% threshold",
    "status": "pending",
    "activeForm": "Verifying code coverage meets 80% threshold"
  }
]
```
### Progress Update 2: Core Operations Tested
```json
[
  {
    "content": "Write unit tests for CacheManager initialization and cleanup",
    "status": "completed",
    "activeForm": "Wrote unit tests for CacheManager initialization and cleanup"
  },
  {
    "content": "Write unit tests for cache operations (get, set, delete)",
    "status": "completed",
    "activeForm": "Wrote unit tests for cache operations (get, set, delete)"
  },
  {
    "content": "Write tests for cache expiration and TTL handling",
    "status": "in_progress",
    "activeForm": "Writing tests for cache expiration and TTL handling"
  },
  {
    "content": "Write tests for concurrent access and thread safety",
    "status": "pending",
    "activeForm": "Writing tests for concurrent access and thread safety"
  },
  {
    "content": "Run full test suite and fix any failures",
    "status": "pending",
    "activeForm": "Running full test suite and fixing any failures"
  },
  {
    "content": "Verify code coverage meets 80% threshold",
    "status": "pending",
    "activeForm": "Verifying code coverage meets 80% threshold"
  }
]
```
### Progress Update 3: All Tests Written, Running Suite
```json
[
  {
    "content": "Write unit tests for CacheManager initialization and cleanup",
    "status": "completed",
    "activeForm": "Wrote unit tests for CacheManager initialization and cleanup"
  },
  {
    "content": "Write unit tests for cache operations (get, set, delete)",
    "status": "completed",
    "activeForm": "Wrote unit tests for cache operations (get, set, delete)"
  },
  {
    "content": "Write tests for cache expiration and TTL handling",
    "status": "completed",
    "activeForm": "Wrote tests for cache expiration and TTL handling"
  },
  {
    "content": "Write tests for concurrent access and thread safety",
    "status": "completed",
    "activeForm": "Wrote tests for concurrent access and thread safety"
  },
  {
    "content": "Run full test suite and fix any failures",
    "status": "in_progress",
    "activeForm": "Running full test suite and fixing any failures"
  },
  {
    "content": "Verify code coverage meets 80% threshold",
    "status": "pending",
    "activeForm": "Verifying code coverage meets 80% threshold"
  }
]
```
### Progress Update 4: Tests Passing, Coverage Check
Found 3 test failures in concurrent access tests. Fixed race condition in cache locking mechanism.
```json
[
  {
    "content": "Write unit tests for CacheManager initialization and cleanup",
    "status": "completed",
    "activeForm": "Wrote unit tests for CacheManager initialization and cleanup"
  },
  {
    "content": "Write unit tests for cache operations (get, set, delete)",
    "status": "completed",
    "activeForm": "Wrote unit tests for cache operations (get, set, delete)"
  },
  {
    "content": "Write tests for cache expiration and TTL handling",
    "status": "completed",
    "activeForm": "Wrote tests for cache expiration and TTL handling"
  },
  {
    "content": "Write tests for concurrent access and thread safety",
    "status": "completed",
    "activeForm": "Wrote tests for concurrent access and thread safety"
  },
  {
    "content": "Run full test suite and fix any failures",
    "status": "completed",
    "activeForm": "Ran full test suite and fixed failures"
  },
  {
    "content": "Verify code coverage meets 80% threshold",
    "status": "in_progress",
    "activeForm": "Verifying code coverage meets 80% threshold"
  }
]
```
### Final State: Coverage Verified
```json
[
  {
    "content": "Write unit tests for CacheManager initialization and cleanup",
    "status": "completed",
    "activeForm": "Wrote unit tests for CacheManager initialization and cleanup"
  },
  {
    "content": "Write unit tests for cache operations (get, set, delete)",
    "status": "completed",
    "activeForm": "Wrote unit tests for cache operations (get, set, delete)"
  },
  {
    "content": "Write tests for cache expiration and TTL handling",
    "status": "completed",
    "activeForm": "Wrote tests for cache expiration and TTL handling"
  },
  {
    "content": "Write tests for concurrent access and thread safety",
    "status": "completed",
    "activeForm": "Wrote tests for concurrent access and thread safety"
  },
  {
    "content": "Run full test suite and fix any failures",
    "status": "completed",
    "activeForm": "Ran full test suite and fixed failures"
  },
  {
    "content": "Verify code coverage meets 80% threshold",
    "status": "completed",
    "activeForm": "Verified code coverage meets 85% threshold"
  }
]
```
### Key Takeaways
- Test writing broken into logical groups (initialization, operations, expiration, concurrency)
- Test execution and failure fixing marked as a single task (because fixing failures is part of the test validation process)
- Tests discovered and fixed a real concurrency bug
- Coverage verification showed 85% (exceeding the 80% threshold)
---
## Example 5: Documentation and Examples
**Scenario:** Create comprehensive documentation for the new AsyncMailboxExecutor feature.
### Initial TodoWrite Call
```json
[
  {
    "content": "Write API reference documentation for AsyncMailboxExecutor",
    "status": "in_progress",
    "activeForm": "Writing API reference documentation for AsyncMailboxExecutor"
  },
  {
    "content": "Create basic usage example script",
    "status": "pending",
    "activeForm": "Creating basic usage example script"
  },
  {
    "content": "Create advanced usage examples (error handling, timeouts)",
    "status": "pending",
    "activeForm": "Creating advanced usage examples (error handling, timeouts)"
  },
  {
    "content": "Write integration guide with MessageBus",
    "status": "pending",
    "activeForm": "Writing integration guide with MessageBus"
  },
  {
    "content": "Add troubleshooting guide",
    "status": "pending",
    "activeForm": "Adding troubleshooting guide"
  },
  {
    "content": "Review all documentation for clarity and correctness",
    "status": "pending",
    "activeForm": "Reviewing all documentation for clarity and correctness"
  }
]
```
### Progress Update 1: API Reference Complete
```json
[
  {
    "content": "Write API reference documentation for AsyncMailboxExecutor",
    "status": "completed",
    "activeForm": "Wrote API reference documentation for AsyncMailboxExecutor"
  },
  {
    "content": "Create basic usage example script",
    "status": "in_progress",
    "activeForm": "Creating basic usage example script"
  },
  {
    "content": "Create advanced usage examples (error handling, timeouts)",
    "status": "pending",
    "activeForm": "Creating advanced usage examples (error handling, timeouts)"
  },
  {
    "content": "Write integration guide with MessageBus",
    "status": "pending",
    "activeForm": "Writing integration guide with MessageBus"
  },
  {
    "content": "Add troubleshooting guide",
    "status": "pending",
    "activeForm": "Adding troubleshooting guide"
  },
  {
    "content": "Review all documentation for clarity and correctness",
    "status": "pending",
    "activeForm": "Reviewing all documentation for clarity and correctness"
  }
]
```
### Progress Update 2: Basic and Advanced Examples Complete
```json
[
  {
    "content": "Write API reference documentation for AsyncMailboxExecutor",
    "status": "completed",
    "activeForm": "Wrote API reference documentation for AsyncMailboxExecutor"
  },
  {
    "content": "Create basic usage example script",
    "status": "completed",
    "activeForm": "Created basic usage example script"
  },
  {
    "content": "Create advanced usage examples (error handling, timeouts)",
    "status": "completed",
    "activeForm": "Created advanced usage examples (error handling, timeouts)"
  },
  {
    "content": "Write integration guide with MessageBus",
    "status": "in_progress",
    "activeForm": "Writing integration guide with MessageBus"
  },
  {
    "content": "Add troubleshooting guide",
    "status": "pending",
    "activeForm": "Adding troubleshooting guide"
  },
  {
    "content": "Review all documentation for clarity and correctness",
    "status": "pending",
    "activeForm": "Reviewing all documentation for clarity and correctness"
  }
]
```
### Progress Update 3: Integration Guide and Troubleshooting Complete
```json
[
  {
    "content": "Write API reference documentation for AsyncMailboxExecutor",
    "status": "completed",
    "activeForm": "Wrote API reference documentation for AsyncMailboxExecutor"
  },
  {
    "content": "Create basic usage example script",
    "status": "completed",
    "activeForm": "Created basic usage example script"
  },
  {
    "content": "Create advanced usage examples (error handling, timeouts)",
    "status": "completed",
    "activeForm": "Created advanced usage examples (error handling, timeouts)"
  },
  {
    "content": "Write integration guide with MessageBus",
    "status": "completed",
    "activeForm": "Wrote integration guide with MessageBus"
  },
  {
    "content": "Add troubleshooting guide",
    "status": "completed",
    "activeForm": "Added troubleshooting guide"
  },
  {
    "content": "Review all documentation for clarity and correctness",
    "status": "in_progress",
    "activeForm": "Reviewing all documentation for clarity and correctness"
  }
]
```
### Final State: All Documentation Complete and Reviewed
```json
[
  {
    "content": "Write API reference documentation for AsyncMailboxExecutor",
    "status": "completed",
    "activeForm": "Wrote API reference documentation for AsyncMailboxExecutor"
  },
  {
    "content": "Create basic usage example script",
    "status": "completed",
    "activeForm": "Created basic usage example script"
  },
  {
    "content": "Create advanced usage examples (error handling, timeouts)",
    "status": "completed",
    "activeForm": "Created advanced usage examples (error handling, timeouts)"
  },
  {
    "content": "Write integration guide with MessageBus",
    "status": "completed",
    "activeForm": "Wrote integration guide with MessageBus"
  },
  {
    "content": "Add troubleshooting guide",
    "status": "completed",
    "activeForm": "Added troubleshooting guide"
  },
  {
    "content": "Review all documentation for clarity and correctness",
    "status": "completed",
    "activeForm": "Reviewed all documentation for clarity and correctness"
  }
]
```
### Key Takeaways
- Documentation structured from reference to examples to troubleshooting
- Each component created and reviewed separately
- Systematic progression ensuring comprehensive coverage
- Final review step ensures quality before release
---
## Example 6: Complex Feature with Dependencies
**Scenario:** Implement the new Session Resume feature with multiple dependent components.
### Initial TodoWrite Call
```json
[
  {
    "content": "Design Session Resume architecture and data models",
    "status": "in_progress",
    "activeForm": "Designing Session Resume architecture and data models"
  },
  {
    "content": "Implement SessionState serialization and persistence",
    "status": "pending",
    "activeForm": "Implementing SessionState serialization and persistence"
  },
  {
    "content": "Implement session checkpoint creation at completion",
    "status": "pending",
    "activeForm": "Implementing session checkpoint creation at completion"
  },
  {
    "content": "Implement session restoration from checkpoint",
    "status": "pending",
    "activeForm": "Implementing session restoration from checkpoint"
  },
  {
    "content": "Integrate with CLI for --resume flag",
    "status": "pending",
    "activeForm": "Integrating with CLI for --resume flag"
  },
  {
    "content": "Add validation for checkpoint compatibility",
    "status": "pending",
    "activeForm": "Adding validation for checkpoint compatibility"
  },
  {
    "content": "Write integration tests for session resume workflow",
    "status": "pending",
    "activeForm": "Writing integration tests for session resume workflow"
  },
  {
    "content": "Add documentation with resume examples",
    "status": "pending",
    "activeForm": "Adding documentation with resume examples"
  }
]
```
### Progress Update 1: Architecture and Serialization Done
Designed session state model. Implemented JSON serialization with version tagging for forward compatibility.
```json
[
  {
    "content": "Design Session Resume architecture and data models",
    "status": "completed",
    "activeForm": "Designed Session Resume architecture and data models"
  },
  {
    "content": "Implement SessionState serialization and persistence",
    "status": "completed",
    "activeForm": "Implemented SessionState serialization and persistence"
  },
  {
    "content": "Implement session checkpoint creation at completion",
    "status": "in_progress",
    "activeForm": "Implementing session checkpoint creation at completion"
  },
  {
    "content": "Implement session restoration from checkpoint",
    "status": "pending",
    "activeForm": "Implementing session restoration from checkpoint"
  },
  {
    "content": "Integrate with CLI for --resume flag",
    "status": "pending",
    "activeForm": "Integrating with CLI for --resume flag"
  },
  {
    "content": "Add validation for checkpoint compatibility",
    "status": "pending",
    "activeForm": "Adding validation for checkpoint compatibility"
  },
  {
    "content": "Write integration tests for session resume workflow",
    "status": "pending",
    "activeForm": "Writing integration tests for session resume workflow"
  },
  {
    "content": "Add documentation with resume examples",
    "status": "pending",
    "activeForm": "Adding documentation with resume examples"
  }
]
```
### Progress Update 2: Checkpoint and Restoration Complete
```json
[
  {
    "content": "Design Session Resume architecture and data models",
    "status": "completed",
    "activeForm": "Designed Session Resume architecture and data models"
  },
  {
    "content": "Implement SessionState serialization and persistence",
    "status": "completed",
    "activeForm": "Implemented SessionState serialization and persistence"
  },
  {
    "content": "Implement session checkpoint creation at completion",
    "status": "completed",
    "activeForm": "Implemented session checkpoint creation at completion"
  },
  {
    "content": "Implement session restoration from checkpoint",
    "status": "completed",
    "activeForm": "Implemented session restoration from checkpoint"
  },
  {
    "content": "Integrate with CLI for --resume flag",
    "status": "in_progress",
    "activeForm": "Integrating with CLI for --resume flag"
  },
  {
    "content": "Add validation for checkpoint compatibility",
    "status": "pending",
    "activeForm": "Adding validation for checkpoint compatibility"
  },
  {
    "content": "Write integration tests for session resume workflow",
    "status": "pending",
    "activeForm": "Writing integration tests for session resume workflow"
  },
  {
    "content": "Add documentation with resume examples",
    "status": "pending",
    "activeForm": "Adding documentation with resume examples"
  }
]
```
### Progress Update 3: CLI Integration and Validation Done
```json
[
  {
    "content": "Design Session Resume architecture and data models",
    "status": "completed",
    "activeForm": "Designed Session Resume architecture and data models"
  },
  {
    "content": "Implement SessionState serialization and persistence",
    "status": "completed",
    "activeForm": "Implemented SessionState serialization and persistence"
  },
  {
    "content": "Implement session checkpoint creation at completion",
    "status": "completed",
    "activeForm": "Implemented session checkpoint creation at completion"
  },
  {
    "content": "Implement session restoration from checkpoint",
    "status": "completed",
    "activeForm": "Implemented session restoration from checkpoint"
  },
  {
    "content": "Integrate with CLI for --resume flag",
    "status": "completed",
    "activeForm": "Integrated with CLI for --resume flag"
  },
  {
    "content": "Add validation for checkpoint compatibility",
    "status": "completed",
    "activeForm": "Added validation for checkpoint compatibility"
  },
  {
    "content": "Write integration tests for session resume workflow",
    "status": "in_progress",
    "activeForm": "Writing integration tests for session resume workflow"
  },
  {
    "content": "Add documentation with resume examples",
    "status": "pending",
    "activeForm": "Adding documentation with resume examples"
  }
]
```
### Final State: Feature Complete with Tests and Docs
```json
[
  {
    "content": "Design Session Resume architecture and data models",
    "status": "completed",
    "activeForm": "Designed Session Resume architecture and data models"
  },
  {
    "content": "Implement SessionState serialization and persistence",
    "status": "completed",
    "activeForm": "Implemented SessionState serialization and persistence"
  },
  {
    "content": "Implement session checkpoint creation at completion",
    "status": "completed",
    "activeForm": "Implemented session checkpoint creation at completion"
  },
  {
    "content": "Implement session restoration from checkpoint",
    "status": "completed",
    "activeForm": "Implemented session restoration from checkpoint"
  },
  {
    "content": "Integrate with CLI for --resume flag",
    "status": "completed",
    "activeForm": "Integrated with CLI for --resume flag"
  },
  {
    "content": "Add validation for checkpoint compatibility",
    "status": "completed",
    "activeForm": "Added validation for checkpoint compatibility"
  },
  {
    "content": "Write integration tests for session resume workflow",
    "status": "completed",
    "activeForm": "Wrote integration tests for session resume workflow"
  },
  {
    "content": "Add documentation with resume examples",
    "status": "completed",
    "activeForm": "Added documentation with resume examples"
  }
]
```
### Key Takeaways
- Complex feature with 8 interconnected tasks
- Tasks ordered by dependency (architecture before implementation)
- Validation added as separate task ensuring quality gate
- Tests and documentation at the end, after core feature complete
- Systematic progression through complex implementation
---
## Example 7: Error Handling and Blocked Tasks
**Scenario:** Implementing thread pool improvements but blocked by missing dependency.
### Initial TodoWrite Call
```json
[
  {
    "content": "Analyze current thread pool implementation for bottlenecks",
    "status": "in_progress",
    "activeForm": "Analyzing current thread pool implementation for bottlenecks"
  },
  {
    "content": "Design new thread pool architecture with work-stealing queues",
    "status": "pending",
    "activeForm": "Designing new thread pool architecture with work-stealing queues"
  },
  {
    "content": "Implement new thread pool with work-stealing queues",
    "status": "pending",
    "activeForm": "Implementing new thread pool with work-stealing queues"
  },
  {
    "content": "Benchmark new implementation against current",
    "status": "pending",
    "activeForm": "Benchmarking new implementation against current"
  },
  {
    "content": "Deploy thread pool improvements",
    "status": "pending",
    "activeForm": "Deploying thread pool improvements"
  }
]
```
### Progress Update 1: Analysis Complete, Then Blocked
Analysis reveals we need a newer version of the concurrent library for work-stealing queue implementation. Current version is incompatible.
```json
[
  {
    "content": "Analyze current thread pool implementation for bottlenecks",
    "status": "completed",
    "activeForm": "Analyzed current thread pool implementation for bottlenecks"
  },
  {
    "content": "Install and configure concurrent library v3.0.1",
    "status": "in_progress",
    "activeForm": "Installing and configuring concurrent library v3.0.1"
  },
  {
    "content": "Design new thread pool architecture with work-stealing queues",
    "status": "pending",
    "activeForm": "Designing new thread pool architecture with work-stealing queues"
  },
  {
    "content": "Implement new thread pool with work-stealing queues",
    "status": "pending",
    "activeForm": "Implementing new thread pool with work-stealing queues"
  },
  {
    "content": "Benchmark new implementation against current",
    "status": "pending",
    "activeForm": "Benchmarking new implementation against current"
  },
  {
    "content": "Deploy thread pool improvements",
    "status": "pending",
    "activeForm": "Deploying thread pool improvements"
  }
]
```
**Note:** Blocking task "Install concurrent library v3.0.1" was created and marked in_progress to address the dependency issue.
### Progress Update 2: Dependency Installed, Resuming
Concurrent library v3.0.1 successfully installed and tested. Now resuming original work.
```json
[
  {
    "content": "Analyze current thread pool implementation for bottlenecks",
    "status": "completed",
    "activeForm": "Analyzed current thread pool implementation for bottlenecks"
  },
  {
    "content": "Install and configure concurrent library v3.0.1",
    "status": "completed",
    "activeForm": "Installed and configured concurrent library v3.0.1"
  },
  {
    "content": "Design new thread pool architecture with work-stealing queues",
    "status": "in_progress",
    "activeForm": "Designing new thread pool architecture with work-stealing queues"
  },
  {
    "content": "Implement new thread pool with work-stealing queues",
    "status": "pending",
    "activeForm": "Implementing new thread pool with work-stealing queues"
  },
  {
    "content": "Benchmark new implementation against current",
    "status": "pending",
    "activeForm": "Benchmarking new implementation against current"
  },
  {
    "content": "Deploy thread pool improvements",
    "status": "pending",
    "activeForm": "Deploying thread pool improvements"
  }
]
```
### Progress Update 3: Design Complete
```json
[
  {
    "content": "Analyze current thread pool implementation for bottlenecks",
    "status": "completed",
    "activeForm": "Analyzed current thread pool implementation for bottlenecks"
  },
  {
    "content": "Install and configure concurrent library v3.0.1",
    "status": "completed",
    "activeForm": "Installed and configured concurrent library v3.0.1"
  },
  {
    "content": "Design new thread pool architecture with work-stealing queues",
    "status": "completed",
    "activeForm": "Designed new thread pool architecture with work-stealing queues"
  },
  {
    "content": "Implement new thread pool with work-stealing queues",
    "status": "in_progress",
    "activeForm": "Implementing new thread pool with work-stealing queues"
  },
  {
    "content": "Benchmark new implementation against current",
    "status": "pending",
    "activeForm": "Benchmarking new implementation against current"
  },
  {
    "content": "Deploy thread pool improvements",
    "status": "pending",
    "activeForm": "Deploying thread pool improvements"
  }
]
```
### Progress Update 4: Implementation Complete, Benchmarking
```json
[
  {
    "content": "Analyze current thread pool implementation for bottlenecks",
    "status": "completed",
    "activeForm": "Analyzed current thread pool implementation for bottlenecks"
  },
  {
    "content": "Install and configure concurrent library v3.0.1",
    "status": "completed",
    "activeForm": "Installed and configured concurrent library v3.0.1"
  },
  {
    "content": "Design new thread pool architecture with work-stealing queues",
    "status": "completed",
    "activeForm": "Designed new thread pool architecture with work-stealing queues"
  },
  {
    "content": "Implement new thread pool with work-stealing queues",
    "status": "completed",
    "activeForm": "Implemented new thread pool with work-stealing queues"
  },
  {
    "content": "Benchmark new implementation against current",
    "status": "in_progress",
    "activeForm": "Benchmarking new implementation against current"
  },
  {
    "content": "Deploy thread pool improvements",
    "status": "pending",
    "activeForm": "Deploying thread pool improvements"
  }
]
```
### Final State: Feature Complete and Deployed
Benchmarks show 35% improvement in throughput. Deployment successful with no issues.
```json
[
  {
    "content": "Analyze current thread pool implementation for bottlenecks",
    "status": "completed",
    "activeForm": "Analyzed current thread pool implementation for bottlenecks"
  },
  {
    "content": "Install and configure concurrent library v3.0.1",
    "status": "completed",
    "activeForm": "Installed and configured concurrent library v3.0.1"
  },
  {
    "content": "Design new thread pool architecture with work-stealing queues",
    "status": "completed",
    "activeForm": "Designed new thread pool architecture with work-stealing queues"
  },
  {
    "content": "Implement new thread pool with work-stealing queues",
    "status": "completed",
    "activeForm": "Implemented new thread pool with work-stealing queues"
  },
  {
    "content": "Benchmark new implementation against current",
    "status": "completed",
    "activeForm": "Benchmarked new implementation against current (35% improvement)"
  },
  {
    "content": "Deploy thread pool improvements",
    "status": "completed",
    "activeForm": "Deployed thread pool improvements"
  }
]
```
### Key Takeaways
- Hit a blocker: missing dependency became clear during analysis
- Rather than abandoning work, created explicit blocking task
- Addressed blocker immediately, allowing continuation
- Marked all intermediate completion points clearly
- Final state shows clean progression from analysis to deployment
- Benchmark results captured in task description for reference
---
## Summary: TodoWrite Usage Patterns
Across these 7 examples, you see common patterns:
1. **Initialization**: Start with the first task as `in_progress`
2. **Sequential Progression**: Move through tasks one at a time
3. **Immediate Marking**: Mark tasks complete as soon as they're done
4. **Blocker Handling**: When blocked, create explicit task for blocker
5. **Real-Time Updates**: Update task list frequently as work progresses
6. **Clear Descriptions**: Use both content and activeForm consistently
7. **Completion Verification**: Only mark done when truly complete
These patterns ensure clear communication, accurate progress tracking, and systematic completion of complex SDK development work.
