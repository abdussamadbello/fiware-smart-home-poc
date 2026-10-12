#!/bin/sh
# usage: dstats.sh <outfile> <samples>  -- repeated docker stats snapshots (no-stream)
out=$1; n=${2:-5}; : > "$out"
for i in $(seq 1 $n); do sudo docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' >> "$out"; sleep 2; done
