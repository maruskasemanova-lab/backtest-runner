---
description: Route a task to the correct primary BMAD domain and surface cross-domain interface risks.
argument-hint: "[task]"
allowed-tools: Read, Grep, Glob, mcp__axon__*
model: sonnet
---

Route this task to the right project domain before coding.

Input task:
$ARGUMENTS

Required context files:
1. `bmad/context/generated/00-index.md`
2. `bmad/context/generated/00-machine-index.json`
3. Relevant domain pack in `bmad/context/generated/<domain>.md`

Process:
1. Pick exactly one primary domain pack.
2. List secondary domains only if interface changes are required.
3. Return schema-first output:

```yaml
primary_domain: <domain-id>
primary_pack: bmad/context/generated/<domain>.md
files_to_read_first:
  - <path>
secondary_domains:
  - <domain-id>
cross_domain_risks:
  - <risk>
```

If unclear, propose two possible domains and the deciding question.
