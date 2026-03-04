---
description: Delegate complex tasks to a BMAD orchestration agent that enforces Axon-first analysis, domain discipline, and required validation.
argument-hint: [task]
allowed-tools: Task(bmad-orchestration-agent), Read, Grep, Glob
model: sonnet
---

# BMAD Orchestrate

Task:
$ARGUMENTS

Workflow:
1. Invoke `Task` with `subagent_type="bmad-orchestration-agent"`.
2. Pass the full task text and require strict adherence to `AGENTS.md` and `CLAUDE.md`.
3. Require final output fields:
   - `primary_domain`
   - `changed_files`
   - `test_results`
   - `contract_changes`
   - `residual_risks`

Do not skip required verification commands.
