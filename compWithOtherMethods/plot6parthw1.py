#!/usr/bin/python
from numpy import *
from pylab import *
from matplotlib import rc, rcParams
import matplotlib.units as units
import matplotlib.ticker as ticker
import sys
import os


rc('text',usetex=True)
rc('font',**{'family':'serif','serif':['Six electron quantum dot']})

dataSRG = loadtxt("6part10/SRG6part.dat")
dataFCI = loadtxt("6part10/FCI6part.dat")
dataCCSD = loadtxt("6part10/CCSD6part.dat")

l = len(dataSRG[:,0])
data7 = zeros(l)
# DMC results
data7[:] = 20.1532

axis([4,20,20.05, 21])
xlabel(r'$R$',fontsize=20)
ylabel(r'$E_0\, [E_h^*]$',fontsize=20)
plot(dataSRG[:,0], dataSRG[:,2],'b-*', dataSRG[:,0], dataSRG[:,1],'r:.', 
dataFCI[:,0], dataFCI[:,1],'g--x', dataCCSD[:,0], dataCCSD[:,1], 'm:v',dataSRG[:,0], data7[:], 'k--',markersize=7)

#title(r'$N=6,\;\omega=1.0$', fontsize=20, horizontalalignment='center')
legend(('SRG','HF','FCI','CCSD','DMC'),
           'upper right', shadow=False, fancybox=False,prop={"size":18})
legend(loc='upper right')

xticks( [4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20])
# Save the figure in a separate file
savefig('6parthw1.pdf', format='pdf')
# Draw the plot to screen
show()
    
