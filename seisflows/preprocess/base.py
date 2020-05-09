#!/usr/bin/env python
"""
This is the main seisflows.preprocess.base

This is a main Seisflows class, it controls the preprocessing. This main class
is mainly empty, but provides the necessary skeleton of functions necessary
for subclasses to implement, which will be called by other modules in the
package.
"""
import sys
import obspy

PAR = sys.modules['seisflows_parameters']
PATH = sys.modules['seisflows_paths']


class Base(object):
    """
    Data preprocessing class

    Provides data processing functions for seismic traces, with options for
    data misfit, filtering, normalization and muting
    """
    def check(self):
        """ 
        Checks parameters and paths
        """
        raise NotImplementedError('Must be implemented by subclass.')

    def setup(self):
        """
        Sets up data preprocessing machinery
        """
        raise NotImplementedError('Must be implemented by subclass.')

    def prepare_eval_grad(self, path='.'):
        """
        Prepares solver for gradient evaluation by writing residuals and
        adjoint traces

        :type path: str
        :param path: directory containing observed and synthetic seismic data
        """
        raise NotImplementedError('Must be implemented by subclass.')

    def prepare_eval_hess(self, path='.'):
        """
        Optional, prepares solver for hessian evaluation

        :type path: str
        :param path: directory containing observed and synthetic seismic data
        """
        pass

    def write_residuals(self, path, syn, obs):
        """
        Computes residuals and write them to disk

        :type path: str
        :param path: location "adjoint traces" will be written
        :type syn: obspy.core.stream.Stream
        :param syn: synthetic data
        :type obs: obspy.core.stream.Stream
        :param syn: observed data
        """
        raise NotImplementedError('Must be implemented by subclass.')

    def sum_residuals(self, files):
        """
        Sum residuals to provide a value for the total misfit

        :type files: str
        :param files: list of single-column text files containing residuals
        :rtype: float
        :return: sum of squares of residuals
        """
        raise NotImplementedError('Must be implemented by subclass.')

    def finalize(self):
        """
        Optional: run finalization routines for preprocessing machinery.
        """
        pass
