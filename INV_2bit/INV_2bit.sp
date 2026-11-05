.subckt INV in out
mn0 out in vss! vss! nmos_rvt w=27e-9 l=20e-9 nfin=1
mp1 out in vdd! vdd! pmos_rvt w=54e-9 l=20e-9 nfin=2
.ends INV

xi1 in<0> out<0> INV
xi0 in<1> out<1> INV
