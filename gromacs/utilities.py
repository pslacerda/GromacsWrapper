# $Id$
# Copyright (c) 2009 Oliver Beckstein <orbeckst@gmail.com>
# Released under the GNU Public License 3 (or higher, your choice)
# See the file COPYING for details.

"""
``gromacs.utilities`` -- Helper functions and classes
=====================================================

The module defines some convenience functions and classes that are
used in other modules; they do *not* make use of :mod:`gromacs.tools`
or :mod:`gromacs.cbook` and can be safely imported.

Classes
-------

:class:`FileUtils` provides functions related to filename handling. It
can be used as a mixin class. The :class:`gromacs.analysis.Simulation`
class is derived from it.

.. autoclass:: FileUtils
   :members:
.. autoclass:: AttributeDict
.. autoclass:; XVG

Functions
---------

Some additiona convenience functions:

.. autofunction:: anyopen
.. autofunction:: iterable
.. autofunction:: convert_aa_code
.. autofunction:: unlink_f
.. autofunction:: unlink_gmx
.. autofunction:: unlink_gmx_backups

Data
----

.. autodata:: amino_acid_codes

"""
from __future__ import with_statement

__docformat__ = "restructuredtext en"

import os
import glob
import warnings
import errno
import bz2, gzip
import numpy

class AttributeDict(dict):
    """A dictionary with pythonic access to keys as attributes --- useful for interactive work."""
    def __getattribute__(self,x):
        try:
            return super(AttributeDict,self).__getattribute__(x)
        except AttributeError:
            return self[x]
    def __setattr__(self,name,value):
        try:
            super(AttributeDict,self).__setitem__(name, value)
        except KeyError:
            super(AttributeDict,self).__setattr__(name, value)            

def anyopen(datasource):
    """Open datasource and return a stream."""
    if hasattr(datasource,'next') or hasattr(datasource,'readline'):
        stream = datasource
        filename = '(%s)' % stream.name  # maybe that does not always work?        
    else:
        stream = None
        filename = datasource
        for openfunc in bz2.BZ2File, gzip.open, file:   # file should be last
            stream = _get_stream(datasource, openfunc)
            if not stream is None:
                break
        if stream is None:
            raise IOError("Cannot open %r for reading." % filename)
    return stream, filename

def _get_stream(filename, openfunction=file):
    try:
        stream = openfunction(filename,'r')
    except IOError:
        return None

    try:
        stream.readline()
        stream.close()
        stream = openfunction(filename,'r')
    except IOError:
        stream.close()
        stream = None
    return stream

#: translation table for 1-letter codes --> 3-letter codes 
amino_acid_codes = {'A':'ALA', 'C':'CYS', 'D':'ASP', 'E':'GLU',
                    'F':'PHE', 'G':'GLY', 'H':'HIS', 'I':'ILE',
                    'K':'LYS', 'L':'LEU', 'M':'MET', 'N':'ASN',
                    'P':'PRO', 'Q':'GLN', 'R':'ARG', 'S':'SER',
                    'T':'THR', 'V':'VAL', 'W':'TRP', 'Y':'TYR'}
inverse_aa_codes = dict([(three, one) for one,three in amino_acid_codes.items()])

def convert_aa_code(x):
    """Converts between 3-letter and 1-letter amino acid codes."""
    if len(x) == 1:
        return amino_acid_codes[x.upper()]
    elif len(x) == 3:
        return inverse_aa_codes[x.upper()]
    else:
        raise ValueError("Can only convert 1-letter or 3-letter amino acid codes, "
                         "not %r" % x)


class FileUtils(object):
    """Mixin class to provide additional IO capabilities."""

    def filename(self,filename=None,ext=None,set_default=False,use_my_ext=False):
        """Supply a file name for the class object.

        Typical uses::

           fn = filename()             ---> <default_filename>
           fn = filename('name.ext')   ---> 'name'
           fn = filename(ext='pickle') ---> <default_filename>'.pickle'
           fn = filename('name.inp','pdf') --> 'name.pdf'
           fn = filename('foo.pdf',ext='png',use_my_ext=True) --> 'foo.pdf'

        The returned filename is stripped of the extension
        (``use_my_ext=False``) and if provided, another extension is
        appended. Chooses a default if no filename is given.  

        Raises a ``ValueError`` exception if no default file name is known.

        If ``set_default=True`` then the default filename is also set.

        ``use_my_ext=True`` lets the suffix of a provided filename take
        priority over a default ``ext`` tension.
        """
        if filename is None:
            if not hasattr(self,'_filename'):
                self._filename = None        # add attribute to class 
            if self._filename:
                filename = self._filename
            else:
                raise ValueError("A file name is required because no default file name was defined.")
            my_ext = None
        else:
            filename, my_ext = os.path.splitext(filename)
            if set_default:                  # replaces existing default file name
                self._filename = filename
        if my_ext and use_my_ext:  
            ext = my_ext
        if ext is not None:
            if ext.startswith('.'):
                ext = ext[1:]  # strip a dot to avoid annoying mistakes
            filename = filename + '.' + ext
        return filename

    def check_file_exists(self, filename, resolve='exception'):
        """If a file exists then continue with the action specified in ``resolve``.

        ``resolve`` must be one of

        "ignore"
              always return ``False``
        "indicate"
              return ``True`` if it exists
        "warn"
              indicate and issue a :exc:`UserWarning`
        "exception"
              raise :exc:`IOError` if it exists
        """
        def _warn(x):
            warnings.warn("File %r already exists." % x)
            return True
        def _raise(x):
            raise IOError("File %r already exists." % x)
        solutions = {'ignore': lambda x: False,      # file exists, but we pretend that it doesn't
                     'indicate': lambda x: True,     # yes, file exists
                     'warn': _warn,
                     'warning': _warn,
                     'exception': _raise,
                     }
        if not os.path.isfile(filename):
            return False
        else:
            return solutions[resolve](filename)


class XVG(FileUtils):
    """Class that represents a grace xvg file."""
    def __init__(self, filename):
        self.filename = filename

    def asarray(self):
        """Return data of the file as numpy array.

        .. note:: Only simple nxy files are currently supported.
        """
        with open(self.filename) as xvg:
            rows = []
            for line in xvg:
                line = line.strip()
                if line.startswith(('#', '@')) or len(line) == 0:
                    continue
                rows.append(map(float, line.split()))
        return numpy.array(rows)

def iterable(obj):
    """Returns ``True`` if *obj* can be iterated over and is *not* a  string."""
    if type(obj) is str:
        return False    # avoid iterating over characters of a string

    if hasattr(obj, 'next'):
        return True    # any iterator will do 
    try: 
        len(obj)       # anything else that might work
    except TypeError: 
        return False
    return True

def asiterable(obj):
    """Returns obj so that it can be iterated over; a string is *not* treated as iterable"""
    if not iterable(obj):
        obj = [obj]
    return obj


# In utilities so that it can be safely used in tools, cbook, ...

def unlink_f(path):
    """Unlink path but do not complain if file does not exist."""
    try:
        os.unlink(path)
    except OSError, err:
        if err.errno <> errno.ENOENT:
            raise

def unlink_gmx(*args):
    """Unlink (remove) Gromacs file(s) and all corresponding backups."""
    for path in args:
        unlink_f(path)
    unlink_gmx_backups(*args)

def unlink_gmx_backups(*args):
    """Unlink (rm) all backup files corresponding to the listed files."""
    for path in args:
        dirname, filename = os.path.split(path)
        fbaks = glob.glob(os.path.join(dirname, '#'+filename+'.*#'))
        for bak in fbaks:
            unlink_f(bak)
