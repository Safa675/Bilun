# AGENTS.md

These rules override default model behavior and must be followed strictly.

---

# Workflow Orchestration

## 1. Self-Improvement Loop

The agent must continuously improve its behavior using a persistent lessons system.

- After ANY correction from the user, immediately update `tasks/lessons.md`
- Extract the **pattern behind the mistake**, not just the incident
- Write a rule that prevents the mistake from happening again
- Iterate on lessons until the same mistake stops occurring
- Review `tasks/lessons.md` **at the start of every session**

Learning from mistakes is mandatory. Repeating mistakes means the lesson rule must be rewritten stronger.

---

## 2. Mandatory Specification Extraction Before Implementation

Before implementing anything, the agent must eliminate ambiguity and fully understand the task.

Confirm the following before implementation:

- Exact goal and expected outcome
- Scope boundaries (what is included vs excluded)
- Target environment (language, framework, runtime)
- Integration points with existing systems
- UI/UX expectations (if applicable)
- Performance constraints (if relevant)
- Edge cases and failure conditions
- Definition of done (clear success criteria)

### Clarification Rule

If **any uncertainty exists**, ask questions until the task is fully specified.

- No assumptions  
- No silent inference  
- No guessing missing requirements  

### Implementation Gate

Implementation may only begin after:

- Requirements are fully clarified
- Plan is written in `tasks/todo.md`
- Plan is verified
- Success criteria are explicit

### Hard Rule

Never start coding based on guesses or partial understanding.

Premature implementation is considered a **critical failure**.

---

## 3. Mandatory Subagent and Teammate 

Use teammates and subagents aggressively. Default to delegation unless the task is trivially fast.

### When to spawn a teammate

- Any research, investigation, or exploration task — always offload
- Any parallel workstream — never do sequentially what can run concurrently
- Any deep technical sub-problem unrelated to the current orchestration step
- Any task whose output feeds another task — pipeline them
- Any ambiguous requirement that needs scouting before committing

### Rules

- One focused task per subagent — no multi-tasking within a single subagent
- Give each subagent full context: goal, constraints, definition of done
- Main agent orchestrates only — it never does work a subagent could do
- Prefer spawning 3 subagents in parallel over 3 sequential steps
- Subagents must verify their own output before returning it

### Hard rule

If a task takes more than ~2 minutes to do alone, a teammate should be doing it or helping. Doing everything solo in a complex workflow is a planning failure.

---

## 4. Verification Before Done

Never mark a task complete without proving it works.

Verification steps may include:

- Running tests
- Inspecting logs
- Comparing behavior before and after changes
- Validating expected outputs

Ask yourself:

> Would a staff engineer approve this change?

Demonstrate correctness before declaring completion.

---

## 5. Zombie Process Check — Before ANY Debugging

**Before touching a single line of code when a server won't start or a port is in use — kill zombie processes first.**

This step is mandatory. Skipping it and going straight to code debugging is a critical failure.

### When to run this check

Any time you see errors like:
- `[Errno 98] Address already in use`
- `EADDRINUSE`
- `port XXXX is already allocated`
- A server that "starts" but behaves like an old version is still running
- Unexpected stale state after a restart

### The Check — Run This First

```bash
# Find what's holding your ports
lsof -i :8000
lsof -i :3000

# Or check by process name
ps aux | grep uvicorn
ps aux | grep node
ps aux | grep next

# Kill by port
kill -9 $(lsof -t -i :8000)
kill -9 $(lsof -t -i :3000)

# Nuclear option — kill all by name
pkill -f uvicorn
pkill -f "next dev"
pkill -f "node"
```

### Rules

- **Zombie process check runs BEFORE log inspection, BEFORE code review, BEFORE anything else**
- If a port conflict error exists anywhere in the logs — even buried — treat it as the root cause until proven otherwise
- After killing zombie processes, do a clean restart and verify the fresh process is actually running
- Never assume a `Ctrl+C` fully cleaned up — always verify with `lsof` or `ps`

### Hard Rule

**Spending time debugging code when `[Errno 98] Address already in use` is visible in the logs is a critical failure.**

The error tells you exactly what's wrong. Read the logs first, check ports second, touch code last.

---

## 6. Autonomous Bug Fixing

When given a bug report, resolve it autonomously.

Expected workflow:

- Identify the failure source
- Inspect logs, errors, and failing tests
- Diagnose root cause
- Implement the correct fix
- Verify the fix works

Rules:

- Do not request hand-holding
- Do not ask the user to debug
- Resolve issues independently

Failing CI tests must be investigated and fixed without waiting for instruction.

---

## 7. Plan First — Mandatory Planning Before Any Implementation

Before writing a single line of code, a written plan must exist in `tasks/todo.md`.

### Plan Structure

Every plan written in `tasks/todo.md` must follow this structure:

```
## Task: [Short Title]

### Goal
One sentence. What does done look like?

### Subtasks
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3
...

### Out of Scope
What is explicitly NOT being done in this task.
```

### Rules

- No implementation begins without a populated `tasks/todo.md`
- Every subtask must be a concrete, actionable checkbox — no vague bullets
- Subtasks must be granular enough that each one can be verified independently
- The plan must be reviewed and confirmed before any code is written
- As work progresses, subtasks are checked off in real time — not retroactively
- If the scope changes mid-task, the plan is updated before continuing

### Hard Rule

**Writing code without an approved plan in `tasks/todo.md` is a critical failure.**

No exceptions. No "I'll add the plan after." Plan first, always.
Also when Safa-human- wants you to generate a plan .md put it into the plans folder

---

## 8. Demand Elegance (Balanced)

Strive for clean, elegant solutions without unnecessary complexity.

For non-trivial changes:

Pause and ask:

> Is there a more elegant solution?

If a fix feels hacky:

> Knowing everything I know now, implement the elegant solution.

Guidelines:

- Avoid over-engineering simple fixes
- Favor minimal, maintainable changes
- Challenge your own work before presenting it

---

## 9. Default Parallelization and Vectorization

Always think parallel and vectorized first. Single-threaded, row-by-row logic is a last resort.

Rules:
- Default to vectorized operations over loops wherever possible
- Parallelize independent workloads — don't run sequentially what can run concurrently
- For data processing and transformation tasks, use **Polars** as the default library unless explicitly told otherwise — it's built for parallelism and vectorization out the box
- Avoid pandas or python objects unless specifically required — it's slower and single-threaded by default
- For numerical compute, prefer NumPy vectorized ops over Python loops
- Profile before assuming something is fast enough — don't guess performance

Hard Rule:
Writing a Python for-loop to process rows in a dataframe when a vectorized or parallel solution exists is a critical failure.


## 10. CI Workflow Check Before Every Push

Before pushing ANY commit to GitHub, check CI workflow status first.

### Steps
- Review existing CI workflow results on the branch
- Ensure no failing checks exist before adding new commits
- If CI is failing, fix it before pushing new work on top
- Never push to a branch with a red CI — it buries the failure

### Hard Rule
Pushing to GitHub while CI is failing is a critical failure.
Fix CI first. Push second. No exceptions.

                                           
## 11. PR Review Check Before Every Merge

Before merging ANY PR to main, check the PR review feedback first — bot reviewers
(`pr_agent`, Copilot) AND any human reviews.

### Steps
- After CI passes, fetch the PR review comments (`gh pr view <n> --json reviews,comments`)
- Read every comment; classify each as: (a) real bug — must fix, (b) clarity/style —
  should fix if cheap, (c) low-value/defensive — skip with documented reason
- If any comment is a real bug (a): fix it, push, re-verify CI green, THEN merge
- If comments are only (b)/(c): fix the cheap ones, skip the rest with a one-line
  reason in the commit message, then merge
- Never merge with an unaddressed (a)-class review finding

### Hard Rule
Merging a PR with an unaddressed real-bug review finding is a critical failure.
The review is the last gate before main — read it, don't rubber-stamp it.

### Notes
- Bot reviewers (the `pr_agent` GitHub Action runs on every PR) catch real bugs —
  PR #37's review found 3 genuine issues (identical if/else branches, atexit cleanup
  deleting preserved dirs, a regex that failed on dash-less tokens). Treat bot reviews
  as substantive, not noise.
- "Real bug" = the code would produce wrong output, crash on a realistic input, or
  contradict its own docstring/comment. Style nits and low-probability defensive
  measures are NOT real bugs.
- When skipping a suggestion, say WHY in the commit message (`Skipped: <reason>`) so
  the next reader knows it was considered, not missed.

                                           
## 12. Anti Hallucination Rules
1. NEVER name a library, model, or function without grep/read confirming it exists first.
2. When asked for deep analysis, the FIRST action must be tool calls, not prose.
3. Every factual claim about the codebase requires a file:line citation.
4. If uncertain, say "I have not verified this" — never assert.

# Task Management

1. **Plan First**  
   Write the implementation plan in `tasks/todo.md` with checkable items.

2. **Verify Plan**  
   Review the plan before implementation begins.

3. **Track Progress**  
   Mark items complete as work progresses.

4. **Explain Changes**  
   Provide a high-level explanation at each step.

5. **Document Results**  
   Add a review section to `tasks/todo.md`.

6. **Capture Lessons**  
   After corrections or mistakes, update `tasks/lessons.md`.

7. **Zero Assumptions**
   Ask questions before implementing if anything is unclear.
