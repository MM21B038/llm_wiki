#!/bin/bash
echo "===== SHORT-TERM CONTEXT ====="
cat /home/butcher/projects/llm_wiki/experiments/memory/short_term/active_context.md
echo ""
echo "===== TODO ====="
cat /home/butcher/projects/llm_wiki/experiments/memory/short_term/todo.md
echo ""
echo "===== RECENT CURRENT STATE ====="
tail -20 /home/butcher/projects/llm_wiki/experiments/memory/short_term/current_state.md
