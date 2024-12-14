from aiidalab_qe.common.panel import ResultsModel
import traitlets as tl
from aiida import orm

class MuonResultsModel(ResultsModel):
    
    """Top level model for result models in the muon spectroscopy.
    
        For each specific subworkflow of ImplantMuonWorkChain, 
        a new model should be created and injected in the corresponding view.
    """
    
    identifier = "muonic"

    _this_process_label = "ImplantMuonWorkChain"

    tab_titles = tl.List([])
    
    def get_muon_node(self):
        return self._get_child_outputs() # this gets: qepp.outputs.muonic
    
    def needs_findmuon_rendering(self):
        node = self.get_muon_node()
        if not any(key in node for key in ["findmuon"]):
            return False
        return True
    
    def needs_undi_rendering(self):
        node = self.get_muon_node()
        # Querybuilder to find node with a given label, outgoing from this node
        if not any(key in node for key in ["polarization"]):
            return False
        return True