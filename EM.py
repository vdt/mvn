#! /usr/bin/env python

import numpy
from matrix import Matrix
from __init__ import Mvar
from mixture import Mixture

import pylab; pylab.ion()

#source = Mixture(
#    distributions=[
#        Mvar.fromData(Matrix.randn([500,2])*(Matrix.eye(2)+Matrix.randn([2,2]))),
#        Mvar.fromData(Matrix.randn([500,2])*(Matrix.eye(2)+Matrix.randn([2,2]))),    
#    ],
#    weights=[numpy.random.rand(),numpy.random.rand()],
#)
#data = soure.sample(200) 

D1 = Matrix.randn([1000,2])*(Matrix.eye(2)+Matrix.randn([2,2]))
D2 = Matrix.randn([100,2])*(Matrix.eye(2)+Matrix.randn([2,2]))    


M1 = Mvar.fromData(D1)
M2 = Mvar.fromData(D2)

print 'M1=%s' % M1
print 'M2=%s' % M2

data = numpy.vstack([
    D1,
    D2,
])


W1,R1 = [1e7],Mvar(mean=[ 10.0, 10.0],var=numpy.array([20.0,20.0])**2)
W2,R2 = [1e7],Mvar(mean=[-10.0,-10.0],var=numpy.array([20.0,20.0])**2)

old_p = numpy.inf

for N in range(250):

    pi1 = sum(W1)
    pi2 = sum(W2)

    (pi1,pi2) = [
        pi1/(pi1+pi2),
        pi2/(pi1+pi2)
    ]

    d1 = R1.density(data)*pi1
    d2 = R2.density(data)*pi2

    (W1,W2) = [
        d1/(d1+d2),
        d2/(d1+d2),
    ]

    R1 = Mvar.fromData(data = data,weights = W1,bias=True)
    R2 = Mvar.fromData(data = data,weights = W2,bias=True)

    #print 'W1=%s' % sum(W1)
    #print 'W2=%s' % sum(W2)

    pylab.plot(data[:,0],data[:,1],'.r')
    pylab.gca().add_artist(R1.patch())
    pylab.gca().add_artist(R2.patch())
    pylab.draw()
    pylab.gcf().clear()

    p=sum(pi1*W1*pi2*W2)
    print 'p=%s' % p
#    if abs(p-old_p) <0.0000001:
#        break
    old_p = p


