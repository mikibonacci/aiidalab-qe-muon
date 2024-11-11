import numpy as np

import ipywidgets as ipw
import plotly.graph_objects as go

from aiidalab_qe_muon.app.undi_interface.model import PolarizationModel


def create_html_table(matrix, first_row=[]):
    """
    Create an HTML table representation of a Nx3 matrix. N is the number of isotope mixtures.

    :param matrix: List of lists representing an Nx3 matrix
    :return: HTML table string
    """
    html = '<table border="1" style="border-collapse: collapse;">'
    for cell in first_row[1:]:
        html += f'<td style="padding: 5px; text-align: center;">{cell}</td>'
    html += "</tr>"
    for row in matrix:
        html += "<tr>"
        for cell in row[1:]:
            html += f'<td style="padding: 5px; text-align: center;">{cell}</td>'
        html += "</tr>"
    html += "</table>"
    return html


class UndiPlotWidget(ipw.VBox):
    """_summary_

    Trying to implement the MVC model (model, control, view).

    Control should manage both view and model.
    So, the value of the widgets are linked to the attibute of the model

    Args:
        ipw (_type_): _description_
    """

    def __init__(self, model=PolarizationModel(), **kwargs):
        # from aiidalab_qe.common.widgets import LoadingWidget # when lazy-loading is there.

        super().__init__(
            # children=[LoadingWidget("Loading Polarization panel")], # when lazy-loading is there.
            **kwargs,
        )
        self.rendered = False
        self._model = model

    def render(self):
        if self.rendered:
            return

        self._model.prepare_data_for_plots()
        self.fig = go.FigureWidget()
        self.produce_undi_plots()

        if self._model.mode == "plot":
            self.plot_box = self.tuning_plot_box()

            table = create_html_table(
                self._model.create_cluster_matrix(),
                first_row=["cluster index", "isotopes", "spins", "probability"],
            )
            self.cluster_isotopes_table = ipw.HTML(table)

            self.children = [
                ipw.HBox(
                    [
                        self.fig,
                        self.plot_box,
                    ],
                ),
                ipw.HTML("Isotopes combination considered in this calculation:"),
                self.cluster_isotopes_table,
            ]

            self.rendered = True

        else:
            self.children = [
                ipw.HBox(
                    [
                        self.fig,
                        ipw.HTML("Convergence analysis..."),
                    ],
                ),
            ]

            self.rendered = True

    # view
    def produce_undi_plots(
        self,
    ):
        """
        This will produce plots for both results of the polarization, both for the convergence of it.
        """

        self.fig.data = ()
        direction = self._model.directions

        for index in range(len(self._model.nodes)):
            # shell_node = node #orm.load_node(2582)

            if self._model.mode == "plot":
                Bmod = self._model.results[index][0]["B_ext"] * 1000  # mT
                label = f"B<sub>ext</sub>={Bmod} mT"
                ydata = self._model.data["y"][index][f"signal_{direction}"]
                ylabel = "P(t)"
                title = None
            elif self._model.mode == "analysis":
                import json

                Bmod = self._model.results[index][0]["B_ext"] * 1000  # mT
                label = f"max<sub>hdim</sub> = {self._model.nodes[index].inputs.nodes.max_hdim.value}"
                highest_res = json.loads(
                    self._model.nodes[-1].outputs.results_json.get_content()
                )
                ydata = np.array(highest_res[0][f"signal_{direction}_lf"]) - np.array(
                    self._model.data["y"][index][f"signal_{direction}"]
                )
                title = "$$\Delta P(t) = P_{max\_hdim=10^9}(t) - P(t)$$"
                ylabel = "$$\Delta P(t)$$"

            if not self.rendered:
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

            self.fig.add_trace(
                go.Scatter(
                    x=self._model.data["x"],
                    y=ydata,
                    name=label,
                    mode="lines",
                    marker=dict(size=10),
                    line=dict(width=2),
                ),
            )

    # view
    def tuning_plot_box(
        self,
    ):
        sample_dir = ipw.ToggleButtons(
            options=["x", "y", "z", "powder"],
            value=self._model.directions,
            description="(a) Sampling directions:",
            style={"description_width": "initial"},
        )

        update_button = ipw.Button(description="Replot", disabled=True)

        field_directions_ddown = ipw.Dropdown(
            options=[("Longitudinal", "lf"), ("Transverse", "tf")],
            value="lf",  # Default value
            description="B<sub>ext</sub> is: ",
            disabled=False,
        )
        field_directions_ddown.observe(self._on_field_direction_change, "value")

        plot_box = ipw.VBox(
            [
                sample_dir,
                update_button,
                field_directions_ddown,
            ],
            layout=ipw.Layout(width="40%"),
        )
        sample_dir.observe(self._on_sampling_dir_change, "value")
        update_button.on_click(self._update_plot)  # the on_* is already in on_click.

        return plot_box

    # control of view
    def _on_sampling_dir_change(self, change):
        if change["new"] != change["old"]:
            # I am referring to the childrens using the indexes, because these are just three;
            # but we should put them as attributes of the superwidget, I think, and refer them accessing these attributes.
            self.plot_box.children[1].disabled = False

    # control of model and view
    def _update_plot(self, _=None):
        # is this control or view? Control, because it calls view?
        self._model.directions = self.plot_box.children[0].value

        self._model.prepare_data_for_plots()

        self.produce_undi_plots()

        self.plot_box.children[1].disabled = True

    # control of model
    def _on_field_direction_change(self, change):
        if change["new"] != change["old"]:
            self._model.field_direction = change["new"]
            self._update_plot()
