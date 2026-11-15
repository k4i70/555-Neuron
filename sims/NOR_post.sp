
* NOR2 Post-Layout Simulation - FO4

* Global nodes
.GLOBAL VSS VDD

* Temperature
.TEMP 25.0

* Simulation options (from sample TB)
.OPTION
+ ARTIST=2
+ INGOLD=2
+ PARHIER=LOCAL
+ PSF=2
+ HIER_DELIM=0

.options accurate=1 NUMDGT=8 measdgt=5 GMINDC=1e-18 DELMAX=1n method=gear INGOLD=2 POST=1

* Include transistor models
.INCLUDE "/srv/auto/apps/asap7pdk/2022-fixed/asap7PDK_r1p7/models/hspice/7nm_TT_160803.pm"

* Include extracted NOR layout
.INCLUDE "NOR.pex.netlist"

* Reference inverter from original AND2_TB
.SUBCKT INV IN OUT
MN0 OUT IN VSS VSS nmos_rvt W=27e-9 L=20e-9 nfin=1
MP1 OUT IN VDD VDD pmos_rvt W=54e-9 L=20e-9 nfin=2
.ENDS INV

* Power supplies
v1 VSS 0 0v
v2 VDD 0 0.9v

* Input A
v3 A 0 PWL(
+ 0ns     0v
+ 1ns     0v
+ 1.025ns 0.9v
+ 2ns     0.9v
+ 2.025ns 0v
+ 3ns     0v
+ 3.025ns 0.9v
+ 4ns     0.9v
+ 4.025ns 0v
+ 5ns     0v
)

* Input B
v4 B 0 PWL(
+ 0ns     0v
+ 2ns     0v
+ 2.025ns 0.9v
+ 4ns     0.9v
+ 4.025ns 0v
+ 5ns     0v
)

* Main AND2 DUT - extracted pin order: VSS VDD B A Y
XNOR VSS VDD B A Y NOR

* Fanout of 4 at AND2 output
XLOAD1 Y L1 INV
XLOAD2 Y L2 INV
XLOAD3 Y L3 INV
XLOAD4 Y L4 INV

* Save input/output waveforms
.PROBE TRAN V(A) V(B) V(Y)

* Transient analysis
.OP
.TRAN STEP=1p STOP=5n



* NOR propagation delay measurements

* Output HIGH to LOW: A rises at 1.025ns
.MEASURE TRAN tHL TRIG V(A) VAL=0.45 RISE=1
+ TARG V(Y) VAL=0.45 FALL=1

* Output LOW to HIGH: B falls at 4.025ns
.MEASURE TRAN tLH TRIG V(B) VAL=0.45 FALL=1
+ TARG V(Y) VAL=0.45 RISE=1

* Output rise time (10% to 90%)
.MEASURE TRAN trise TRIG V(Y) VAL=0.09 RISE=1
+ TARG V(Y) VAL=0.81 RISE=1

* Output fall time (90% to 10%)
.MEASURE TRAN tfall TRIG V(Y) VAL=0.81 FALL=1
+ TARG V(Y) VAL=0.09 FALL=1


* NOR truth table verification

* Truth table sampling
* Output samples
.MEASURE TRAN Y_0 FIND V(Y) AT=0.5n
.MEASURE TRAN Y_1 FIND V(Y) AT=1.5n
.MEASURE TRAN Y_2 FIND V(Y) AT=2.5n
.MEASURE TRAN Y_3 FIND V(Y) AT=3.5n

.END
