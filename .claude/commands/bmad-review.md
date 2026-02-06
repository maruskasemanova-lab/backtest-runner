Perform a risk-first code review for this task.

Scope:
$ARGUMENTS

Review priorities (in order):
1. Behavioral regressions
2. Look-ahead bias leaks
3. Execution/risk model inconsistencies
4. API contract breaks (runner <-> strategy API <-> frontend)
5. Missing tests

Output format:
- Findings (severity ordered) with file references
- Open questions
- Suggested fixes
