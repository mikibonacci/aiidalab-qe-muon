"""Bands results view widgets

"""
from __future__ import annotations

from aiidalab_qe.common.panel import ResultPanel

import ipywidgets as ipw

from .utils_results import (
    produce_muonic_dataframe,
    produce_collective_unit_cell,
    SummaryMuonStructureBarWidget,
    SingleMuonStructureBarWidget
)

from aiida import orm

class Result(ResultPanel):

    title = "Muon spectroscopy"
    workchain_label = "muonic"

    def _update_view(self):
        
        if "muonic" in self.node.outputs: 
            if "findmuon" in self.node.outputs.muonic:
                
                dataframe = produce_muonic_dataframe(findmuon_output_node=self.node.outputs.muonic.findmuon)
                summarized_unit_cell = produce_collective_unit_cell(findmuon_output_node=self.node.outputs.muonic.findmuon)

                if dataframe is not None and summarized_unit_cell is not None:
                    first_index = dataframe.columns[0]  #<=== lowest energy unique site.
                    
                    childrens = [
                        SummaryMuonStructureBarWidget(orm.StructureData(pymatgen=summarized_unit_cell), df=dataframe,tags=summarized_unit_cell.tags),
                        SingleMuonStructureBarWidget(dataframe,first_index)]

                    # Create the summary button
                    summary_button = ipw.Button(
                        description='Summary of all unique muon sites',
                        disabled=False
                    )
                    summary_button.layout.width = "300px"

                    # Function to react to button click
                    def _show_summary(a):
                        muon_tab_results.children = [ipw.HBox([ipw.HTML("Select view mode for muonic outputs:"),
                                                summary_button,
                                                single_button]),childrens[0]]
                        
                        #hard coded selection of the button.
                        #single_button.disabled=False
                        #summary_button.disabled=True
                        single_button.style.button_color="white"
                        summary_button.style.button_color="lightgray"
                    summary_button.on_click(_show_summary)

                    # Create the single muon button
                    single_button = ipw.Button(
                        description='Single muon site',
                        disabled=False
                    )
                    single_button.layout.width = "300px"

                    # Function to react to button click
                    def _show_single(b):
                        muon_tab_results.children = [ipw.HBox([ipw.HTML("Select view mode for muonic outputs:"),
                                                summary_button,
                                                single_button]),childrens[1]]
                        
                        #hard coded selection of the button.
                        #single_button.disabled=True
                        #summary_button.disabled=False
                        single_button.style.button_color="lightgray"
                        summary_button.style.button_color="white"
                    single_button.on_click(_show_single)
                    
                    #tab widget
                    muon_tab_results = ipw.VBox(
                                children=[ipw.HBox([
                                    ipw.HTML("Select view mode for muonic outputs:"),
                                    summary_button,
                                    single_button]),]
                                    #childrens[0]]
                        #layout=ipw.Layout(min_height="250px"),
                    )
                    
                    self.children=[muon_tab_results]
                    
                
                
                
