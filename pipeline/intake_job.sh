#!/usr/bin/env bash
# Process one submitted result and store it on its data branch, safely when
# several results arrive at once.
#
#     pipeline/intake_job.sh map|distill
#
# Run from the main checkout, with the data branch checked out in ./store and
# the issue in $INTAKE_EVENT (or the workflow's own event). Runs do not wait
# for each other (GitHub keeps only one run waiting per concurrency group and
# cancels the rest, which would drop results in a burst). Instead each run,
# on every attempt, starts again from the branch as it is now, checks the
# result against it, and pushes; if another run pushed first, it tries again.
# The reply for the issue is left in verdict.json. A rejected result is
# stored too, as its reason in rejected/<issue>.json, so the site can show
# what goes wrong. stored=false in it means the result could not be pushed, and the issue is left
# open for the sweeper to try again. With INTAKE_NO_PUSH set (CI's
# rehearsal), everything happens but the push.

set -u
kind="$1"
branch="${kind}-2025"
[ "$kind" = "distill" ] && export DISTILL_DIR=store || export MAP_DIR=store

stored=false
for attempt in 1 2 3 4 5 6; do
  git -C store fetch -q origin "$branch" && git -C store reset -q --hard FETCH_HEAD && git -C store clean -qfd
  python pipeline/intake.py | tail -n 1 > verdict.json
  if [ "$kind" = "distill" ]; then
    python pipeline/combine.py store > /dev/null
    python pipeline/known_twins.py result store > /dev/null
  fi
  if [ -z "$(git -C store status --porcelain)" ]; then
    stored=true                       # nothing to store: the result was already stored, or the unit complete
    break
  fi
  git -C store add -A
  git -C store -c user.name="github-actions[bot]" \
      -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
      commit -q -m "Record a ${kind} result from issue #$(python -c "import json, os; print(json.load(open(os.environ.get('INTAKE_EVENT') or os.environ['GITHUB_EVENT_PATH']))['issue']['number'])")"
  if [ -n "${INTAKE_NO_PUSH:-}" ] || git -C store push -q origin "HEAD:$branch"; then
    stored=true
    break
  fi
  echo "push $attempt lost a race; trying again from the branch as it is now"
  sleep $(( (RANDOM % 20) + 5 ))
done

python - "$stored" <<'PY'
import json, sys
v = json.load(open("verdict.json"))
v["stored"] = sys.argv[1] == "true"
if not v["stored"]:
    v["reply"] += " It could not be stored just now; it will be tried again automatically."
json.dump(v, open("verdict.json", "w"))
print(v["reply"])
PY
