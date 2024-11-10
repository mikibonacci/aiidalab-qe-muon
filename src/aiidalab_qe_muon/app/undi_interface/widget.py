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
    for cell in first_row:
        html += f'<td style="padding: 5px; text-align: center;">{cell}</td>'
    html += "</tr>"
    for row in matrix:
        html += "<tr>"
        for cell in row:
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
        import itertools

        self.fig.data = ()

        for index, direction in itertools.product(
            range(len(self._model.nodes)),
            self._model.directions,
        ):
            # shell_node = node #orm.load_node(2582)

            if self._model.mode == "plot":
                Bmod = self._model.results[index][0]["B_ext"] * 1000  # mT
                label = f"B<sub>ext</sub>={Bmod} mT, {direction}"
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
        description_string_pol = ipw.HTML("""
            <b>Replot instructions</b>
            <br> Choose the sample orientation directions among x,y and/or z, separated by commas.
            Choose the isotopes (via the index in the below table) to be included in the average,
            separated by commas.
        """)
        string_pol = ipw.Text(
            description="(a) Sample directions:",
            value=",".join(self._model.directions),
            style={
                "description_width": "initial"
            },  # Adjust the width of the description label
        )
        string_isotopes = ipw.Text(
            description="(b) Clusters considered:",
            value=",".join(map(str, self._model.selected_isotopes)),
            style={
                "description_width": "initial"
            },  # Adjust the width of the description label
        )
        update_button = ipw.Button(description="Replot", disabled=True)

        field_directions_ddown = ipw.Dropdown(
            options=[("Longitudinal", "lf"), ("Transverse", "tf")],
            value="lf",  # Default value
            description="B<sub>ext</sub> is: ",
            disabled=False,
        )
        field_directions_ddown.observe(self._update_field_direction, "value")

        plot_box = ipw.VBox(
            [
                description_string_pol,
                string_pol,
                string_isotopes,
                update_button,
                field_directions_ddown,
            ],
            layout=ipw.Layout(width="40%"),
        )
        string_pol.observe(self._enable_replot, "value")  # on_string_pol_change
        string_isotopes.observe(
            self._enable_replot, "value"
        )  # on_string_isotopes_change
        update_button.on_click(self._update_plot)  # the on_ is already in on_click.

        return plot_box

    # control of view
    def _enable_replot(self, _=None):
        new_directions = (
            self.plot_box.children[1].value.rstrip(",").split(",")
        )  # this generates a list of strings + "". this is why belowe we put rstrip(",").
        new_isotopes = list(
            map(int, self.plot_box.children[2].value.rstrip(",").split(","))
        )

        # check that we have the polarizations x and/or y and/or z, otherwise error.
        self.plot_box.children = self.plot_box.children[:5]
        if not set(new_directions).issubset(set(["x", "y", "z"])) and not set(
            new_directions
        ).issubset(set(["powder"])):
            self.plot_box.children += (
                ipw.HTML(
                    f"Invalid direction selected: {new_directions}. Valid directions are: {set(['x','y','z'])} and 'powder'"
                ),
            )
        # check that we selected valid cluster indexes.
        elif not set(new_isotopes).issubset(set(range(len(self._model.isotopes)))):
            self.plot_box.children += (
                ipw.HTML(
                    f"Invalid isotopes index selected. Valid indexes are: {set(range(len(self._model.isotopes)))}"
                ),
            )
        else:
            self.plot_box.children = self.plot_box.children[:5]
            if (
                new_directions == self._model.directions
                and new_isotopes == self._model.selected_isotopes
            ):
                return
            self.plot_box.children[3].disabled = False

    # control of model and view
    def _update_plot(self, _=None):
        # is this control or view? Control, because it calls view?
        self._model.directions = self.plot_box.children[1].value.rstrip(",").split(",")
        self._model.selected_isotopes = list(
            map(int, self.plot_box.children[2].value.rstrip(",").split(","))
        )

        self._model.prepare_data_for_plots()  # compute the isotopic averages - depends on the selected isotope configurations

        self.produce_undi_plots()

        self.plot_box.children[3].disabled = True

    # control of model
    def _update_field_direction(self, change):
        if change["new"] != change["old"]:
            self._model.field_direction = change["new"]
            self._update_plot()
