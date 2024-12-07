"""Muonic results view widgets"""

from aiidalab_qe_muon.app.results.model import MuonResultsModel
from aiidalab_qe.common.panel import ResultsPanel

from aiidalab_qe_muon.app.results.sub_mvc.findmuonmodel import FindMuonModel
from aiidalab_qe_muon.app.results.sub_mvc.findmuonwidget import FindMuonWidget

import ipywidgets as ipw

class MuonResultsPanel(ResultsPanel[MuonResultsModel]):
    
    """General results panel for muons
    
    This panel is used to display the results of the muon spectroscopy calculations.
    for now, it only displays the results of the FindMuonWorkChain and the Undi WorkGraph.
    This is why we call only one model and one widget, but in principle, in the future, it 
    can hosts also Neb and others.
    """
    
    title = "Muonic"
    identifier = "munonic"
    workchain_labels = ["muon"]
    
    def render(self):
        if self.rendered:
            return

        muon_node = self._model.get_muon_node()

        needs_findmuon_rendering = self._model.needs_findmuon_rendering()
        if needs_findmuon_rendering:
            muon_model = FindMuonModel()
            muon_widget = FindMuonWidget(
                model=muon_model,
                node=muon_node,
            )

        self.children = [muon_widget]
        
        for child in self.children:
            child.render()
            
        self.rendered = True
