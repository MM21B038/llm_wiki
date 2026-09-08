# Memory System

## Structure
- `/home/butcher/projects/llm_wiki/experiments/memory/short_term/` — Current session context, active task state
- `/home/butcher/projects/llm_wiki/experiments/memory/long_term/` — Persistent knowledge, skills, project understanding

## How to use
- Before any task: read `short_term/active_context.md` and `long_term/project_knowledge.md`
- After each step: update `short_term/current_state.md` with what happened
- At session end or milestone: consolidate into `long_term/`

## Files

### Short-term (this session)
- `active_context.md` — Current objective, last action, next steps
- `current_state.md` — Step-by-step log of what was done
- `todo.md` — Remaining tasks, blockers

### Long-term (across sessions)
- `project_knowledge.md` — Project structure, tools, design decisions
- `user_preferences.md` — How the user likes things done
- `lessons_learned.md` — Mistakes, patterns, useful commands
- `tasks_history.md` — Summary of completed tasks
