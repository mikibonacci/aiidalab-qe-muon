"""Module to provide functionality to import structures."""

import datetime
import functools
import io
import pathlib
import tempfile
from collections import OrderedDict

import ase
import ipywidgets as ipw
import numpy as np
import spglib
import traitlets as tl
from aiida import engine, orm, plugins

from aiidalab_widgets_base.data import LigandSelectorWidget
from aiidalab_widgets_base.utils import StatusHTML, exceptions, get_ase_from_file, get_formula
from aiidalab_widgets_base.viewers import StructureDataViewer

from pymatgen.io.cif import CifParser
from aiidalab_widgets_base import (
    StructureUploadWidget,
)
from pymatgen.core import Structure

def get_pymatgen_from_file(fname, file_format="mcif",primitive=True):  # pylint: disable=redefined-builtin
    """Get pymatgen structure object."""
    try:
        parser  = CifParser(fname)
        traj    = parser.get_structures(primitive = primitive)[0]
    except:
        raise ValueError(f"Could not read any information from the file {fname}")
    return traj


class ImportMagnetism(StructureUploadWidget):
    """
    Import a structure by reading mcif file, for magnetism.
    Up to now, this is meant to work with muons.
    """

    structure = tl.Union(
        [tl.Instance(Structure), tl.Instance(orm.Data)], allow_none=True
    )

    def __init__(
        self, title="Upload mcif", description="Upload Structure", allow_trajectories=False
    ):
        super().__init__()
        self.title = title
        self.file_upload_subwidget1 = ipw.Checkbox(
            description="Use conventional (select before the upload)",
            indent=False,
            value=False,
        )
        self.file_upload = ipw.FileUpload(
            description=description, multiple=False, layout={"width": "initial"}
        )
        
        # Whether to allow uploading multiple structures from a single file.
        # In this case, we create TrajectoryData node.
        supported_formats = ipw.HTML(
            """<a Supported format is mcif. </a>"""
        )
        self._status_message = StatusHTML(clear_after=5)
        self.file_upload.observe(self._on_file_upload, names="value")
        
        self.children = tuple([self.file_upload_subwidget1]) + self.children
        
    def _validate_and_fix_pymatgen_cell(self, structure):
    
        structure_aiida = orm.StructureData(pymatgen=structure)
        if "magmom" in structure.site_properties.keys():
            magmoms = structure.site_properties["magmom"]
            magmom = orm.List([list(magmom) for magmom in magmoms])  
            structure_aiida.base.extras.set("magmom",magmom)
        
        return structure_aiida
    
    def _read_structure(self, fname, content):
        suffix = "".join(pathlib.Path(fname).suffixes)            

        with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            try:
                structures = get_pymatgen_from_file(temp_file.name,primitive=not self.file_upload_subwidget1)
            except KeyError:
                self._status_message.message = f"""
                    <div class="alert alert-danger">ERROR: Could not parse file {fname}</div>
                    """
                return None

            
            return self._validate_and_fix_pymatgen_cell(structures)
        