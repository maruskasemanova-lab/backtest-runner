Route this task to the right project domain before coding.

Input task:
$ARGUMENTS

Process:
1. Read `bmad/context/generated/00-index.md`.
2. Pick exactly one primary domain pack.
3. List secondary domains only if interface changes are required.
4. Return:
   - `primary_domain`
   - `primary_pack`
   - `files_to_read_first` (max 8)
   - `cross_domain_risks`

If unclear, propose two possible domains and the deciding question.
