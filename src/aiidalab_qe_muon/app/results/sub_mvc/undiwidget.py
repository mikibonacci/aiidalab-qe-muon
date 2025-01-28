import numpy as np
import base64
import pandas as pd

import copy

import ipywidgets as ipw
import plotly.graph_objects as go

from aiida import orm

from aiidalab_qe.common.widgets import LoadingWidget
from aiidalab_qe_muon.app.results.sub_mvc.undimodel import PolarizationModel

class UndiPlotWidget(ipw.VBox):
    """_summary_

    Trying to implement the MVC model (model, control, view).

    Control should manage both view and model.
    So, the value of the widgets are linked to the attibute of the model

    Args:
        model (PolarizationModel): The model that contains the data and the logic.
                                   Needs to already have loaded the nodes inside it.
                                   
    NB: you can put, as attribute, before rendering, the convergence_undi_widget, which is simply a UndiPlotWidget
    with the convergence analysis of the polarization data. It can be obtained from the model doing:
    
    ```python
    conv_undi_model = UndiModel(mode="analysis")
    convergence_undi_widget = UndiPlotWidget(
        model=conv_undi_model,
        node=muon_node,
    )
    ```
    """

    def __init__(self, model: PolarizationModel, node, **kwargs):

        super().__init__(
            children=[LoadingWidget("Loading widgets")],
            **kwargs,
        )
        self._model = model
        self._model.muon = node
        self.rendered = False
        
    def render(self):
        if self.rendered:
            return
        
        description = ipw.HTML(
            """
            <h3>Polarization data</h3>
            Here you can see the polarization data for the detected muon stopping sites. <br>
            It is possible to select several quantities:
            <ul>
            <li>sample orientation;</li>
            <li>magnetic field directions and magnitudes;</li>
            <li>Kubo-Toyabe plot.</li>
            </ul>
            Details on the approximations and code used, the isotope combinations and the convergence analysis are provided below.
            """
        )

        self._initial_view()

        self.fig = go.FigureWidget()
        self.init_undi_plots()

        if self._model.mode == "plot":
            self.plot_box = self.inject_tune_plot_box()
            
            selected_indexes_widget = ipw.HTML(
                f"Selected muon sites: {self._model.selected_indexes}",
            )
            ipw.dlink(
                (self._model, "selected_indexes"),
                (selected_indexes_widget, "value"),
                lambda x: f"Selected muon sites: {x}",
            )
            selected_indexes_widget.observe(self._on_selected_indexes_change, "value")
            
            table = self._model.create_html_table(
                first_row=["cluster index", "isotopes", "spins", "probability"],
            )
            self.cluster_isotopes_table = ipw.HTML(table)
            self.info_on_the_approximations = ipw.Accordion(
                children=[
                    ipw.HTML(
                        """
                        The approximations used in this plots are: ... <br>
                        You can find more information on the UNDI code here: ...
                        """
                    ),
                    ipw.VBox(
                        [
                            ipw.HTML(
                                "The average is performed considering the probabilities..."
                            ),
                            self.cluster_isotopes_table,
                        ],
                    ),
                ],
            )
            self.info_on_the_approximations.set_title(
                0, "Details on the approximations"
            )
            self.info_on_the_approximations.set_title(1, "Isotopes combinations")
            
            # I don't like so much this logic, but fine:
            if self.convergence_undi_widget:
                self.info_on_the_approximations.children += (self.convergence_undi_widget,)
                self.info_on_the_approximations.set_title(2, "Convergence analysis")
                
            self.info_on_the_approximations.selected_index = None  # Collapse by default

            download_data_button = ipw.Button(
                description="Download P(t) data in csv format",
                icon="download",
                button_style="primary",
                disabled=False,
                tooltip="Download polarization data with selected directions, for all the applied magnetic field magnitudes.",
                layout=ipw.Layout(width="auto"),
            )
            download_data_button.on_click(self._model._download_pol)
        

            self.children = [
                description,
                self.fig,
                selected_indexes_widget,
                ipw.HBox(
                    [
                        ipw.HTML("<b>Plot options:</b>"),
                        download_data_button,
                    ],
                    layout=ipw.Layout(justify_content="space-between"),
                ),
                self.plot_box,
                self.info_on_the_approximations, # I will render it in the MultipleUndiMVC
            ]
            if self.convergence_undi_widget:
                self.convergence_undi_widget.render()
            

            

        else:
            self.plotting_quantity = ipw.ToggleButtons(
                options=[
                    ("P(t)", "P"),
                    ("ΔP(t) = P(t) - Pᵣ(t)", "deltaP"),
                    ("100*ΔP(t)/Pᵣ(t)", "deltaP_rel"),
                ],
                value="P",
            )
            ipw.dlink(
                (self.plotting_quantity, "value"),
                (self._model, "plotting_quantity"),
            )
            self.plotting_quantity.observe(self._on_plotting_quantity_change, "value")


            self.children = [
                self.fig,
                self.plotting_quantity,
                ipw.HTML(
                    """
                                - Here you can check the convergence with respect to the maximum Hilbert space dimension (max<sub>hdim</sub>)
                                which is used to build the Hamiltonian containing the muon-nuclei interactions. For more details, please have a look here... <br>
                                - We considered a reference P<sub>r</sub>(t) computed using max<sub>hdim</sub>=10<sup>9</sup> (the same value used in the the 'Polarization plot' tab.). <br>
                                - If you think the results are not at convergence and/or need further improvement, you can contact the developers from the corresponding
                                <a href="https://github.com/mikibonacci/aiidalab-qe-muon" target="_blank">github page</a>.
                                """
                ),
            ]

        self.rendered = True

    def _initial_view(self):
        self._model.fetch_data() 
        self._model.get_data_plot()

    # view
    def _update_plot(
        self,
    ):
        """
        This will produce plots for both results of the polarization, both for the convergence of it.
        """

        self.fig.data = ()
        direction = self._model.directions
        field_direction = self._model.field_direction
        if self._model.mode == "plot":
            quantity_to_iterate = self._model.selected_fields
        else:
            quantity_to_iterate = self._model.max_hdims
        selected_indexes = self._model.selected_indexes
        ylabel=None

        for muon_index in selected_indexes:
            
            muon_index_string = f" (site {muon_index})" if len(selected_indexes) > 1 else ""
            #for index in range(len(self._model.muons[str(muon_index)].results)):
            for value in quantity_to_iterate:
                # shell_node = node #orm.load_node(2582)
                if self._model.mode == "plot":
                    index = self._model.muons[str(muon_index)].fields.index(value)
                    Bmod = self._model.muons[str(muon_index)].results[index][0]["B_ext"] * 1000  # mT
                    label = f"B<sub>ext</sub>={Bmod} mT"+muon_index_string
                    ydata = self._model.muons[str(muon_index)].data["y"][field_direction][index][
                        f"signal_{direction}"
                    ]
                    ylabel = "P(t)"
                    title = None
                elif self._model.mode == "analysis":
                    index = self._model.max_hdims.index(value)
                    to_be_plotted = self._model.plotting_quantity
                    Bmod = self._model.muons[str(muon_index)].results[index][0]["B_ext"] * 1000  # mT
                    label = f"max<sub>hdim</sub> = {self._model.max_hdims[index]}"

                    highest_res = self._model.muons[str(muon_index)].results[-1]

                    ydata = np.array(
                        self._model.muons[str(muon_index)].data["y"][field_direction][index][f"signal_{direction}"]
                    )
                    ylabel = "P(t)"
                    if "delta" in to_be_plotted:
                        ydata = np.array(highest_res[0][f"signal_{direction}_lf"]) - ydata
                        ylabel = "ΔP(t)"
                    if "rel" in to_be_plotted:
                        ydata /= 100 * np.array(highest_res[0][f"signal_{direction}_lf"])
                        ylabel = "Δ<sub>%</sub>P(t)"
                    title = None  # "$$\Delta P(t) = P_{max\_hdim=10^9}(t) - P(t)$$"

                self.fig.add_trace(
                    go.Scatter(
                        x=self._model.muons[str(muon_index)].data["x"],
                        y=ydata,
                        name=label,
                        mode="lines",
                        marker=dict(size=10),
                        line=dict(width=2),
                    ),
                )
                self.fig.update_layout(yaxis=dict(title=ylabel))
                
        if not self.rendered:
            title = None
            self.fig.update_layout(
                barmode="overlay",
                yaxis=dict(title=ylabel),
                xaxis=dict(title="time (μs)"),
                title={
                    "text": title,
                    "x": 0.5,  # Center the title
                    "xanchor": "center",
                    "yanchor": "top",
                },
                margin=dict(
                    t=5 if not title else 35, r=20
                ),  # Reduce the top margin
                # width=500, # Width of the plot
                # height=500, # Height of the plot
                font=dict(  # Font size and color of the labels
                    size=12,
                    color="#333333",
                ),
                plot_bgcolor="gainsboro",  # Background color of the plot
                # paper_bgcolor='white', # Background color of the paper
                legend=dict(
                    x=0.02,  # x position of the legend
                    y=0.02,  # y position of the legend
                    traceorder="normal",
                    bgcolor="rgba(255, 255, 255, 0.5)",  # Background color with transparency
                    # bordercolor='Black',
                    # borderwidth=1
                ),
            )
                
        self._on_add_KT_change()
        
    # view
    def inject_tune_plot_box(
        self,
    ):
        sample_description = ipw.HTML(
            """
            <b>Sample direction</b>
            """,
            layout=ipw.Layout(
                width="80%",
            ),
        )

        sample_dir = ipw.RadioButtons(
            options=["x", "y", "z", "powder"],
            value=self._model.directions,
            layout=ipw.Layout(
                width="80%",
            ),
        )
        ipw.dlink(
            (sample_dir, "value"),
            (self._model, "directions"),
        )
        sample_dir.observe(self._on_sampling_dir_change, "value")

        add_KT = ipw.Checkbox(
            value=False,
            description="Add Kubo-Toyabe in the plot",
            disabled=False,
            indent=False,
            layout=ipw.Layout(
                width="80%",
            ),
        )
        ipw.dlink(
            (add_KT, "value"),
            (self._model, "plot_KT"),
        )
        add_KT.observe(self._on_add_KT_change, "value")

        field_direction_desc = ipw.HTML(
            """
            <b>B<sub>ext</sub> direction</b>
            """
        )

        field_directions_ddown = ipw.RadioButtons(
            options=[("Longitudinal", "lf"), ("Transverse", "tf")],
            value="lf",  # Default value
            disabled=False,
            layout=ipw.Layout(
                width="90%",
            ),
        )
        ipw.dlink(
            (field_directions_ddown, "value"),
            (self._model, "field_direction"),
        )
        field_directions_ddown.observe(self._on_field_direction_change, "value")


        field_magnitude_desc = ipw.HTML(
            """
            <b>B<sub>ext</sub> magnitude (mT)</b> <br>
            select mutiple field values using CTRL+cursor.
            """
        )
        fields = copy.deepcopy(self._model.fields)
        fields.sort()
        field_magnitudes = ipw.SelectMultiple(
            options=fields,
            value=self._model.selected_fields,
            disabled=False,
            layout=ipw.Layout(width="200px", height="100px"),
        )
        ipw.dlink(
            (field_magnitudes, "value"),
            (self._model, "selected_fields"),
        )
        field_magnitudes.observe(self._on_field_magnitudes_change, "value")

        plot_box = ipw.HBox(
            [
                ipw.VBox(
                    [
                        sample_description,
                        sample_dir,
                        add_KT,
                    ],
                    layout=ipw.Layout(
                        width="30%",
                    ),
                ),
                ipw.VBox(
                    [
                        field_direction_desc,
                        field_directions_ddown,
                    ],
                    layout=ipw.Layout(height="100%", width="30%"),
                ),
                ipw.VBox(
                    [
                        field_magnitude_desc,
                        field_magnitudes,
                    ],
                    layout=ipw.Layout(height="100%", width="40%"),
                ),
            ],
            layout=ipw.Layout(width="100%", border="2px solid black", padding="10px"),
        )

        return plot_box

    # control of view
    def _on_sampling_dir_change(self, change):
        self._update_plot()

    # control of view
    def _on_field_direction_change(self, change):
        self._update_plot()

    # control of view
    def _on_field_magnitudes_change(self, change):
        self._update_plot()

    # for the convergence analysis:
    def _on_plotting_quantity_change(self, change):
        self._update_plot()
        
    # if selected_muons in the findmuonwidget changes, we need to update the plot also here:
    def _on_selected_indexes_change(self, change):
        self._update_plot()
    
    def _on_add_KT_change(self, change = None):
        
        for muon_index in self._model.selected_indexes:
            muon_index_string = f" (site {muon_index})" if len(self._model.selected_indexes) > 1 else ""
            if self._model.plot_KT:
                # add the trace
                if self._model.muons[str(muon_index)].KT_output:
                    self.KT_trace = go.Scatter(
                            x=self._model.muons[str(muon_index)].KT_output["t"],
                            y=self._model.muons[str(muon_index)].KT_output["KT"],
                            name="Kubo-Toyabe" + muon_index_string,
                            mode="lines",
                            marker=dict(size=10),
                            line=dict(width=2),
                        )
                    self.fig.add_trace(self.KT_trace)
            else:
                # remove the trace
                if hasattr(self, "KT_trace"): 
                    self.fig.data = tuple([trace for trace in self.fig.data[:-1]])
                    delattr(self, "KT_trace")
        
    def init_undi_plots(self):
        self._update_plot()
