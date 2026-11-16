#!/bin/zsh -l
# usage: netlist.sh [out.cdl]   (default: NEURON.cdl in this script's folder)
# Netlists 555-Neuron/NEURON/schematic from Virtuoso to auCdl with the si batch
# netlister, using si.env in this folder, and writes the result to out.cdl.
B=${0:A:h}                  # folder containing this script (<lib>/test_neuron)
OUT=${1:-NEURON.cdl}
[[ $OUT = /* ]] || OUT=$B/$OUT
RUN=$B/.netlist
CDSLIB=${B:h:h}/cds.lib     # cds.lib next to the library folder (defines 555-Neuron)
module load courses/ece555/asap7-cadence-calibre >/dev/null 2>&1
rm -rf "$RUN" && mkdir -p "$RUN" || exit 1
sed "s|^simRunDir = .*|simRunDir = \"$RUN\"|" "$B/si.env" > "$RUN/si.env"
echo "INCLUDE $CDSLIB" > "$RUN/cds.lib"
cd "$RUN" && cadence-run si -batch -command netlist > si.out 2>&1
if ! grep -q 'End netlisting' si.out || [ ! -s NEURON.cdl ]; then
    echo "netlisting failed, see $RUN/si.out" >&2; tail -5 si.out >&2; exit 1
fi
cp NEURON.cdl "$OUT" && echo "wrote $OUT ($(grep -c '^MM' "$OUT") transistors)"
