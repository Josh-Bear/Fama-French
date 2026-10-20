#!/bin/bash
cd "/Users/doyinratnavardhana/Fama French/Fund Style Dashboard" || exit 1
SC=.claude/factor_team/scratch
export PYTHONPATH=.
for s in S003 S005 S006; do
  mkdir -p $SC/factor-analyst_s010_regress_$s
  ./.venv/bin/python .claude/factor_team/runs/$s/run.py --out $SC/factor-analyst_s010_regress_$s > $SC/factor-analyst_s010_regress_$s.out 2>&1
  echo "$s done rc=$?"
done
mkdir -p $SC/factor-analyst_s010_regress_S009
./.venv/bin/python .claude/factor_team/runs/S009/run.py --out $SC/factor-analyst_s010_regress_S009 > $SC/factor-analyst_s010_regress_S009.out 2>&1
echo "S009 done rc=$?"
./.venv/bin/python .claude/factor_team/runs/S009/run_addendum.py --out $SC/factor-analyst_s010_regress_S009 > $SC/factor-analyst_s010_regress_S009_add.out 2>&1
echo "S009add done rc=$?"
echo ALLDONE
