## Task: Tab-Specific Chat Context & Workspace Shell Subtabs

### Goal
Connect the AI chatbot to authentic SUT rule database metrics on `rule-database` and isolate chat histories per active tab, plus render dedicated Lucide icons on all subtabs in WorkspaceTabStrip.

### Subtasks
- [x] Phase 0: IDE-style workspace shell merged in PR #68
- [x] Frontend: Add Lucide icons to all subtabs across Reference Tools, Compliance, and Rule Database
- [x] Frontend: Dynamically resolve active subtab icons and titles in WorkspaceTabStrip with breadcrumb tooltips
- [x] Backend: Add tab-aware data fetching and `build_rule_database_context` for Rule Database tab
- [x] Backend/Frontend: Scope workspace chat sessions per active tab (`bilun:workspace:${activeTab}`) to isolate chat histories
- [x] Clean up all non-Bilun scratch/emulation files from repository root
- [x] Rebase/merge with origin/main and resolve conflicts

### Review
- PR #69 opened with all changes cleanly integrated on top of main.
- All backend (2502) and frontend (229) tests pass 100%.
