#!/bin/sh
# usage: stats_under_load.sh <profile-label>
# Runs a fixed 60 s workload (c=4) per path and samples docker stats 10x during it.
set -e
P=$1; PY=${PY:-python3}
for kind in orion iota; do
  DUR=60 $PY -c "import asyncio,json,bench; print(json.dumps(asyncio.run(bench.load('$kind',4))))" > load60_${P}_${kind}.json &
  pid=$!; sleep 5
  sh dstats.sh stats_${P}_load_${kind}.csv 10
  wait $pid
done
