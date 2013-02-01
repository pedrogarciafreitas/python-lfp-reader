# python
#
# lfp-reader
# LFP (Light Field Photography) File Reader.
#
# http://code.behnam.es/python-lfp-reader/
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright (C) 2012-2013  Behnam Esfahbod


"""
=========================================
LFP (Light Field Photography) File Reader
=========================================

Provides a Python library and command-line scripts to read Lytro LFP files, and
a simple viewer for Lytro LFP Picture files.

Technically, there are two types of LFP files: Picture and Storage.  LFP
Storage files are used to store the data and configurations for Lytro cameras,
and LFP Picture (.lfp) files are used to store RAW and/or processed data for
Lytro light-field pictures.

This is a pure-Python package and should work on any platform.  Please report
any problems at <https://github.com/behnam/python-lfp-reader/issues>.


LFP Reader Library
=======================

**LFP Reader library (``lfp_reader``)** provides direct reading access to all
data and metadata in any LFP files. For the processed LFP Picture files, you
can easily access the JPEG data and the depth table. And for LFP Storage files,
you can access embedded files easily using their pathname.

The main classes in the ``lfp_reader`` package are:

- ``LfpGenericFile``
- ``LfpPictureFile``
- ``LfpStorageFile``
- ``LfpTkViewer``


Legal Notice
============

This project is NOT affiliated with LYTRO, INC.  Lytro (R) is a trademark of
LYTRO, INC. <http://www.lytro.com/>

Some of this work is based on Nirav Patel's ``lfptools`` project and his
analysis on LFP file format.  <https://github.com/nrpatel/lfptools>

Copyright (C) 2012-2013 Behnam Esfahbod.

"""


from lfp_file      import LfpGenericFile, LfpGenericError
from lfp_picture   import LfpPictureFile, LfpPictureError
from lfp_storage   import LfpStorageFile, LfpStorageError
from lfp_tk_viewer import LfpTkViewer


__version__     = "2.0"
__author__      = "Behnam Esfahbod"
__copyright__   = "Copyright 2012-2013, Behnam Esfahbod"
__credits__     = ["Behnam Esfahbod"]
__license__     = "GPLv3+"
__maintainer__  = "Behnam Esfahbod"
__email__       = "behnam@behnam.es"
__status__      = "Production"

