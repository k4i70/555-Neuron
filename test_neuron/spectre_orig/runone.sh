#!/bin/zsh -l
# Spectre version (kept for reference). usage: spectre_orig/runone.sh <sim cdl> <golden cdl> <dir>
# Paths are relative to test_neuron/; uses the Spectre gen_tb.py/analyze.py from this folder.
S=${0:A:h}          # spectre_orig/
B=${S:h}            # test_neuron/
[ $# -eq 3 ] || { echo "usage: $0 <sim cdl> <golden cdl> <dir>" >&2; exit 1; }
module load courses/ece555/asap7-cadence-calibre >/dev/null 2>&1
mkdir -p "$B/$3" && cd "$B/$3" && python3 "$S/gen_tb.py" "$B/$1" 0.7 >/dev/null || exit 1
cadence-run /srv/auto/apps/cadence/SPECTRE251/bin/spectre -64 neuron_tb.sp -format nutbin +aps +log spectre.log >/dev/null 2>&1
cd "$B" && PYTHONPATH="$B" python3 "$S/analyze.py" "$2" "$3" > "$3/report.txt" 2>/dev/null
rm -f "$B/$3/neuron_tb.raw"
echo "$3 done: $(grep -m1 'Functional' "$3/report.txt")"
