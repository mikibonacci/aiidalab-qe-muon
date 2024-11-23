import numpy as np
import base64
import pandas as pd

import ipywidgets as ipw
import plotly.graph_objects as go

from aiidalab_qe_muon.undi_interface.model import PolarizationModel


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
            self.info_on_the_approximations.selected_index = None  # Collapse by default

            download_data_button = ipw.Button(
                description="Download P(t) data in csv format",
                icon="download",
                button_style="primary",
                disabled=False,
                tooltip="Download polarization data with selected directions, for all the applied magnetic field magnitudes.",
                layout=ipw.Layout(width="auto"),
            )

            self.children = [
                self.fig,
                ipw.HBox(
                    [
                        ipw.HTML("Plot options:"),
                        download_data_button,
                    ],
                    layout=ipw.Layout(justify_content="space-between"),
                ),
                self.plot_box,
                self.info_on_the_approximations,
            ]

            download_data_button.on_click(self._download_pol)

            self.rendered = True

        else:
            self.plotting_quantity = ipw.ToggleButtons(
                options=[
                    ("P(t)", "P"),
                    ("ΔP(t) = P(t) - Pᵣ(t)", "deltaP"),
                    ("100*ΔP(t)/Pᵣ(t)", "deltaP_rel"),
                ],
                value="P",
            )
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

            self.plotting_quantity.observe(self._on_plotting_quantity_change, "value")

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
        field_direction = self._model.field_direction
        selected_fields = self._model.selected_fields

        for index in range(len(self._model.results)):
            # shell_node = node #orm.load_node(2582)
            if self._model.fields[index] not in selected_fields:
                continue
            if self._model.mode == "plot":
                Bmod = self._model.results[index][0]["B_ext"] * 1000  # mT
                label = f"B<sub>ext</sub>={Bmod} mT"
                ydata = self._model.data["y"][field_direction][index][
                    f"signal_{direction}"
                ]
                ylabel = "P(t)"
                title = None
            elif self._model.mode == "analysis":
                to_be_plotted = self._model.plotting_quantity
                Bmod = self._model.results[index][0]["B_ext"] * 1000  # mT
                label = f"max<sub>hdim</sub> = {self._model.max_hdims[index]}"

                highest_res = self._model.results[-1]

                ydata = np.array(
                    self._model.data["y"][field_direction][index][f"signal_{direction}"]
                )
                ylabel = "P(t)"
                if "delta" in to_be_plotted:
                    ydata = np.array(highest_res[0][f"signal_{direction}_lf"]) - ydata
                    ylabel = "ΔP(t)"
                if "rel" in to_be_plotted:
                    ydata /= 100 * np.array(highest_res[0][f"signal_{direction}_lf"])
                    ylabel = "Δ<sub>%</sub>P(t)"
                title = None  # "$$\Delta P(t) = P_{max\_hdim=10^9}(t) - P(t)$$"

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
            if self._model.mode == "analysis":
                self.fig.update_layout(
                    yaxis=dict(title=ylabel),
                )

    # view
    def tuning_plot_box(
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

        add_KT = ipw.Checkbox(
            value=False,
            description="Add Kubo-Toyabe in the plot",
            disabled=False,
            indent=False,
            layout=ipw.Layout(
                width="80%",
            ),
        )

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

        field_magnitude_desc = ipw.HTML(
            """
            <b>B<sub>ext</sub> magnitude (mT)</b> <br>
            select mutiple field values using CTRL+cursor.
            """
        )
        field_magnitudes = ipw.SelectMultiple(
            options=self._model.fields,
            value=self._model.selected_fields,
            disabled=False,
            layout=ipw.Layout(width="200px", height="100px"),
        )

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

        sample_dir.observe(self._on_sampling_dir_change, "value")
        field_directions_ddown.observe(self._on_field_direction_change, "value")
        field_magnitudes.observe(self._on_field_magnitudes_change, "value")

        return plot_box

    # control of view
    def _on_sampling_dir_change(self, change):
        if change["new"] != change["old"]:
            self._model.directions = change["new"]
            self._update_plot()

    # control of view
    def _on_field_direction_change(self, change):
        if change["new"] != change["old"]:
            self._model.field_direction = change["new"]
            self._update_plot()

    # control of view
    def _on_field_magnitudes_change(self, change):
        if change["new"] != change["old"]:
            self._model.selected_fields = change["new"]
            self._update_plot()

    # for the convergence analysis:
    def _on_plotting_quantity_change(self, change):
        if change["new"] != change["old"]:
            self._model.plotting_quantity = change["new"]
            self._update_plot()

    # control of model and view
    def _update_plot(self, _=None):
        # is this control or view? Control, because it calls view?
        # self._model.prepare_data_for_plots()
        self.produce_undi_plots()

    def _download_pol(self, _=None):
        csv_dict = {"t (μs)": self._model.data["x"]}

        for i, Bvalue in enumerate(self._model.fields):
            csv_dict[f"B={Bvalue}_mT"] = self._model.data["y"][
                self._model.field_direction
            ][i][f"signal_{self._model.directions}"]

        df = pd.DataFrame.from_dict(csv_dict)
        data = base64.b64encode(df.to_csv(index=True).encode()).decode()
        fname = f"muon_1_dir_{self._model.directions}_{self._model.field_direction}.csv"
        self._download(payload=data, filename=fname)

    @staticmethod
    def _download(payload, filename):
        from IPython.display import Javascript, display

        javas = Javascript(
            f"""
            var link = document.createElement('a');
            link.href = 'data:application;base64,{payload}'
            link.download = '{filename}'
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """
        )
        display(javas)
