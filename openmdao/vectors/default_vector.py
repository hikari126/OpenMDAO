"""Define the default Vector and Transfer classes."""
from __future__ import division
import numpy

import numbers
from six.moves import range

from vector import Vector, Transfer

real_types = tuple([numbers.Real, numpy.float32, numpy.float64])


class DefaultTransfer(Transfer):
    """Default NumPy transfer."""

    def __call__(self, ip_vec, op_vec, mode='fwd'):
        """See openmdao.vectors.vector.Transfer."""
        ip_inds = self._ip_inds
        op_inds = self._op_inds

        if mode == 'fwd':
            for ip_iset, op_iset in self._ip_inds:
                key = (ip_iset, op_iset)
                if len(self._ip_inds[key]) > 0:
                    ip_inds = self._ip_inds[key]
                    op_inds = self._op_inds[key]
                    tmp = op_vec._global_vector._data[op_iset][op_inds]
                    ip_vec._global_vector._data[ip_iset][ip_inds] = tmp
        elif mode == 'rev':
            for ip_iset, op_iset in self._ip_inds:
                key = (ip_iset, op_iset)
                if len(self._ip_inds[key]) > 0:
                    ip_inds = self._ip_inds[key]
                    op_inds = self._op_inds[key]
                    tmp = ip_vec._global_vector._data[ip_iset][ip_inds]
                    numpy.add.at(op_vec._global_vector._data[op_iset],
                                 op_inds, tmp)


class DefaultVector(Vector):
    """Default NumPy vector."""

    TRANSFER = DefaultTransfer

    def _create_data(self):
        """Allocate list of arrays, one for each var_set.

        Returns
        -------
        [ndarray[:], ...]
            list of zeros arrays of correct size, one for each var_set.
        """
        return [numpy.zeros(numpy.sum(sizes[self._iproc, :]))
                for sizes in self._assembler._variable_sizes[self._typ]]

    def _extract_data(self):
        """Extract views of arrays from global_vector.

        Returns
        -------
        [ndarray[:], ...]
            list of zeros arrays of correct size, one for each var_set.
        """
        variable_sizes = self._assembler._variable_sizes[self._typ]
        variable_set_indices = self._assembler._variable_set_indices[self._typ]

        ind1, ind2 = self._system._variable_allprocs_range[self._typ]
        sub_variable_set_indices = variable_set_indices[ind1:ind2, :]

        data = []
        for iset in range(len(variable_sizes)):
            bool_vector = sub_variable_set_indices[:, 0] == iset
            data_inds = sub_variable_set_indices[bool_vector, 1]
            if len(data_inds) > 0:
                sizes_array = variable_sizes[iset]
                ind1 = numpy.sum(sizes_array[self._iproc, :data_inds[0]])
                ind2 = numpy.sum(sizes_array[self._iproc, :data_inds[-1]+1])
                data.append(self._global_vector._data[iset][ind1:ind2])
            else:
                data.append(numpy.zeros(0))

        return data

    def _initialize_data(self, global_vector):
        """See openmdao.vectors.vector.Vector."""
        if global_vector is None:
            self._data = self._create_data()
        else:
            self._data = self._extract_data()

    def _initialize_views(self):
        """See openmdao.vectors.vector.Vector."""
        variable_sizes = self._assembler._variable_sizes[self._typ]
        variable_set_indices = self._assembler._variable_set_indices[self._typ]

        system = self._system
        variable_myproc_names = system._variable_myproc_names[self._typ]
        variable_myproc_indices = system._variable_myproc_indices[self._typ]
        meta = system._variable_myproc_metadata[self._typ]

        views = {}

        # contains a 0 index for floats or a slice(None) for arrays so getitem
        # will return either a float or a properly shaped array respectively.
        idxs = {}

        for ind, name in enumerate(variable_myproc_names):
            ivar_all = variable_myproc_indices[ind]
            iset, ivar = variable_set_indices[ivar_all, :]
            ind1 = numpy.sum(variable_sizes[iset][self._iproc, :ivar])
            ind2 = numpy.sum(variable_sizes[iset][self._iproc, :ivar+1])
            views[name] = self._global_vector._data[iset][ind1:ind2]
            views[name].shape = meta[ind]['shape']
            val = meta[ind]['value']
            if isinstance(val, real_types):
                idxs[name] = 0
            elif isinstance(val, numpy.ndarray):
                idxs[name] = slice(None)

        self._views = views
        self._idxs = idxs

    def _clone_data(self):
        """See openmdao.vectors.vector.Vector."""
        for iset in range(len(self._data)):
            data = self._data[iset]
            self._data[iset] = numpy.array(data)

    def __iadd__(self, vec):
        """See openmdao.vectors.vector.Vector."""
        for iset in range(len(self._data)):
            self._data[iset] += vec._data[iset]
        return self

    def __isub__(self, vec):
        """See openmdao.vectors.vector.Vector."""
        for iset in range(len(self._data)):
            self._data[iset] -= vec._data[iset]
        return self

    def __imul__(self, val):
        """See openmdao.vectors.vector.Vector."""
        for data in self._data:
            data *= val
        return self

    def add_scal_vec(self, val, vec):
        """See openmdao.vectors.vector.Vector."""
        for iset in range(len(self._data)):
            self._data[iset] *= val * vec._data[iset]

    def set_vec(self, vec):
        """See openmdao.vectors.vector.Vector."""
        for iset in range(len(self._data)):
            self._data[iset][:] = vec._data[iset]

    def set_const(self, val):
        """See openmdao.vectors.vector.Vector."""
        for data in self._data:
            data[:] = val

    def get_norm(self):
        """See openmdao.vectors.vector.Vector."""
        global_sum = 0
        for data in self._data:
            global_sum += numpy.sum(data**2)
        return global_sum ** 0.5