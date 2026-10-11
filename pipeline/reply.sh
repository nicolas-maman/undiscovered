#!/usr/bin/env bash
# Answer a result's issue from verdict.json (written by pipeline/intake_job.sh).
#
#     pipeline/reply.sh <issue number>
#
# Accepted and stored: reply, label work-result, close. Not accepted: reply,
# label invalid, close. Accepted but not stored (every push lost a race):
# reply and leave the issue open and unlabelled, so the sweeper tries again.

set -eu
number="$1"
python -c "import json; open('reply.txt', 'w').write(json.load(open('verdict.json'))['reply'])"
gh issue comment "$number" --body-file reply.txt
outcome=$(python -c "import json; v = json.load(open('verdict.json')); print('retry' if v['accepted'] and not v.get('stored', True) else ('work-result' if v['accepted'] else 'invalid'))")
if [ "$outcome" != "retry" ]; then
  gh issue edit "$number" --add-label "$outcome"
  gh issue close "$number"
fi
