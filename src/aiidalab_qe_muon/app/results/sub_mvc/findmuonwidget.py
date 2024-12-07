import ipywidgets as ipw
from aiidalab_qe_muon.app.results.sub_mvc.findmuonmodel import FindMuonModel
from aiidalab_qe.common.widgets import LoadingWidget

from aiidalab_widgets_base.viewers import StructureDataViewer


class FindMuonWidget(ipw.VBox):
    """
    Widget for displaying FindMuonWorkChain results
    """

    def __init__(self, model: FindMuonModel, node: None, **kwargs):
        super().__init__(
            children=[LoadingWidget("Loading widgets")],
            **kwargs,
        )
        self._model = model

        self.rendered = False
        self._model.muon = node

    def render(self):
        if self.rendered:
            return
        
        self._initial_view() # fetch data and maybe some initial choice (if only one site, switch...)
        
        selected_indexes = ipw.SelectMultiple(
                description="Select muon sites:",
                options=self._model.muon_index_list,
                value=[self._model.muon_index_list[0]],
            )
        ipw.link(
            (selected_indexes, "value"),
            (self._model, "selected_indexes"),
        )
        selected_indexes.observe(self._on_selected_indexes_change, names="value")
        
        self.structure_viewer = ipw.VBox(
            children=[
                StructureDataViewer(self._model.structure),
            ],
            layout=ipw.Layout(
                flex="1",
            ),
        )
        
        self.children = [
            selected_indexes,
            self.structure_viewer
        ]
        
        self.rendered = True
        
    def _initial_view(self):
        self._model.fetch_data()
        self._model.select_structure()
    
    def _on_selected_indexes_change(self, change):
        self._model.select_structure() # switch between the structure to be displayed
        self.structure_viewer.children = [StructureDataViewer(self._model.structure)]
        