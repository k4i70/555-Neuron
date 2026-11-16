#!/bin/zsh -l
# usage: runone.sh <sim cdl> <golden cdl> <dir>   (paths relative to this script's folder)
B=${0:A:h}          # folder containing this script
[ $# -eq 3 ] || { echo "usage: $0 <sim cdl> <golden cdl> <dir>" >&2; exit 1; }
module load synopsys/hspice/2026.03 >/dev/null 2>&1
mkdir -p "$B/$3" && cd "$B/$3" && python3 "$B/gen_tb.py" "$B/$1" 0.7 >/dev/null || exit 1
hspice -i neuron_tb.sp -o neuron_tb > hspice.out 2>&1   # -> neuron_tb.tr0, neuron_tb.lis
cd "$B" && python3 analyze.py "$2" "$3" > "$3/report.txt" 2>/dev/null
[ -n "$KEEP_TR0" ] || rm -f "$B/$3/neuron_tb.tr0"
echo "$3 done: $(grep -m1 'Functional' "$3/report.txt")"
