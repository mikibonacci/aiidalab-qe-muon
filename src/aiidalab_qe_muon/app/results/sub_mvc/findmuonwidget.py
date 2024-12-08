import ipywidgets as ipw
import plotly.graph_objects as go

from aiidalab_qe_muon.app.results.sub_mvc.findmuonmodel import FindMuonModel


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
        
        selected_muons = ipw.SelectMultiple(
                description="Select muon sites:",
                options=self._model.muon_index_list,
                value=[self._model.muon_index_list[0]],
            )
        ipw.link(
            (selected_muons, "value"),
            (self._model, "selected_muons"),
        )
        selected_muons.observe(self._on_selected_muons_change, names="value")
        
        select_all_button = ipw.Button(
            description="Select all",
            button_style="primary",
        )
        select_all_button.on_click(self._select_all)
        
        self.structure_viewer = ipw.VBox(
            children=[
                StructureDataViewer(self._model.structure),
            ],
            layout=ipw.Layout(
                flex="1",
            ),
        )
        
        self.barplot = go.FigureWidget()
        self._update_barplot()
        
        self.children = [
            selected_muons,
            select_all_button,
            self.structure_viewer,
            self.barplot,
        ]
        
        self.rendered = True
        
    def _initial_view(self):
        self._model.fetch_data()
        self._model.select_structure()
    
    def _on_selected_muons_change(self, change):
        self._update_structure_view()
        self._update_barplot()
        self._update_table()
        
    def _select_all(self, _=None):
        self._model.selected_muons = self._model.muon_index_list
    
    def _update_structure_view(self, _=None):
        self._model.select_structure() # switch between the structure to be displayed
        self.structure_viewer.children = [StructureDataViewer(self._model.structure)]
        
    def _update_barplot(self, _=None):
        
        data_to_plot = self._model.get_data_plot() # to have more compact code below
        if not self.rendered:
            for entry, color, data_y in zip(data_to_plot["entry"], data_to_plot["color_code"], data_to_plot["y"]):
                self.barplot.add_trace(
                    go.Scatter(
                        x=data_to_plot["x"],
                        y=data_y,
                        name=entry,
                        mode="markers+lines",
                        marker=dict(color=color),
                    )
                )
            
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
                titlefont=dict(color=data_to_plot["color_code"]["delta_E"]),
                tickfont=dict(color=data_to_plot["color_code"]["delta_E"]),
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
            #if "B_T_norm" in data_to_plot["entry"]:
            self.barplot.update_layout(
            yaxis=dict(
                title="B (T)",
                titlefont=dict(color="blue"),
                tickfont=dict(color="blue"),
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
        pass