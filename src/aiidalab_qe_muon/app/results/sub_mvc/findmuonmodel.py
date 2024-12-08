from aiidalab_qe.common.mvc import Model
import traitlets as tl
from aiida.common.extendeddicts import AttributeDict
import numpy as np
import base64
import json
from IPython.display import display

from aiidalab_qe_muon.utils.export_findmuon import export_findmuon_data
from aiidalab_qe_muon.utils.data import dictionary_of_names_for_html, color_code

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
    selected_muons = tl.List(
        trait=tl.Int(),
    )
    selected_view_mode = tl.Int(0)
    structure = tl.Union(
        [
            tl.Instance(ase.Atoms),
            tl.Instance(orm.StructureData),
        ],
        allow_none=True,
    )
    html_table = tl.Unicode("")
    
    def fetch_data(self):
        """Fetch the findmuon data from the FindMuonWorkChain outputs."""
        self.findmuon_data = export_findmuon_data(self.muon.findmuon)
        self.muon_index_list = self.findmuon_data["table"].index.tolist()
        self.selected_muons = [self.muon_index_list[0]]

    def select_structure(self):
        """Select a structure to be displayed.
        
        if we have multiple sites selected, we need to show the unrelaxed unit cell with all sites.
        Otherwise, we show the relaxed supercell with the single selected site.
        And then in the view we select only the one we want to inspect.
        """
        if len(self.muon_index_list) == 1:
            self.structure = orm.load_node(self.findmuon_data["table"].loc[self.muon_index_list[0],"structure_pk"])
        elif len(self.selected_muons) == 1 and self.selected_view_mode == 0:
            self.structure = orm.load_node(self.findmuon_data["table"].loc[self.selected_muons[0],"structure_pk"])
        elif len(self.selected_muons) > 1:
            self.structure = self.findmuon_data["unit_cell"]
    
    def convert_label_to_html(self, entry) -> str:
        # to have nice names in the html, instead of the column names.
        return dictionary_of_names_for_html[entry]
    
    def get_data_plot(self) -> dict:
        """Get the data for the plot.
        
        This method is called by the controller to get the data for the plot.
        I put it in the model as it can also be used to reorganize the data for other
        purposes than the view.
        """
        
        self.data_plot = {
            "x":self.selected_muons,
            "y":[],
            "entry":[],
            "color_code":[],
        }
        
        entries = ["delta_E", "B_T_norm", "Bdip_norm", "hyperfine_norm"]
        
        self.data_plot["y"] = [
            self.findmuon_data["table"].loc[self.selected_muons, entry].tolist() for entry in entries
            if entry in self.findmuon_data["table"].columns.tolist()
        ]
        
        self.data_plot["entry"] = [
            self.convert_label_to_html(entry) for entry in entries
            if entry in self.findmuon_data["table"].columns.tolist()
        ]
        
        self.data_plot["color_code"] = [
            color_code[entry] for entry in entries
            if entry in self.findmuon_data["table"].columns.tolist()
        ]
                
        return self.data_plot
    
    def _generate_html_table(self,) -> str:
        """Generate an html table from the selected data.
        
        This method is called by the controller to get the html table.
        """
        self.html_table = self.findmuon_data["table"].loc[self.selected_muons].to_html()
        
    def _prepare_data_for_download(self) -> str:
        """Prepare the data for download.
        
        This method is called by the controller to get the data for download.
        """
        # prepare the data for download as csv file
        data = base64.b64encode(self.findmuon_data['table'].to_csv(index=True).encode()).decode()
        formula = orm.load_node(self.findmuon_data["table"].loc[self.muon_index_list[0],"structure_pk"]).get_formula()
        filename = f"Summary_{formula}_muon_{'_'.join([str(muon_index) for muon_index in self.selected_muons])}.csv"
        return data, filename
           