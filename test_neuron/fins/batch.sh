#!/bin/zsh -l
# usage: fins/batch.sh <specfile> [parallel]
#   specfile lines:  NAME  sizevar-args...   (e.g.  O32P  --min OAI32:MM4=6,MM3=6,MM0=6)
# Builds fins/NAME.cdl with sizevar.py from ../NEURON.cdl and simulates each in fins/run_NAME.
F=${0:A:h}; B=${F:h}
P=${2:-12}
grep -v '^\s*#' "$1" | grep -v '^\s*$' | while read -r name args; do
    python3 "$B/sizevar.py" "$B/NEURON.cdl" "$F/$name.cdl" ${=args} || exit 1
    echo "$name"
done | xargs -P "$P" -I{} "$B/runone.sh" fins/{}.cdl fins/{}.cdl fins/run_{}
