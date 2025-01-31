import ipywidgets as ipw
import plotly.graph_objects as go

from aiidalab_qe_muon.app.results.sub_mvc.findmuonmodel import FindMuonModel

from aiidalab_qe.common.widgets import TableWidget
from aiidalab_qe.common.widgets import LoadingWidget

from aiidalab_widgets_base.viewers import StructureDataViewer


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
        
        description = ipw.HTML("""
            <h3>Muon resting sites</h3>
            Inspect the results of the search for muon resting sites. <br
            <ul>
            <li>For each muon site, the table and plot show several quantities, such as:</li>
                <ul>
                <li>Total energy;</li>
                <li>Magnetic field at the muon site (if computed);</li>
                <li>Muon site index.</li>
                </ul>
            </li>
            <li>Click on a row in the table to inspect the corresponding muon site in the structure view.</li>
            <li>Click on the "Visualize all sites in the unit cell" checkbox to visualize all muon sites in the unit cell.</li>
            </ul>
        """)
        
        selected_muons = ipw.SelectMultiple(
            options=self._model.muon_index_list,
            value=self._model.muon_index_list,
            layout=ipw.Layout(width='50%')
        )
        ipw.link(
            (selected_muons, "value"),
            (self._model, "selected_muons"),
        )
        selected_muons.observe(self._on_selected_muons_change, names="value")
        
        self.select_all_button = ipw.Checkbox(
            #description="Visualize all sites in the unit cell",
            button_style="primary",
            value=True,
            layout=ipw.Layout(width='50%', margin='0px 0px 0px 0px'),
        )
        ipw.dlink(
            (self.select_all_button, "value"),
            (self._model, "selected_view_mode"),
            lambda value: 1 if value else 0,
        )
        self.select_all_button.observe(self._select_all, names="value")
        
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
        
        self.table = TableWidget(layout=ipw.Layout(width='100%'))
        ipw.dlink(
            (self._model, "table_data"), 
            (self.table, "data"),
        )
        self._update_table()
        self.table.observe(self._on_selected_rows_change,"selected_rows")
        
        download_button = ipw.Button(
            description="Download Table", 
            tooltip="Download the data for the selected muons in CSV format",
            icon="download", 
            button_style="primary"
        )
        download_button.on_click(self.download_data)
        
        self.barplot = go.FigureWidget()
        self.barplot_container = ipw.VBox([self.barplot])
        self._update_barplot()
        
        self.children = [
            ipw.HBox([
                description,
                ipw.VBox([
                    ipw.HTML("Select muon indexes:"),
                    selected_muons,
                    ipw.HBox(
                        [
                            ipw.HTML("Visualize all sites in the unit cell: ", layout=ipw.Layout(width="100%"),),
                            self.select_all_button
                        ],
                        ),
                    ],
                    ),
                ]),
            self.structure_view_container,
            self.table,
            download_button,
            self.barplot_container,
        ]
        
        self.rendered = True
        
    def _initial_view(self):
        self._model.fetch_data()
        self._model.select_structure()
    
    def _on_selected_muons_change(self, change):
        self._update_structure_view()
        self._update_picked_atoms()
        self._update_barplot()
        #self._update_table()
        
    def _on_selected_rows_change(self, change):
        self._model.selected_muons = [
            int(self._model.findmuon_data["table"].iloc[index].muon_index) # because are store as strings!
            for index in self.table.selected_rows
            ]
        
    def _on_displayed_selection_change(self, change):
        if self.select_all_button.value:
            self._model.selected_muons = [
                self._model.findmuon_data["table"][self._model.findmuon_data["table"].muon_index_global_unitcell == index].muon_index.values
                for index in self.structure_view_container.children[0].displayed_selection
                ]
        
    def _select_all(self, _=None):
        
        if self.select_all_button.value:
            self._model.selected_muons = self._model.muon_index_list
    
    def _update_structure_view(self, _=None):
        self._model.select_structure() # switch between the structure to be displayed
        #self.structure_view_container.children = [StructureDataViewer(self._model.structure)]
        self.structure_view_container.children[0].structure = self._model.structure
    
    def _update_picked_atoms(self, _=None):
        if self.select_all_button.value:
            selected_muons = [
                self._model.findmuon_data["table"].loc[index_selected].muon_index_global_unitcell - 1
                for index_selected in self._model.selected_muons
                ]
            self.structure_view_container.children[0].displayed_selection = selected_muons
        else:
            self.structure_view_container.children[0].displayed_selection = []
            
    def _update_barplot(self, _=None):
        
        data_to_plot = self._model.get_data_plot() # to have more compact code below
        
        if not "B_T_norm" in data_to_plot["entry"]:
            # hide the figure and return
            self.barplot_container.layout.display = "none"
            self.rendered = True
            return
            
        # if not B field is there, we can also avoid to render it.
        if not self.rendered:
            for entry, color, data_y in zip(data_to_plot["entry"], data_to_plot["color_code"], data_to_plot["y"]):
                
                if entry == "ΔE<sub>total</sub> (eV)":
                    trace_callback = go.Scatter
                else:
                    trace_callback = go.Bar
                
                self.barplot.add_trace(
                    trace_callback(
                        x=data_to_plot["x"],
                        y=data_y,
                        name=entry,
                        mode="markers+lines",
                        marker=dict(color=color),
                    )
                )
            
            color_tot_E = data_to_plot["color_code"][data_to_plot["entry"].index("ΔE<sub>total</sub> (eV)")]
            self.barplot.update_layout(
            # title='Summary',
            barmode="group",
            xaxis=dict(
                title="Muon site index",
                tickmode="linear",
                dtick=1,
                #titlefont=dict(color="mediumslateblue"),
                #tickfont=dict(color="mediumslateblue"),
            ),
            yaxis=dict(
                title="ΔE<sub>total</sub> (eV)",
                titlefont=dict(color=color_tot_E),
                tickfont=dict(color=color_tot_E),
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
            if "B_T_norm" in data_to_plot["entry"]:
                color_B = data_to_plot["color_code"][data_to_plot["entry"].index("|B<sub>total</sub>| (T)")]
            else:
                color_B = "blue"
            self.barplot.update_layout(
            yaxis2=dict(
                title="B (T)",
                titlefont=dict(color=color_B),
                tickfont=dict(color=color_B),
                overlaying="y",
                side="right",
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
        b64_str, file_name = self._model._prepare_data_for_download()
        self._model._download(payload=b64_str, filename=file_name)