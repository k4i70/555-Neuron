** Library name: ECE555
** Cell name: AND2
** View name: schematic
.subckt AND2 a b y vdd vss
xm5 y net1 vdd vdd pmos_rvt w=81e-9 l=20e-9 nfin=3
xm4 net1 a vdd vdd pmos_rvt w=162e-9 l=20e-9 nfin=6
xm3 net1 b vdd vdd pmos_rvt w=162e-9 l=20e-9 nfin=6
xm1 net2 a vss vss nmos_rvt w=108e-9 l=20e-9 nfin=4
xm2 y net1 vss vss nmos_rvt w=54e-9 l=20e-9 nfin=2
xm0 net1 b net2 vss nmos_rvt w=108e-9 l=20e-9 nfin=4
.ends AND2
** End of subcircuit definition.

** Library name: ECE555
** Cell name: INV
** View name: schematic
.subckt INV a vdd vss y
xm0 y a vss vss nmos_rvt w=81e-9 l=20e-9 nfin=3
xm1 y a vdd vdd pmos_rvt w=81e-9 l=20e-9 nfin=3
.ends INV
** End of subcircuit definition.

** Library name: ECE555
** Cell name: AND2_TEST
** View name: schematic
xi0 a b y vdd vss AND2
xi4 y vdd vss net11 INV
xi3 y vdd vss net9 INV
xi2 y vdd vss net7 INV
xi1 y vdd vss net5 INV
