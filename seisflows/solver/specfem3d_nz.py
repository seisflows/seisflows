import time
import subprocess
from glob import glob
from os.path import join

import sys

import seisflows.plugins.solver.specfem3d as solvertools
from seisflows.tools.seismic import getpar, setpar

from seisflows.tools import unix
from seisflows.tools.seismic import call_solver
from seisflows.tools.tools import exists
from seisflows.config import ParameterError, custom_import

PAR = sys.modules['seisflows_parameters']
PATH = sys.modules['seisflows_paths']

system = sys.modules['seisflows_system']
preprocess = sys.modules['seisflows_preprocess']


class specfem3d_nz(custom_import('solver', 'base')):
    """ Python interface for SPECFEM3D

      See base class for method descriptions
    """
    def check(self):
        """ Checks parameters and paths
        """
        super(specfem3d_nz, self).check()

        # check time stepping parameters
        if 'NT' not in PAR:
            raise Exception()

        if 'DT' not in PAR:
            raise Exception()

        # check data format
        if 'FORMAT' not in PAR:
            raise Exception()

        # make sure data format is accetapble
        if PAR.FORMAT not in ['su', 'ascii']:
            raise Exception()

    def setup(self):
        """
          Overload of solver.base.setup, removes the need to move data around
          as Pyatoa takes care of data fetching within eval_func
          Prepares solver for inversion or migration
          Sets up directory structure expected by SPECFEM and copies or
          generates seismic data to be inverted or migrated
        """
        # clean up for new inversion
        unix.rm(self.cwd)
         
        self.initialize_solver_directories()
        
        # if synthetic case, create synthetic observations 
        if PAR.CASE == "Synthetic":
            self.generate_data(
                model_path=PATH.MODEL_TRUE,
                model_name='model_true',
                model_type='gll')

        # prepare initial model
        self.generate_mesh(
            model_path=PATH.MODEL_INIT,
            model_name='model_init',
            model_type='gll')

    def generate_data(self, **model_kwargs):
        """ 
        Generates data in the synthetic-synthetic comparison case.
        Not for use in the real-data problem. Differs from specfem3d.nz in that
        it automatically calls generate mesh for the true model, rather than
        passing them in as kwargs.
        """
        # Prepare for the forward simulation
        self.generate_mesh(**model_kwargs)

        print 'specfem3d_nz.generate data'
        unix.cd(self.cwd)
        setpar('SIMULATION_TYPE', '1')
        setpar('SAVE_FORWARD', '.true.')
        setpar('ATTENUATION ', '.true.')
        call_solver(system.mpiexec(), 'bin/xspecfem3D')

        # seismic unix format
        if PAR.FORMAT in ['SU', 'su']:
            src = glob('OUTPUT_FILES/*_d?_SU')
            dst = 'traces/obs'
            unix.mv(src, dst)
        # ascii sem output format
        elif PAR.FORMAT == "ascii":
            src = glob('OUTPUT_FILES/*sem?')
            dst = 'traces/obs'
            unix.mv(src, dst)

        if PAR.SAVETRACES:
            self.export_traces(PATH.OUTPUT+'/'+'traces/obs')

    def generate_mesh(self, model_path=None, model_name=None, model_type='gll'):
        """ Performs meshing and database generation
        """
        print 'specfem3d_nz.generate mesh'
        assert(model_name)
        assert(model_type)

        unix.cd(self.cwd)

        if model_type in ['gll']:
            par = getpar('MODEL').strip()
            if par != 'gll':
                if self.taskid == 0:
                    print 'WARNING: Unexpected Par_file setting:'
                    print 'MODEL =', par
            
            assert(exists(model_path))
            self.check_mesh_properties(model_path)

            src = glob(model_path + '/' + '*')
            dst = self.model_databases
            unix.cp(src, dst)

            call_solver(system.mpiexec(), 'bin/xgenerate_databases')

            if self.taskid == 0:
                self.export_model(PATH.OUTPUT + '/' + model_name)

        else:
            raise NotImplementedError

    def eval_fwd(self, path=''):
        """
        Performs forward simulations for misfit function evaluation.
        Same as solver.base.eval_func without the residual writing.
        For use in specfem3d_nz where eval_func is taken by Pyatoa.
        """
        print 'specfem3d_nz.eval_fwd'
        unix.cd(self.cwd)
        self.import_model(path)
        self.forward()
    
    def eval_func(self, iter='', step=0, suffix=None, *args, **kwargs):
        """
        evaluate the misfit functional using the external package Pyatoa.
        Pyatoa is written in Python3 so it needs to be called with subprocess

        :param args:
        :param kwargs:
        :return:
        """
        print 'specfem3d_nz.eval_func'
        load_conda = "module load Anaconda2/5.2.0-GCC-7.1.0;"
        load_hdf5 = "module load HDF5/1.10.1-GCC-7.1.0;"
        arguments = " ".join([
            "--mode process",
            "--working_dir {}".format(PATH.WORKDIR),
            "--current_dir {}".format(self.cwd),
            "--model_number {}".format("m{:0>2}".format(int(iter) - 1)),
            "--event_id {}".format(self.source_name),
            "--step_count {}".format("s{:0>2}".format(step)),
            "--suffix {}".format(suffix)
        ])
        call_pyatoa = " ".join([load_conda, load_hdf5, PATH.PYTHON3,
                                PATH.PYATOA_RUN, arguments
                                ])
        print(call_pyatoa)
        try:
            tstart = time.time()
            stdout = subprocess.check_output(call_pyatoa, shell=True)
            print '{:.2f}m elapsed'.format((time.time() - tstart) / 60 )
        except subprocess.CalledProcessError as e:
            print("Pyatoa failed with {}".format(e))
            sys.exit(-1)
    
    # low-level solver interface
    def forward(self, path='traces/syn'):
        """ Calls SPECFEM3D forward solver and then moves files into path
        """
        setpar('SIMULATION_TYPE', '1')
        setpar('SAVE_FORWARD', '.true.')
        setpar('ATTENUATION ', '.true.')
        call_solver(system.mpiexec(), 'bin/xgenerate_databases')
        call_solver(system.mpiexec(), 'bin/xspecfem3D')

        # seismic unix output format
        if PAR.FORMAT in ['SU', 'su']:
            src = glob('OUTPUT_FILES/*_d?_SU')
            dst = path
            unix.mv(src, dst)
        # ascii sem output format
        elif PAR.FORMAT == "ascii":
            src = glob('OUTPUT_FILES/*sem?')
            dst = path
            unix.mv(src, dst)

    def adjoint(self):
        """ Calls SPECFEM3D adjoint solver
        """
        setpar('SIMULATION_TYPE', '3')
        setpar('SAVE_FORWARD', '.false.')
        setpar('ATTENUATION ', '.false.')
        unix.rm('SEM')
        unix.ln('traces/adj', 'SEM')
        call_solver(system.mpiexec(), 'bin/xspecfem3D')

    # input file writers
    def check_solver_parameter_files(self):
        """ Checks solver parameters
        """
        nt = getpar('NSTEP', cast=int)
        dt = getpar('DT', cast=float)

        if nt != PAR.NT:
            if self.taskid == 0: print "WARNING: nt != PAR.NT"
            setpar('NSTEP', PAR.NT)

        if dt != PAR.DT:
            if self.taskid == 0: print "WARNING: dt != PAR.DT"
            setpar('DT', PAR.DT)

        if self.mesh_properties.nproc != PAR.NPROC:
            if self.taskid == 0:
                print 'Warning: mesh_properties.nproc != PAR.NPROC'

        if 'MULTIPLES' in PAR:
            raise NotImplementedError

    def initialize_adjoint_traces(self):
        super(specfem3d_nz, self).initialize_adjoint_traces()

        # workaround for SPECFEM2D's use of different name conventions for
        # regular traces and 'adjoint' traces
        if PAR.FORMAT in ['SU', 'su']:
            files = glob(self.cwd + '/' + 'traces/adj/*SU')
            unix.rename('_SU', '_SU.adj', files)

        # workaround for SPECFEM3D's requirement that all components exist,
        # even ones not in use
        unix.cd(self.cwd + '/' + 'traces/adj')
        for iproc in range(PAR.NPROC):
            for channel in ['x', 'y', 'z']:
                src = '%d_d%s_SU.adj' % (iproc, PAR.CHANNELS[0])
                dst = '%d_d%s_SU.adj' % (iproc, channel)
                if not exists(dst):
                    unix.cp(src, dst)

    def rename_data(self):
        """ Works around conflicting data filename conventions
        """
        if PAR.FORMAT in ['SU', 'su']:
            files = glob(self.cwd + '/' + 'traces/adj/*SU')
            unix.rename('_SU', '_SU.adj', files)

    def write_parameters(self):
        unix.cd(self.cwd)
        solvertools.write_parameters(vars(PAR))

    def write_receivers(self):
        unix.cd(self.cwd)
        key = 'use_existing_STATIONS'
        val = '.true.'
        setpar(key, val)
        _, h = preprocess.load('traces/obs')
        solvertools.write_receivers(h.nr, h.rx, h.rz)

    def write_sources(self):
        unix.cd(self.cwd)
        _, h = preprocess.load(dir='traces/obs')
        solvertools.write_sources(vars(PAR), h)

    # postprocessing wrapper overload
    def smooth(self, input_path='', output_path='',
               parameters=[], span_h=0., span_v=0.):
        """ Smooths kernels by convolving them with a Gaussian.  Wrapper over 
            xsmooth_sem utility. 
            smooth() in base.py has the incorrect command line call, specfem 
            requires that NPROC be specified
        """
        if not exists(input_path):
            raise Exception

        if not exists(output_path):
            unix.mkdir(output_path)

        # apply smoothing operator
        unix.cd(self.cwd)
        print 'smoothing parameters ', self.parameters
        for name in parameters or self.parameters:
            print 'smoothing', name
            solver_call = " ".join([
                    PATH.SPECFEM_BIN + '/' + 'xsmooth_sem',  # ./bin/xsmooth_sem
                    str(span_h),  # SIGMA_H
                    str(span_v),  # SIGMA_V
                    name + '_kernel',  # KERNEL_NAME
                    input_path + '/',  # INPUT_DIR
                    output_path + '/',  # OUTPUT_DIR
                    '.false'  # USE_GPU
                    ])
            call_solver(system.mpiexec(), solver_call)
        print ''

        # rename output files
        files = glob(output_path+'/*')
        unix.rename('_smooth', '', files)

    def combine_vol_data(self, output_path='', quantity=''):
        """
        This does not work
        Call Specfems executable combine_vol_data_vtk on kernels or model files
        """
        if not exists(output_path):
            unix.mkdir(output_path)
       
        # This should probably be moved to its own function 
        # def import_kernels()
        unix.cd(self.cwd)
        src = glob(join(PATH.GRAD, self.source_name, "*{}*".format(quantity)))
        dst = join(self.cwd, "kernels")
        unix.mkdir(dst)
        unix.ln(src=src, dst=dst)
        
        solver_call = " ".join([
                PATH.SPECFEM_BIN + '/' + 'xcombine_vol_data_vtk',
                0, # NPROC_START
                PAR.NPROC,  # NPROC_END
                quantity,  # QUANTITY
                dst,  # DIR_IN
                dst,  # DIR_OUT, we will rename the files first
                0  # GPU ACCEL
                ])
        call_solver(system_mpiexec(), solver_call)
        
        unix.rm(dst)
        print ''

    # miscellaneous
    @property
    def data_wildcard(self):
        channels = PAR.CHANNELS
        return '*_d[%s]_SU' % channels.lower()

    @property
    def data_filenames(self):
        unix.cd(self.cwd+'/'+'traces/obs')

        if PAR.FORMAT in ['SU', 'su']:
            if not PAR.CHANNELS:
                return sorted(glob('*_d?_SU'))
            filenames = []
            for channel in PAR.CHANNELS:
                filenames += sorted(glob('*_d'+channel+'_SU'))
            return filenames

        else:
            raise NotImplementedError

    @property
    def kernel_databases(self):
        return join(self.cwd, 'OUTPUT_FILES/DATABASES_MPI')

    @property
    def model_databases(self):
        return join(self.cwd, 'OUTPUT_FILES/DATABASES_MPI')

    @property
    def source_prefix(self):
        return 'CMTSOLUTION'

