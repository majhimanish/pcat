#!/bin/bash
# usage: agent.sh <name> <request>
D=<dogfood>
export PATH=$D/venv/bin:$PATH
unset CLAUDE_ADDITIONAL_DIRECTORIES CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD
rm -rf $D/run_$1 && cp -r $D/healthchecks $D/run_$1 && cd $D/run_$1
timeout 600 claude -p "$2" --output-format stream-json --verbose --no-session-persistence \
  --model claude-sonnet-5-5 --setting-sources project,local --disable-slash-commands \
  --allowedTools Read Edit MultiEdit Write Glob Grep LS TodoWrite "Bash(git status:*)" "Bash(git diff:*)" \
    "Bash(git log:*)" "Bash(git grep:*)" "Bash(ls:*)" "Bash(head:*)" "Bash(wc:*)" \
    mcp__pcat__search_patterns mcp__pcat__get_pattern mcp__pcat__check_code \
  --disallowedTools WebFetch WebSearch Agent Task NotebookEdit > $D/$1.transcript.jsonl 2> $D/$1.stderr
echo "exit $?" >> $D/$1.stderr
git add -A && git diff --cached > $D/$1.diff
