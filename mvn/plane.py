#! /usr/bin/env python
"""
****************
Plane Base Class
****************
"""
import numpy

import mvn.helpers as helpers
import mvn.decorate as decorate
from mvn.matrix import Matrix 


Plane = decorate.underConstruction('Plane')

@decorate.MultiMethod.sign(Plane)
@decorate.automath.automath
@decorate.automath.right
class Plane(object):
    """
    plane class, meant to (eventually) factor out some code, 
    and utility from the Mvn class
    """
    
    rtol = 1e-5
    """
    relative tolerence
    
    see :py:func:`mvn.helpers.approx`
    """
    
    atol = 1e-8
    """
    absolute tolerence
    
    see :py:func:`mvn.helpers.approx`
    """
    
    
    def __init__(
        self,
        vectors= Matrix.eye,
        mean= numpy.zeros,
    ):
        mean = mean if callable(mean) else numpy.array(mean).flatten()[None, :]
        vectors = vectors if callable(vectors) else Matrix(vectors)

        stack=helpers.autoshape([
            [vectors],
            [mean   ],
        ],default= 1)
        
        #unpack the stack into the object's parameters
        self.vectors = Matrix(numpy.real_if_close(stack[0, 0]))
        self.mean    = Matrix(numpy.real_if_close(stack[1, 0]))

    def __repr__(self):
        """
        print self
        """
        return '\n'.join([
            '%s(' % self.__class__.__name__,
            '    mean=',
           ('        %r,' % self.mean).replace('\n', '\n'+8*' '),
            '    vectors=',
           ('        %r' % self.vectors).replace('\n', '\n'+8*' '),
            ')',
        ])

    __str__ = __repr__
    
    def __getitem__(self, index):
        """
        project the plane into the selected dimensions
        """
        assert not isinstance(index, tuple),'1-dimensional index only'
        
        return type(self)(
            mean= self.mean[:, index],
            vectors= self.vectors[:, index],
        )

    copy = decorate.automath.Automath.__dict__['copy']

    @property
    def shape(self):
        """
        get the shape of the vectors,the first element is the number of 
        vectors, the second is their lengths: the number of dimensions of 
        the space they are embedded in
            
        >>> assert A.vectors.shape == A.shape
        >>> assert (A.vectors.shape[0],A.mean.size)==A.shape
        >>> assert A.shape[0]==A.rank
        >>> assert A.shape[1]==A.ndim
        """
        return self.vectors.shape
            
    @property
    def rank(self):
        """
        get the number of dimensions of the space covered by the mvn
        
        >>> assert A.rank == A.vectors.shape[0]
        """
        return self.vectors.shape[0]

    @property
    def ndim(self):
        """
        get the number of dimensions of the space the mvn exists in
        
        >>> assert A.ndim==A.mean.size==A.mean.shape[1]
        >>> assert A.ndim==A.vectors.shape[1]
        """
        return self.mean.size
            
    @property
    def flat(self):
        """
        >>> assert bool(A.flat) == bool(A.vectors.shape[1] > A.vectors.shape[0]) 
        """
        return max(self.vectors.shape[1] - self.vectors.shape[0], 0)
            
    def __nonzero__(self):
        """
        True if not empty
        
        >>> assert A
        >>> assert bool(A) == bool(A.ndim)
        >>> assert not A[:0]
        """
        return bool(self.ndim)

    @decorate.MultiMethod
    def __add__(self, other):
        """
        add two planes together
        """
        raise TypeError("No Apropriate Method Found")

    @__add__.register(Plane)
    def __add__(self, other):
        result = self.copy()
        result.mean = result.mean+other
        return result

    @__add__.register(Plane, Plane)
    def __add__(self, other):
        return Plane(
            mean = self.mean+other.mean,
            vectors = numpy.vstack([self.vectors, other.vectors])
        )

        
    def approx(self, *args):
        return helpers.approx(*args, atol = self.atol, rtol = self.rtol)


    def __and__(self, other):
        """
        plane intersection
        """
        Nself = self.vectors.null()
        Nother = other.vectors.null()

        #and stack them
        null = numpy.vstack([
            Nself,
            Nother,
        ])

        mean = numpy.hstack([self.mean, other.mean])

        #get length of the component of the means along each null vector
        r = numpy.vstack([Nself*self.mean.H, Nother*other.mean.H])

        
        mean = (numpy.linalg.pinv(null, 1e-6)*r).H

        return type(self)(vectors= null.null(), mean=mean)


if __debug__:
    ndim = helpers.randint(1, 10)
    
    A = Plane(
        mean = numpy.random.randn(1, ndim),
        vectors = numpy.random.randn(helpers.randint(1, ndim), ndim)
    )
    
if __name__ == '__main__':
    pass
