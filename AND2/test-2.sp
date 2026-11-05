* Global nodes
.GLOBAL VSS VDD

* Temperature
.TEMP 25.0

* Simulation options
.OPTION
+ 	ARIST=2
+ 	INGOLD=2
+ 	PARHIER=LOCAL
+ 	PSF=2
+ 	HIER_DELIM=0
.options accurate=1 NUMDGT=8 measdgt=5 GMINDC=1e-18 DELMAX=1n method=gear INGOLD=2 POST=1

* Include necessary model files
.INCLUDE "/srv/auto/apps/asap7pdk/2022-fixed/asap7PDK_r1p7/models/hspice/7nm_TT_160803.pm"
.INCLUDE "INV.pex.netlist"
.INCLUDE "AND2.pex.netlist"

* Power supply
v1 VSS 0 0v
v2 VDD 0 0.9v

* Input stimulus for the AND
vina A 0 pwl (0ns 0v 5ns 0v 5.025ns 0v 10ns 0v 10.025ns 0.9v 15ns 0.9v 15.025ns 0.9v 20ns 0.9v 20.025ns 0v 25ns 0v 30ns 0v)
vinb B 0 0.9v

* Instantiate the DUT (main AND)
XAND VSS VDD A B Y AND2 
* Fanout of 4 for the output Y
* First inverter load connected to Y
XLOAD1 VSS VDD Y N1 INV 
* Second inverter load connected to Y 
XLOAD2 VSS VDD Y N2 INV 
* Third inverter load connected to Y 
XLOAD3 VSS VDD Y N3 INV  
* Fourth inverter load connected to Y
XLOAD4 VSS VDD Y N4 INV  

* Output load (optional small capacitance for output node Y)
COUT Y 0 4f

* Transient analysis
.OP
.TRAN STEP=1p STOP=35n

* End the testbench
.END
