#! /usr/bin/env python

##imports
#internals
from __future__ import division

#builtins
import itertools
from itertools import izip as zip
import collections 

import operator

#3rd party
import numpy

try:
    from matplotlib.patches import Ellipse
except ImportError:
    def Ellipse(*args,**kwargs):
        """
        Unable to find matplotlib.patches.Ellipse
        """
        raise ImportError(
            "Ellipse is required, from matplotlib.patches, to get a patch"
        )

#local
from helpers import autostack,diagstack,astype,paralell,close,dot,rotation2d


class Mvar(object):
    """
    Multivariate normal distributions packaged to act like a vector.
        (it's an extension of the vectors)
    
    This is done with kalman filtering in mind, but is good for anything where 
        you need to track linked uncertianties across multiple variables.

    basic math operators (+,-,*,/,**,&) have been overloaded to work 'normally'
    for kalman filtering and common sense. But there are *a lot* of surprising 
    features in the math these things produce, so watchout.
    
    since the operations are defined for kalman filtering, the entire process 
    becomes:
        
        state[t+1] = (state[t]*STM + noise) & measurment
        
        state is a list of mvars (indexed by time), noise and measurment are 
        Mvars, (noise having a zero mean) and 'STM' is the state transition 
        matrix
        
    
    A nice side effect of this is that sensor fusion is just:
    
        result = measurment1 & measurrment2 & measurment3
       
        or
        
        result = paralell(*measurments)
        
    normally (at least in what I read on wikipedia) these things are handled 
    with mean and covariance, but I find mean,scale,rotation to be more useful, 
    so that is how the data is actually managed, but other useful info in 
    accessable through virtual attributes (properties).
    
    This system make compression (think principal component analysis) much 
    easier and more useful, but until I can think of a way to get directly 
    from data to the eigenvectors of the covariance matrix of the data, without 
    calculating the covariance, it is of limited utility).
    
    actual attributes:
        mean
            mean of the distribution
        scale
            the eigenvalue asociated with each eigenvector,as a diagonal matrix
        rotation
            unit eigenvectors, as rows
    virtual attributes:    
        vectors
            vectors eigenvectors, as rows
        cov
            covariance matrix
        affine
            autostack([
                [self.vectors,numpy.zeros],
                [self.mean   ,          1],
            ])
            
        
    the from* functions all create new instances from varous 
    common constructs.
        
    the get* functions all grab useful things out of the structure, 
    all have equivalent properties linked to them
    
    the do* functions all modify the structure inplace
    
    the inplace operators (like +=) work but, unlike in many classes, 
    do not currently speed up any operations.
    
    the mean of the distribution is stored as a row vector, so make sure align 
    your transforms apropriately and have the Mvar on left the when attempting 
    to do a matrix multiplies on it. This is for two reasons: 

        1) inplace operators work nicely (Mvar on the left)
        
        2) The Mvar is (currently) the only object that knows how to do 
        operations on itself, might as well go straight to it instead of 
        passing around 'NotImplemented's 
        
    No work has been done to make things fast, because until they work at all
    and speed actually is a problem it's not worth working on. 
    """
    
    ############## Creation
    def __init__(self,
        stack,
        do_square=True,
        do_compress=True,
        **kwargs
    ):
        """
        create the Mvar from the stack of attributes
        
        stack= autostack([
                [numpy.ones,vectors],
                [         1,   mean],
            ])
        
        stack= autostack([
                [scale,rotation],
                [    1,    mean],
            ])
        
        do_square 
            calls self.do_square() on the result if true. To set the rotation 
            to orthogonal and unit length, do_square automatically calls 
            do_compress, 
            
        do_compress
            calls self.do_compress() on the result if true. To clear out any 
            low valued vectors uses the same defaults as numpy.allclose()
        """
        #unpack the stack into the object's parameters 
        
        self.mean = stack[-1,1:]
        self.scale = numpy.diagflat(stack[:-1,0])
        self.rotation = stack[:-1,1:]
        
        assert not do_square or do_compress,"do_square calls do_compress"
        
        if do_square:
            self.do_square()
        elif do_compress:
            self.do_compress()
    
    def do_square(self,**kwargs):
        """
        this is NOT x**2 it is to set the vectors to perpendicular and unit 
        length
        
        **kwargs is just passed on to do_compress
        """
        #to decouple compress from square you'll need do the square on the 
        #Mvar's brane instead of the full-space, to do that you'll need
        #something like theplane class I've started developing in the adjacent file
        V=self.rotation
        S=self.scale
        if not numpy.allclose(dot(V,V.T),numpy.eye(V.shape[0]),**kwargs):
            (scale,rotation) = numpy.linalg.eigh(dot(V.T,S,S,V))
            sign=numpy.diag(numpy.sign(scale))
            self.rotation=dot(sign,rotation)
            self.scale=numpy.diag(numpy.abs(scale)**(0.5))
            
        self.do_compress(**kwargs)
        
    def do_compress(self,rtol=1e-5,atol=1e-8):
        """
        drop any vector/scale pairs which are under the tolerence limits
        the defaults match numpy's for 'allclose'
        """
        #convert the scale to a column vector
        diag=numpy.diag(self.scale)[:,numpy.newaxis]
        #get the rotation
        rotation=numpy.array(self.rotation)
        
        stack=numpy.hstack([diag,rotation])
        
        stack=stack[numpy.argsort(diag.flatten()),:]
        
        C=~numpy.array(close(stack[:,0],rtol=rtol,atol=atol)).squeeze()
        #drop the scale/rotation where the scale is close to zero
        stack=stack[C,:]
        #unstack them
        self.scale = numpy.diag(stack[:,0])
        self.rotation=stack[:,1:] 
        
    ############## alternate creation methods
    @staticmethod
    def from_attr(
        mean = numpy.zeros,
        vectors = numpy.zeros, 
        scale = numpy.ones,
        **kwargs
    ):
        """
        create the Mvar from available arrtibutes, rotation isn't listed 
        becaues 'vectors' does everything rotation would 
        
        mean
            defaults to numpy.zeros
            
        vectors
            defaults to numpy.zeros. again row vectors. They do not need to be 
            orthogonal, or unit length.
            
        scale
            defaults to numpy.ones
            
        """
        if not callable(scale):
            scale=numpy.array(scale)
            if isdiag(scale):
                scale=scale.diagonal()
            scale=scale.squeeze()
            assert scale.ndim==1,"scales must be flat or diagonal"
            scale=scale[:,numpy.newaxis]
        
        if not callable(mean):
            mean=numpy.array(mean).squeeze()[numpy.newaxis,:]
            
        #use autostack to determine unknown sizes
        return Mvar(
            autostack([
                [scale,vectors],
                [  1.0,   mean],
            ])
        )
    
    @staticmethod
    def from_cov(cov,**kwargs):
        """
        everything in kwargs is passed directly to the constructor
        don't bother to set 'do_square' to true, they will automatically 
        be orthogonal when pulled out of the covariance
        """
        #get the scale and rotation matracies
        scale,rotation = numpy.linalg.eigh(cov)
        
        return Mvar.from_attr(
            vectors=rotation,
            #square root the scales
            scale=scale**0.5,
            **kwargs
        )
    
    @staticmethod
    def from_data(data, bias=0, rowvar=0, **kwargs):
        """
        iterating on the data should produce vectors.
        the date can be an Mvar.
        assert Mvar.from_data(A)==A
        
        bias and row var are passed to numpy's cov function.
        
        the kwargs are just passed on the basic constructor.
        
        create an Mvar with the same mean and covariance as the supplied data
        with each row being a sample and each column being a dimenson
        
        remember numpy's default covariance calculation divides by (n-1) not 
        (n) set bias = 1 to use N,
        
        my default for rowvar is the opposite of numpy's
        """
        #if variables are along rows, switch to colums
        if rowvar:
            data=data.T
            
        #convert the data to a matrix 
        data=numpy.matrix(data)
        #create the mvar from the mean and covariance of the data
        return Mvar.from_cov(
            cov = numpy.cov(data,bias=bias,rowvar=0),
            mean= numpy.mean(data,axis=0),
            **kwargs
        )
        
    def from_affine(affine,**kwargs):
        """
        unpack an affine transform, into an Mvar.
        the transform should be in the format below:
        
        autostack([
            [self.vectors,numpy.zeros]
            [self.mean   ,        1.0]
        ])
        """
        return Mvar(
            autostack([[numpy.ones,affine[:,:-1]]])
            **kwargs
        )

     ############ get methods/properties

    def get_cov(self):
        """
        get the covariance matrix used by the object
        
        >>> assert A.cov == dot(A.vectors.T,A.vectors) 
        >>> assert A.cov == dot(A.rotation.T,A.scale,A.scale,A.rotation)
        """
        vectors=self.vectors
        return dot(vectors.T,vectors)
    
    def get_vectors(self):
        """
        get the matrix of scaled eigenvectors (as rows)

        >>> assert A.vectors = dot(A.scale,A.rotation) 
        """
        return dot(self.scale,self.rotation)
    
    def get_affine(self):
        return  autostack([
            [self.vectors,numpy.zeros],
            [self.mean   ,          1],
        ])

    cov = property(
        fget=get_cov, 
        fset=lambda self,cov:self.copy(
            Mvar.from_cov(
                mean=self.mean,
                cov=cov,
    )))
    
    vectors = property(
        fget=get_vectors, 
        fset=lambda self,vectors:self.copy(
            Mvar.from_attr(
                mean=self.mean,
                vectors=vectors,
    )))
    
    affine = property(
        fget=get_affine,
        fset=lambda self,affine:self.copy(
            Mvar.from_affine(
                affine,
    )))
    
    ########## Utilities
    def copy(self,other=None):
        """
        either return a copy of an Mvar, or copy another into the self
        B=A.copy()
        A.copy(B)
        """ 
        if other is None:
            return Mvar.from_attr(
                mean=self.mean,
                rotation=self.rotation,
                scale=self.scale
            )
        else:
            self.__dict__=other.__dict__.copy()
        
    @staticmethod
    def stack(*mvars,**kwargs):
        """
        it's a static method to make it clear that it's not happening in place
        Stack two Mvars together, equivalent to hstacking the rotation, and 
        diagstacking the covariance matrixes
        
        yes it works but be careful. Don't use this for reconnecting 
        something you calculated from an Mvar, back to the same Mvar it was 
        calculated from, you'll loose all the cross corelations. 
        If you're trying to do that use a better matrix multiply. 
        """
        #no 'refresh' is necessary here because the rotation matrixes are in 
        #entierly different dimensions
        return Mvar.from_attr(
            #stack the means horizontally
            mean=numpy.hstack([mvar.mean for mvar in mvars]),
            #stack the vector packets diagonally
            rotation=diagstack([mvar.rotation for mvar in mvars]),
            scale=numpy.hstack([numpy.matrix(mvar.scale) for scale in mvars]),
            **kwargs
        )
    
    def sample(self,n=1):
        """
        take samples from the distribution
        n is the number of samples, the default is 1
        each sample is a numpy matrix row vector.
        
        the samles will have the same mean and cov as the distribution 
        being sampled
        """
        data=numpy.hstack([
            numpy.random.randn(n,self.mean.size),
            numpy.ones([n,1]),
        ])
        
        transform=numpy.vstack([
            self.vectors,
            self.mean,
        ])

        return dot(data,transform)
    
    ############ Math

    #### logical operations
    def __eq__(self,other):
        """
        A==?
        compares the means and covariances or the distributions
        """
        return (self.mean==other.mean).all() and (self.cov == other.cov).all()
        
    def blend(*mvars):
        """
        A & ?
        
        This is awsome.
        
        optimally blend together any number of mvars, this is done in and 
        because the elipses look like ven-diagrams
        
        And just choosing an apropriate inversion operator (1/A) allows us to 
        define kalman blending as a standard 'paralell' operation, like with 
        resistors. operator overloading takes care of the rest.
        
        The inversion automatically leads to power, multiply, and divide  
        
        When called as a method 'self' is part of *mvars 
        
        This blending function is not restricted to two inputs like the basic
        (wikipedia) version. Any number works.
        
        and it brings the symetry to the front. 
        
        >>> assert A & B == B & A 
        >>> assert A & B == 1/(1/A+1/B)
        >>> assert A & B & C == Paralell(B,C,A)
        >>> assert A & B & C == Mvar.blend(B,A,C)== Mvar.__and__(C,B,A)
        
        the proof that this is identical to the wikipedia definition of blend 
        is a little too involved to write here. Just try it (see the "wiki 
"        function)
        
        >>> assert A & B == wiki(A,B)
        """
        return paralell(mvars)
        
    __and__ = blend
    
    def __iand__(self,other):
        """
        A&=?
        """
        self.copy(paralell([self,other]))

    ## operators
    def __pow__(self,power):
        """
        A**?
        
        This definition was developed to turn kalman blending into a standard 
        resistor-style 'paralell' operation
        
        The main idea is that only the scale matrix (eigenvalues) gets powered.
        (which is normal for diagonalizable matrixes), stretching the sheet at 
        an independant rate along each (perpendicular) eigenvector
        
        Because the scale matrix is a diagonal, powers on it are easy, 
        so this is not restricted to integer powers
        
        But the mean is also affected by the stretching. It's as if the usual 
        value of the mean is a "zero power mean" transformed by whatever is 
        the current value of the A.rotation.T*A.vectors matrix and if you change that 
        the mean changes with it..
        
        Most things you expect to work just work.
        
            >>> assert A**0== A**(-1)*A== A*A**(-1)== A/A        
            >>> assert (A**K1)*(A**K2)=A**(K1+K2)
            >>> assert A**K1/A**K2=A**(K1-K2)
        
        Zero power has some interesting properties: 
            
            The resulting ellipse is always a unit sphere, with the orientation 
            unchanged, but the mean is wherever it gets stretched to while we 
            transform the ellipse to a sphere
              
            >>> assert (A**0).scale == eye(A.mean.shape[1])
            >>> assert (A**0).rotation== A.rotation
            >>> assert (A**0).mean == dot(
                A.mean,A.rotation.T,A.scale**-1,A.rotation
            )
            
        derivation of multiplication:
        
            >>> assert A.vectors== A.scale*A.rotation
            >>> assert (A**K).vectors== (A.scale**K)*A.rotation
            >>> assert (A**K).vectors== A.vectors* A.rotation.T*A.scale**(K-1)*A.rotation
            >>> assert (A**K).mean== A.mean* A.rotation.T*A.scale**(K-1)*A.rotation
            
            that's a matrix multiply.
            
            So all Mvars on the right,in a multiply, can just be converted to 
            matrix:
            
            >>> assert A*B==A*(B.rotation.T*B.scale*B.rotation)
        """
        rotation = self.rotation
        new_scale = numpy.diag(self.scale.diagonal()**(power-1))
        
        transform = dot(rotation.T,new_scale,rotation)
        
        return self*transform
    
    def __ipow__(self,power):
        """
        A**=?
        """
        self.copy(self**power)
        
    def __mul__(
        self,
        other,
        #this function is applied to the right operand, to simplify the types 
        #of the objects we have to deal with, and to convert any Mvars on 
        #the left into a rotation.T*scale*rotation matrix.
        rconvert=lambda 
            item,
            helper=lambda item:(
                numpy.matrix(item) 
                if item.ndim else
                item
            )
        :(  
            numpy.matrix(dot(item.rotation.T,item.scale,item.rotation)) if 
            isinstance(item,Mvar) else 
            helper(numpy.array(item))
        ),
        #this dict is used to dispatch multiplications based on the type of 
        #the right operand, after it has been passed through rconvert
        multipliers={
            (numpy.matrix):(
                lambda self,matrix:Mvar.from_attr(
                    mean=dot(self.mean,matrix),
                    vectors=dot(self.rotation,matrix),
                    scale=self.scale,
                )
            ),
            (numpy.ndarray):(
                lambda self,constant:Mvar.from_cov(
                    mean= self.mean*constant,
                    cov = self.cov*constant,
                )
            )
        }    
    ):
        """
        A*?
        
        coercion notes:
            All non Mvar imputs will be converted to numpy arrays, then 
            treated as constants if zero dimensional, or matrixes otherwise 
            
            Mvar always beats constant. Between Mvar and numpy.matrix the left 
            operand wins 
            
            >>> assert isinstance(A*B,Mvar)
            >>> assert isinstance(A*M,Mvar)
            >>> assert isinstance(M*A,numpy.Matrix) 
            >>> assert isinstance(A*K,Mvar)
            >>> assert isinstance(K*A,Mvar)
            
            whenever an mvar is found on the right it is converted to a 
            rotation.T*scale*rotation matrix and the multiplication is 
            re-called.
            
        general properties:
            
            constants still commute            
            >>> assert K*A*M == A*K*M == A*M*K
            
            but the asociative property is lost if you mix constants and 
            matrixes (but I think it's ok if you only have 1 of the two types?)
            
            >>> assert (A*2)*M == A*(4*M)
            
            ????
            asociative if only mvars and matrixes?
            ????
            still distributive?
            
        Mvar*Mvar
            multiplying two Mvars together is defined to fit with power
            
            >>> assert A*A==A**2
            >>> assert (A*B).affine=A.affine*B.rotation.T*B.vectors
            >>> assert (A*B).vectors == A.vectors*B.rotation.T*B.scale*B.rotation
            >>> assert (A*B).mean == A.mean*B.rotation.T*B.scale*B.rotation
            >>> assert A*B == A*numpy.linalg.matrix_power(B.cov,0.5)
            
            Note that the result does not depend on the mean of the 
            second mvar(!) (really any mvar after the leftmost mvar or matrix)

        Mvar*constant == constant*Mvar
            Matrix multiplication and scalar multiplication behave differently 
            from eachother.  
            
            For this to be a properly defined vector space scalar 
            multiplication must fit with addition, and addition here is 
            defined so it can be used in the kalman noise addition step so: 
            
            >>> assert ((A+A).vectors == (2*A).vectors).all()
            >>> assert ((A+A) == sqrt(2)*A.vectors).all()
            >>> assert ((A+A).mean == (2*A).mean).all()
            >>> assert ((A+A).mean == 2*A.mean).all()
            
            >>> assert ((A*K).vectors == sqrt(K)*A.vectors).all()
            >>> assert ((A*K).mean == K*A.mean).all()
            
            >>> assert sum(itertools.repeat(A,K-1),A) == A*(K) == (K)*A 
            
            >>> assert ((A*K).cov == A.cov*K).all()
            
            be careful with negative constants because you will end up with 
            imaginary numbers in you vectors matrix, (and lime in your coconut) as 
            a direct result of:            
            
            assert ((A*K).vectors == sqrt(K)*A.vectors).all()
            assert B+(-A) == B+(-1)*A == B-A and (B-A)+A==B
            
            if you want to scale the distribution linearily with the mean
            then use matrix multiplication
        
        Mvar*matrix
        
            matrix multiplication transforms the mean and ellipse of the 
            distribution. Defined this way to work with the kalman state 
            update step.
            
            simple scale is like this
            >>> assert ((A(*eye*K)).vectors == A.vectors*K).all()
            >>> assert ((A(*eye*K)).mean == A.mean*K).all()
            
            or more generally
            >>> assert (A*M).cov == M.T*A.cov*M
            >>> assert (A*M).mean == A.mean*M
            
            matrix multiplication is implemented as follows
            
            assert A*M == Mvar.from_affine(A.affine*diagstack([M,1]))
            
            the refresh() here is necessary to ensure that the rotation matrix
            stored in the object stays well behaved. 
        """
        other=rconvert(other)
        print other
        return multipliers[type(other)](self,other) 
    
    def __rmul__(
        self,
        other,
        #here we convert the left operand to a numpy.ndarray if it is a scalar,
        #otherwise we convert it to a numpy.matrix.
        #the self (right operand) will stay an Mvar for scalar multiplication
        #or be converted to a rotation.T*scale*rotation matrix for matrix 
        #multiplication
        convert=lambda
            other,
            self,
            helper=lambda other,self: (
                numpy.matrix(other) if 
                other.ndim else
                other
                ,
                numpy.matrix(dot(item.rotation.T,item.scale,item.rotation)) if 
                other.ndim else
                self
            )
        :helper(numpy.array(other),self)
        ,
        #dispatch the multiplication based on the type of the left operand
        multipliers={
            #if the left operand is a matrix, the mvar has been converted to
            #to a matrix -> use matrix multiply
            (numpy.matrix):dot,
            #if the left operand is a constant use scalar multiply
            (numpy.ndarray):(
                lambda constant,self:Mvar.from_cov(
                    mean= self.mean*constant,
                    cov = self.cov*constant,
                )
            )
        }
    ):
        """
        ?*A
        
        multiplication order:
            doesn't matter for constants
        
            >>> assert k*A == A*k
        
            but it matters a lot for Matrix/Mvar multiplication
        
            >>> assert isinstance(A*M,Mvar)
            >>> assert isinstance(M*A,numpy.matrix)
        
        be careful with right multiplying:
            Because power must fit with multiplication
        
            it was designed to satisfy
            assert A*A==A**2
        
            The most obvious way to treat right multiplication by a matrix is 
            to do exactly the same thing we're dong in Mvar*Mvar, which is 
            convert the right Mvar to the square root of its covariance matrix
            and continue normally,this yields a matrix, not an Mvar.
            
            this conversion is not applied when multiplied by a constant.
        
        Mvar*Mvar
            multiplying two Mvars together fits with the definition of power
            
            assert prod(itertools.repeat(A,N)) == A**N
            assert A*B == A*(B.rotation.T*B.vectors) 
            
            the second Mvar is automatically converted to a matrix, and the 
            result is handled by matrix multiply
            
            again note that the result does not depend on the mean of the 
            second mvar(!)
        
        martix*Mvar
            assert T*A == T*(A.rotation.T*A.scale*A.rotation)

        Mvar*constant==constant*Mvar
            assert A*k == k*A
        """
        (other,self)= convert(other,self)
        return multipliers[type(other)](other,self)
    
    def __imul__(self,other):
        """
        A*=?
        
        This is why I have things set up for left multply, it's 
        so that __imul__ works.
        """
        self.affine=multiply(self,other).affine
    
    def __div__(self,other):
        """
        A/?
        
        see __mul__ and __pow__
        it would be immoral to overload power and multiply but not divide 
        >>> assert A/B == A*(B**(-1))
        >>> assert A/M == A*(M**(-1))
        >>> assert A/K == A*(K**(-1))
        """
        return multiply(self,other**(-1))
        
    def __rdiv__(self,other):
        """
        ?/A
        
        see __rmul__ and __pow__
        >>> assert K/A == K*(A**(-1))
        >>> assert M/A == M*(A**(-1))
        """
        return multiply(other,self**(-1))
        
    def __idiv__(self,other):
        """
        A/=?
        
        see __mul__ and __pow__
        >>self.affine=(self*other**(-1)).affine
        """
        self.affine=multiply(self,other**(-1))
        
    def __add__(self,other):
        """
        A+?
        
        When using addition keep in mind that rand()+rand() is not like scaling 
        one random number by 2, it adds together two random numbers.

        The add here is like rand()+rand()
        
        Addition is defined this way so it can be used directly in the kalman 
        noise addition step
        
        so if you want simple scale use matrix multiplication like rand()*(2*eye)
        
        scalar multiplication however fits with addition:
        
        >>> assert (A+A).vectors == (2*A).vectors == sqrt(2)*A.vectors
        >>> assert (A+A).mean == (2*A).mean == 2*A.mean

        >>> assert (A+B).mean== A.mean+B.mean
        >>> assert (A+B).cov == A.cov+B.cov

        it also works with __neg__, __sub__, and scalar multiplication.
        
        assert B+(-A) == B+(-1)*A == B-A and (B-A)+A=B
        
        but watchout you'll end up with complex eigenvalues in your vectors 
        matrix's
        """
        return Mvar.from_cov(
            mean= (self.mean+other.mean),
            cov = (self.cov + other.cov),
        )

    def __radd__(self,other):
        """
        ?+A
        """
        self.copy(self+other)

    def __iadd__(self,other):
        """
        A+=?
        """
        self.affine = (self+other).affine

    def __sub__(self,other):
        """
        A-?
        
        watch out subtraction is the inverse of addition 
         
            assert (A-B)+B == A
            assert (A-B).mean ==A.mean- B.mean
            assert (A-B).cov ==A.cov - B.cov
            
        if you want something that acts like rand()-rand() use:
            
            assert (A+B*(-1*eye)).mean == A.mean - B.mean
            assert (A+B*(-1*eye)).cov == A.cov + B.cov

        __sub__ also fits with __neg__, __add__, and scalar multiplication.
        
        assert B+(-A) == B+(-1)*A == B-A and (B-A)+A==B
        """
        try:
            return Mvar.from_cov(
                mean= (self.mean-other.mean),
                cov = (self.cov - other.cov),
            )
        except AttributeError:
            return NotImplemented

    def __rsub__(self,other):
        """
        ?-A
        """
        return self+other
    
    def __isub__(self, other):
        """
        A-=?
        """
        self.copy(self-other)

    def __neg__(self):
        """
        (-A)
        
        it would be silly to overload __sub__ without overloading __neg__
        
        assert B+(-A) == B+(-1)*A == B-A and (B-A)+A==B
        """
        return (-1)*self
    
    ################# Non-Math python internals
    def __repr__(self):
        return '\n'.join([
            'Mvar.from_attr(',
            '    mean=',8*' '+self.mean.__repr__().replace('\n','\n'+8*' ')+',',
            '    scale=',8*' '+self.scale.__repr__().replace('\n','\n'+8*' ')+',',
            '    vectors=',8*' '+self.rotation.__repr__().replace('\n','\n'+8*' ')+',',
            ')',
        ])
    
    __str__=__repr__

    ################ Art
    def get_patch(self,nstd=3,**kwargs):
        """
            get a matplotlib Ellipse patch representing the Mvar, 
            all **kwargs are passed on to the call to 
            matplotlib.patches.Ellipse

            not surprisingly Ellipse only works for 2d data.

            the number of standard deviations, 'nstd', is just a multiplier for 
            the eigen values. So the standard deviations are projected, if you 
            want volumetric standard deviations I think you need to multiply by sqrt(ndim)
        """
        if self.mean.size != 2:
            raise ValueError(
                'this method can only produce patches for 2d data'
            )
        
        #unpack the width and height from the scale matrix 
        width,height = nstd*numpy.diag(self.scale)
        
        #return an Ellipse patch
        return Ellipse(
            #with the Mvar's mean at the centre 
            xy=tuple(self.mean.flatten()),
            #matching width and height
            width=width, height=height,
            #and rotation angle pulled from the rotation matrix
            angle=numpy.rad2deg(
                numpy.angle(astype(
                    self.rotation,
                    complex,
                )).flatten()[0]
            ),
            #while transmitting any kwargs.
            **kwargs
        )


## extras    

def wiki(P,M):
    """
    Direct implementation of the wikipedia blending algorythm
    
    The quickest way to prove it's equivalent is by examining this:
        >>> ab=numpy.array([A,B],ndmin=2,dytpe=object)
        >>> assert A & B == dot(ab,(ab.T)**(-2))**(-1)
    """
    yk=M.mean.T-P.mean.T
    Sk=P.cov+M.cov
    Kk=dot(P.cov,(Sk**-1))
    
    return Mvar.from_cov(
        (P.mean.T+dot(Kk*yk)).T,
        dot((numpy.eye(P.mean.size)-Kk),P.cov)
    )

def isplit(sequence,fkey=bool): 
    """
        return a defaultdict (where the default is an empty list), 
        where every value is a sub iterator produced from the sequence
        where items are sent to iterators based on the value of fkey(item).
        
        >>> isodd = isplit([xrange(1,7),lambda item:bool(item%2))
        >>> list(isodd[True])
        [1,3,5]
        >>> list(isodd[False])
        [2,4,6]
        
        which gives the same results as
        
        >>> X=xrange(1,7)
        >>> [item for item in X if bool(item%2)]
        [1,3,5]
        >>> [item for item in X if not bool(item%2)]
        [2,4,6]
        
        or you could make a mess of maps and filter
        but this is so smooth,and really shortens things 
        when dealing with a lot of keys 
        
        >>> bytype = isplit([1,'a',True,"abc",5,7,False],type)
        >>> list(bytype[int])
        [1,5,7]
        >>> list(bytype[str])
        ['a','abc']
        >>> list(bytype[bool])
        [True,False]
        >>> list(bytype[dict])
        []
    """
    result = collections.defaultdict(list,())
    print result
    for key,iterator in itertools.groupby(sequence,fkey):
        result[key]=itertools.chain(result[key],iterator)
        
    return result

    
def issquare(A):
    shape=A.shape
    return A.ndim==2 and shape[0] == shape[1]

def isrotation(A):
    R=numpy.matrix(A)
    return (R*R.T == eye(R.shape[0])).all()

def isdiag(A):
    shape=A.shape
    return A.ndim==2 and ((A != 0) == numpy.eye(shape[0],shape[1])).all()


if __name__=="__main__":
    import doctest

    A=Mvar.from_attr(mean=[1,2],vectors=[[3,4],[-1,8]])
    B=Mvar.from_cov(mean=[3,3],cov=[[1,2],[2,1]])
    M=numpy.matrix([[1.0,2],[3,4]])
    K=7.0

    doctest.testmod()
