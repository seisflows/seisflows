#!/usr/bin/env python
"""
This is the subclass seisflows.preprocess.pyatoa

This is a main Seisflows class, it controls the preprocessing.
This subclass uses the Python package Pyatoa to perform preprocessing, and
misfit measurement.
"""
import sys
import obspy
import numpy as np

from seisflows.config import custom_import
from seisflows.tools.err import ParameterError

from pyatoa import Pyaflowa
from pyatoa.utils.write import (create_stations_adjoint, write_adj_src_to_ascii,
                                write_misfit_stats, tile_combine_imgs,
                                src_vtk_from_specfem, rcv_vtk_from_specfem
                                )

PAR = sys.modules['seisflows_parameters']
PATH = sys.modules['seisflows_paths']


class Pyatoa(custom_import("preprocess", "base")):
    """
    Data preprocessing class

    Outsources data handling to Pyatoa via the class Pyaflowa. All calls are
    made external, this class is simply used as a Seisflows abstraction for
    calls to Pyatoa.
    """
    def check(self):
        """ 
        Checks parameters and paths
        """
        # Pyatoa specific paths
        if "PYATOA_IO" not in PATH:
            raise ParameterError(PATH, "PYATOA_IO")

        super(Pyatoa, self).check()

    def setup(self):
        """
        Sets up data preprocessing machinery by initiating the Pyaflowa class,
        which will parse directory structure and generate the relevant
        directories that are to be filled during the workflow
        """
        self.pyaflowa = Pyaflowa(par=vars(PAR), paths=vars(PATH))

    def prepare_eval_grad(self, path):
        """
        Prepares solver for gradient evaluation by writing residuals and
        adjoint traces.

        This functionality is already taken care of by Pyaflowa.process()

        :type path: str
        :param path: directory containing observed and synthetic seismic data
        """
        self.pyaflowa.prepare_eval_grad()

    def prepare_eval_hess(self, path):
        """

        :param path:
        :return:
        """
        raise NotImplementedError

    def write_residuals(self, path):
        """
        Computes residuals

        :type path: str
        :param path: location "adjoint traces" will be written
        """
        self.pyaflowa.write_residuals()

    def sum_residuals(self, files):
        """
        Sums the average misfit from each event, average by number of events

        :type files: str
        :param files: list of single-column text files containing residuals
        :rtype: float
        :return: average misfit
        """
        assert(len(files) == PAR.NTASK), \
            "Number of misfit files does not match the number of events"
        total_misfit = 0
        for filename in files:
            total_misfit += np.sum(np.loadtxt(filename))

        # Save the total misfit
        total_misfit = total_misfit / PAR.NTASK

        return total_misfit



