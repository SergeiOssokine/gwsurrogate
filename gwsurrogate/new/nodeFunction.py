"""Classes for parameter space fits or interpolants"""

from __future__ import division # for python 2


__copyright__ = "Copyright (C) 2014 Scott Field and Chad Galley"
__email__     = "sfield@astro.cornell.edu, crgalley@tapir.caltech.edu"
__status__    = "testing"
__author__    = "Jonathan Blackman"

__license__ = """
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

if __package__ is "" or "None": # py2 and py3 compatible
  print("setting __package__ to gwsurrogate.new so relative imports work")
  __package__="gwsurrogate.new"
from .saveH5Object import SimpleH5Object  # assumes unique global name

from gwsurrogate import parametric_funcs
import numpy as np
import gwtools
from gwsurrogate.eval_pysur import evaluate_fit

import warnings


class DummyNodeFunction(SimpleH5Object):
    """Used for testing, returns the input or a constant."""

    def __init__(self, return_value=None):
        super(DummyNodeFunction, self).__init__()
        self.val = return_value

    def __call__(self, x):
        if self.val is None:
            return np.mean(x)
        else:
            return self.val


class Polyfit1D(SimpleH5Object):
    """Wrapper class to make use of the old parametric_funcs module"""

    def __init__(self, function_name=None, coefs=None):
        """
        function_name: A key from parametric_funcs.function_dict
        coefs: The fit coefficients to be used when called
        """
        super(Polyfit1D, self).__init__()
        self.function_name=function_name
        self.coefs = coefs

    def __call__(self, x):
        func = parametric_funcs.function_dict[self.function_name]
        return func(self.coefs, x[0])


class pySurrogateFit(SimpleH5Object):
    """Wrapper class to evaluate pySurrogate fits"""

    def __init__(self, name=None, fit_data=None):
        """
        name: A unique identifier.
        fit_data: fit results generated by pySurrogate.fit.fitWrapper
        """
        super(pySurrogateFit, self).__init__(data_keys=['name', 'fit_data'])
        self.name=name
        self.fit_data = fit_data

        # DO NOT include fitFunc in data_keys above. That will try to
        # write fitFunc to h5, which will fail when using GPR fits.
        # We can load the fit using fit_data only, so we don't need to
        # save fitFunc
        self.h5_prepare_subs()

    def h5_prepare_subs(self):
        self.fitFunc = evaluate_fit.getFitEvaluator(self.fit_data)

    def __call__(self, x):
        return self.fitFunc(x)


class NRHybSur3dq8Fit(pySurrogateFit):
    """
    Evaluates fits for the NRHybSur3dq8 surrogate model.

    Transforms the input parameter to fit parameters before evaluating the fit.
    That is, maps from [q, chi1z, chi2z] to [np.log(q), chiHat, chi_a]
    chiHat is defined in Eq.(3) of 1508.07253.
    chi_a = (chi1z - chi2z)/2.
    """

    def __call__(self, x):
        q, chi1z, chi2z = x

        eta = q/(1.+q)**2
        chi_wtAvg = (q*chi1z+chi2z)/(1.+q)
        chiHat = (chi_wtAvg - 38.*eta/113.*(chi1z + chi2z))/(1. - 76.*eta/113.)
        chi_a = (chi1z - chi2z)/2.

        mapped_x = [np.log(q), chiHat, chi_a]

        with warnings.catch_warnings():
            # Ignore this specific GPR warning.
            # This warning was mentioned in issues:
            # https://github.com/autoreject/autoreject/issues/35
            # https://github.com/scikit-learn/scikit-learn/issues/8748
            # But it seems like we can ignore it
            warnings.filterwarnings("ignore", message="Predicted variances"
                " smaller than 0. Setting those variances to 0.")

            return super(NRHybSur3dq8Fit, self).__call__(mapped_x)

class NRHybSur2dq15Fit(pySurrogateFit):
    """
    Evaluates fits for the NRHybSur2dq15 surrogate model.

    Transforms the input parameter to fit parameters before evaluating the fit.
    That is, maps from [q, chi1z] to [np.log(q), chiHat]
    chiHat is defined in Eq.(3) of 1508.07253.
    """

    def __call__(self, x):
        q, chi1z = x
        chi2z = 0

        eta = q/(1.+q)**2
        chi_wtAvg = (q*chi1z+chi2z)/(1.+q)
        chiHat = (chi_wtAvg - 38.*eta/113.*(chi1z + chi2z))/(1. - 76.*eta/113.)

        mapped_x = [np.log(q), chiHat]

        with warnings.catch_warnings():
            # Ignore this specific GPR warning.
            # This warning was mentioned in issues:
            # https://github.com/autoreject/autoreject/issues/35
            # https://github.com/scikit-learn/scikit-learn/issues/8748
            # But it seems like we can ignore it
            warnings.filterwarnings("ignore", message="Predicted variances"
                " smaller than 0. Setting those variances to 0.")

            return super(NRHybSur2dq15Fit, self).__call__(mapped_x)


class MappedPolyFit1D_q10_q_to_nu(Polyfit1D):
    """
    Transforms the input before evaluating the fit. Used for the SpEC q 1 to 10
    non-spinning surrogate. This could be generalized later.
    """

    def __call__(self, x):
        mapped_x = 4*gwtools.q_to_nu(x)
        return super(MappedPolyFit1D_q10_q_to_nu, self).__call__(mapped_x)


NODE_CLASSES = {
    "Dummy": DummyNodeFunction,
    "Polyfit1D": Polyfit1D,
    "SpEC_q10_non_spinning": MappedPolyFit1D_q10_q_to_nu,
    "NRHybSur3dq8Fit": NRHybSur3dq8Fit,
    "NRHybSur2dq15Fit": NRHybSur2dq15Fit,
        }


class NodeFunction(SimpleH5Object):
    """
    A holder class for any node function (for example a parametric fit or
    tensor-spline). This is essentially only to let us know what class to
    initialize when loading from an h5 file.
    """

    def __init__(self, name='', node_function=None):
        """
        name: A name for this node
        node_function: An instance of one of the values in NODE_CLASSES
        """
        super(NodeFunction, self).__init__(sub_keys=['node_function'])
        self.name = name
        self.node_function = node_function
        self.node_class = None
        if node_function is not None:
            for k, v in NODE_CLASSES.items(): # inefficient on Py2
                if node_function.__class__.__name__ == v.__name__:
                    self.node_class = k
            if self.node_class is None:
                raise Exception("node_function must be in NODE_CLASSES!")

    def __call__(self, x):
        return self.node_function(x)

    def h5_prepare_subs(self):
        self.node_function = NODE_CLASSES[self.node_class]()
