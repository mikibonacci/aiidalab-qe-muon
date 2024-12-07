from aiidalab_qe.common.mvc import Model
import traitlets as tl
from aiida.common.extendeddicts import AttributeDict
import numpy as np
import base64
import json
from IPython.display import display

from aiidalab_qe_muon.utils.export_findmuon import export_findmuon_data

from aiida import orm
import ase


class FindMuonModel(Model):
    """Model for the FindMuon data.
    
    """
    view_mode_options = [ # does not need to be a trait
            ("Compare sites", 0),
            ("Inspect site", 1),
    ]
    
    muon = tl.Instance(AttributeDict, allow_none=True)
    selected_indexes = tl.List(
        trait=tl.Unicode(),
    )
    selected_view_mode = tl.Int(0)
    structure = tl.Union(
        [
            tl.Instance(ase.Atoms),
            tl.Instance(orm.StructureData),
        ],
        allow_none=True,
    )
    
    
    def fetch_data(self):
        """Fetch the findmuon data from the FindMuonWorkChain outputs."""
        self.findmuon_data = export_findmuon_data(self.muon.findmuon)
        self.muon_index_list = self.findmuon_data["table"].columns.tolist()
        self.selected_indexes = [self.muon_index_list[0]]

    def select_structure(self):
        """Select a structure to be displayed.
        
        if we have multiple sites selected, we need to show the unrelaxed unit cell with all sites.
        Otherwise, we show the relaxed supercell with the single selected site.
        And then in the view we select only the one we want to inspect.
        """
        if len(self.muon_index_list) == 1:
            self.structure = self.findmuon_data["table"][str(self.muon_index_list[0])]["structure"]
        elif len(self.selected_indexes) == 1 and self.selected_view_mode == 0:
            self.structure = self.findmuon_data["table"][str(self.selected_indexes[0])]["structure"]
        elif len(self.selected_indexes) > 1:
            self.structure = self.findmuon_data["unit_cell"]