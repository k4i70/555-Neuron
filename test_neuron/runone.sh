#!/bin/zsh -l
# usage: runone.sh <sim netlist> <golden cdl> <dir>
#   <sim netlist>: schematic auCdl, or Calibre xACT netlist of NEURON (post-layout,
#                  detected automatically). <golden cdl>: schematic used for the
#                  expected outputs (and, for xACT runs, the driver INV + net names).
#   Relative paths are relative to this script's folder.
B=${0:A:h}          # folder containing this script
[ $# -eq 3 ] || { echo "usage: $0 <sim netlist> <golden cdl> <dir>" >&2; exit 1; }
abs() { [[ $1 = /* ]] && echo $1 || echo $B/$1; }
SIM=$(abs $1) GOLD=$(abs $2) RUN=$(abs $3)
module load synopsys/hspice/2026.03 >/dev/null 2>&1
mkdir -p "$RUN" && cd "$RUN" && python3 "$B/gen_tb.py" "$SIM" 0.7 "$GOLD" || exit 1
hspice -i neuron_tb.sp -o neuron_tb > hspice.out 2>&1   # -> neuron_tb.tr0, neuron_tb.lis
cd "$B" && python3 analyze.py "$GOLD" "$RUN" > "$RUN/report.txt" 2>"$RUN/analyze.err"
[ -n "$KEEP_TR0" ] || rm -f "$RUN/neuron_tb.tr0"
echo "$3 done: $(grep -m1 'Functional' "$RUN/report.txt" || tail -1 "$RUN/analyze.err")"
