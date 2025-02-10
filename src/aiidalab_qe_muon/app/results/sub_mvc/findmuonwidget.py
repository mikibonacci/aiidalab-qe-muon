import ipywidgets as ipw
import plotly.graph_objects as go

from aiidalab_qe_muon.app.results.sub_mvc.findmuonmodel import FindMuonModel

from aiidalab_qe.common.widgets import TableWidget
from aiidalab_qe.common.widgets import LoadingWidget
from aiidalab_qe.common.infobox import InfoBox

from aiidalab_widgets_base.viewers import StructureDataViewer

from aiidalab_qe_muon.utils.data import (
    dictionary_of_names_for_html, 
    no_Bfield_sentence,
    color_code,
    unit_cell_explanation_text
)



class FindMuonWidget(ipw.VBox):
    """Widget for displaying FindMuonWorkChain results.
    
    Here, the controller for displaying the data is defined. 
    I don't think we should define it in the FindMuonModel: the model
    should only control data manipulation, not view manipulation.
    If we need to process the data, we should do it in the controller of the model.
    But if we need to display the data, we should do it in the controller of the view.
    """

    def __init__(self, model: FindMuonModel, node: None, **kwargs):
        super().__init__(
            children=[LoadingWidget("Loading muon resting sites results")],
            **kwargs,
        )
        self._model = model

        self.rendered = False
        self._model.muon = node

    def render(self):
        if self.rendered:
            return
                        
        self._initial_view() # fetch data and maybe some initial choice (if only one site, switch...)
        
        self.title = ipw.HTML("""
            <h3>Muon stopping sites</h3>
            Inspect the results by selecting different rows in the following table, each of them
            corresponding to a different detected muon sites. Structures are 
            ordered by increasing total energy with respect to the lowest one 
            (labeled as "A"). <br>
            If you use this results in your work, please cite the following paper: <a href="https://doi.org/10.1039/D4DD00314D"
            target="_blank">Onuorah et al., Digital Discovery, 2025</a>, which describes the approach used here to find the muon sites (as implemented
            in the <b><a href="https://positivemuon.github.io/aiida-muon/" target="_blank">aiida-muon</b></a> plugin).
        """)
        
        if self._model.supercell_was_small:
            self.title.value = self.title.value + "<br><b>Warning:</b> The supercell used for the calculations was too small to properly represent the muon sites."
        
        if self._model.no_B_in_DFT:
            self.title.value = self.title.value + no_Bfield_sentence
        
        self.table = TableWidget(layout=ipw.Layout(width='auto', height='auto'))
        ipw.dlink(
            (self._model, "table_data"), 
            (self.table, "data"),
        )
        self._update_table()
        self.table.selected_rows = [0]
        self.table.observe(self._on_selected_rows_change,"selected_rows")
        
        self.advanced_table = ipw.Checkbox(
            description="Advanced table mode",
            button_style="primary",
            value=False,
        )
        ipw.dlink(
            (self.advanced_table, "value"),
            (self._model, "advanced_table"),
        )
        self.advanced_table.observe(self.on_advanced_table_change, names="value")
        
        self.about_toggle = ipw.ToggleButton(
            layout=ipw.Layout(width="auto"),
            button_style="",
            icon="info",
            value=False,
            description="Table legend",
            tooltip="Info on the table",
            disabled=False,
        )
        self.about_toggle.observe(self.display_table_legend, names="value")
        
        self.table_legend = ipw.HTML("")
        ipw.dlink(
            (self._model, "table_legend_text"),
            (self.table_legend, "value"),
        )
        self.table_legend_infobox = InfoBox(
            children=[self.table_legend],
        )
        self.table_legend_infobox.layout.display = "none"

        
        self.compare_muons_button = ipw.Checkbox(
            description="Compare muon sites mode",
            button_style="primary",
            value=False,
        )
        ipw.dlink(
            (self.compare_muons_button, "value"),
            (self._model, "selected_view_mode"),
            lambda value: 1 if value else 0,
        )
        self.compare_muons_button.observe(self._compare_mode, names="value")
        self.about_unit_cell_toggle = ipw.ToggleButton(
            layout=ipw.Layout(width="auto"),
            button_style="",
            icon="info",
            value=False,
            description="About the compare mode",
            disabled=False,
        )
        self.about_unit_cell_toggle.observe(self.display_unit_cell_explanation, names="value")
        
        self.unit_cell_explanation = ipw.HTML(unit_cell_explanation_text)
        self.unit_cell_explanation_infobox = InfoBox(
            children=[self.unit_cell_explanation],
        )
        self.unit_cell_explanation_infobox.layout.display = "none"
        
        
        self.structure_view_container = ipw.VBox(
            children=[
                StructureDataViewer(self._model.structure),
            ],
            layout=ipw.Layout(
                flex="1",
            ),
        )
        #self.structure_view_container.children[0].observe(
        #    self._on_displayed_selection_change, 
        #    names="displayed_selection"
        #    )
        
                
        download_button = ipw.Button(
            description="Download data", 
            tooltip="Download the all the resting sites data",
            icon="download", 
            button_style="primary"
        )
        download_button.on_click(self.download_data)
        
        self.barplot = go.FigureWidget()
        self.barplot_container = ipw.VBox([self.barplot])
        self._update_barplot()
        
        self.children = [
            self.title,
            self.table,
            ipw.HBox([self.advanced_table, self.about_toggle, download_button,],),
            self.table_legend_infobox,
            self.structure_view_container,
            ipw.HBox([
                self.compare_muons_button,
                self.about_unit_cell_toggle,
            ],),
            self.unit_cell_explanation_infobox,
            self.barplot_container,
        ]
        
        self.rendered = True
        
    def _initial_view(self):
        self._model.fetch_data()
        self._model.select_structure()
        self._model.generate_table_legend()
        
    def on_advanced_table_change(self, change):
        self._model.generate_table_legend()
        self._model._generate_table_data()
        
    def display_table_legend(self, change):
        self.table_legend_infobox.layout.display = "block" if change["new"] else "none"
        
    def display_unit_cell_explanation(self, change):
        self.unit_cell_explanation_infobox.layout.display = "block" if change["new"] else "none"
    
    def _on_selected_muons_change(self):
        self._update_structure_view()
        self._update_picked_atoms()
        self._update_barplot()
        #self._update_table()
        
    def _on_selected_rows_change(self, change):
        
        if not self.compare_muons_button.value:
            self.table.selected_rows = self.table.selected_rows[-1:]
            
        self._model.selected_muons = [
            int(self._model.findmuon_data["table"].iloc[index].muon_index) # because are stored as strings!
            for index in self.table.selected_rows
            ]
        
        self._on_selected_muons_change()

    def _on_displayed_selection_change(self, change):
        if self.compare_muons_button.value:
            self._model.selected_muons = [
                self._model.findmuon_data["table"][self._model.findmuon_data["table"].muon_index_global_unitcell == index].muon_index.values
                for index in self.structure_view_container.children[0].displayed_selection
                ]
        
    def _compare_mode(self, _=None):
        if self.compare_muons_button.value:
            self._model.selected_muons = self._model.muon_index_list
        else:
            self._model.selected_muons = self._model.muon_index_list[0:1]
        self._on_selected_rows_change(None)
    
    def _update_structure_view(self, _=None):
        self._model.select_structure() # switch between the structure to be displayed
        #self.structure_view_container.children = [StructureDataViewer(self._model.structure)]
        self.structure_view_container.children[0].structure = self._model.structure
    
    def _update_picked_atoms(self, _=None):
        if self.compare_muons_button.value:
            selected_muons = [
                self._model.findmuon_data["table"].loc[index_selected].muon_index_global_unitcell - 1
                for index_selected in self._model.selected_muons
                ]
            self.structure_view_container.children[0].displayed_selection = selected_muons
        else:
            self.structure_view_container.children[0].displayed_selection = []
            
    def _update_barplot(self, _=None):
        
        data_to_plot = self._model.get_data_plot() # to have more compact code below
        
        if not '|B<sub>total</sub>| (T)' in data_to_plot["entry"]:
            # hide the figure and return
            self.barplot_container.layout.display = "none"
            return
            
        # if not B field is there, we can also avoid to render it.
        if not self.rendered:
            for entry, color, data_y in zip(data_to_plot["entry"], data_to_plot["color_code"], data_to_plot["y"]):
                
                if entry == 'ΔE<sub>total</sub> (meV)':
                    self.barplot.add_trace(
                        go.Scatter(
                            x=data_to_plot["x"],
                            y=data_y,
                            name=entry,
                            yaxis='y',
                            #mode="markers+lines",
                            marker=dict(color=color, opacity=0.8),
                        )
                    )
                else:
                    self.barplot.add_trace(
                        go.Bar(
                            x=data_to_plot["x"],
                            y=data_y,
                            name=entry,
                            yaxis='y2',
                            #mode="markers+lines",
                            marker=dict(color=color, opacity=0.65),
                        )
                    )
            
            color_tot_E = data_to_plot["color_code"][data_to_plot["entry"].index('ΔE<sub>total</sub> (meV)')]
            self.barplot.update_layout(
            # title='Summary',
            barmode="group",
            xaxis=dict(
                title="Muon label",
                tickmode="linear",
                dtick=1,
                #titlefont=dict(color="mediumslateblue"),
                #tickfont=dict(color="mediumslateblue"),
            ),
            yaxis=dict(
                title='ΔE<sub>total</sub> (meV)',
                titlefont=dict(color=color_tot_E),
                tickfont=dict(color=color_tot_E),
                side="right",
                showticklabels=True,
                showgrid=False,
            ),
            legend=dict(x=0.01, y=1, xanchor="left", yanchor="top"),
            # width=400, # Width of the plot
            # height=500, # Height of the plot
            font=dict(  # Font size and color of the labels
                size=12,
                color="#333333",
            ),
            plot_bgcolor="gainsboro",  # Background color of the plot
            # paper_bgcolor='white', # Background color of the paper
            # bargap=0.000001, # Gap between bars
            # bargroupgap=0.4, # Gap between bar groups
            )
            if '|B<sub>total</sub>| (T)' in data_to_plot["entry"]:
                color_B = data_to_plot["color_code"][data_to_plot["entry"].index('|B<sub>total</sub>| (T)')]
            else:
                color_B = "blue"
            self.barplot.update_layout(
            yaxis2=dict(
                title='|B<sub>total</sub>| (T)',
                titlefont=dict(color=color_B),
                tickfont=dict(color=color_B),
                overlaying="y",
                side="left",
                showticklabels=True,
                showgrid=False,
                ),
            )
                    
        elif self.rendered:
            data_to_plot = self._model.get_data_plot()
            for i, (entry, color, data_y) in enumerate(zip(data_to_plot["entry"], data_to_plot["color_code"], data_to_plot["y"])):
                self.barplot.data[i].x = data_to_plot["x"]
                self.barplot.data[i].y = data_y
           
    def _update_table(self, _=None):
        self._model._generate_table_data()
        
    def download_data(self, _=None):
        """Function to download the data."""
        self._model.download_data()
        
        