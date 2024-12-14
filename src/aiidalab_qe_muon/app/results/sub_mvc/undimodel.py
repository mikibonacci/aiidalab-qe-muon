from aiidalab_qe.common.mvc import Model
import traitlets as tl
from aiida.common.extendeddicts import AttributeDict
import numpy as np
import base64
import json

from aiida import orm


class PolarizationModel(Model):
    """PolarizationModel is a class designed for handling polarization plots and convergence analysis.
    Attributes:
        nodes (list): List of nodes used in the model.
        sample_orientation (str): str of directions for polarization, default is "z", but can be also x, y or powder.
        fields (list): List of magnetic field values in mT.
        mode (str): Mode of operation, either "plot" or "analysis".
        max_hdims (list): List of maximum hyperfine dimensions.
        estimated_convergence (int): Estimated convergence value.
        REMOVED -> selected_isotopes (list): List of selected isotopes for analysis.
    Methods:
        __init__(self, nodes_pk=[]):
            Initializes the PolarizationModel with given node primary keys.
        get_data_plot(self):
            Prepares the data to be used in the UndiWidget for plotting.
        compute_isotopic_averages(self):
            Computes the isotopic averages for the selected isotopes and returns them.
            We always average over all the isotopes.
    """

    fields = [0.0] # initial guess for the computed fields, then we will load the fields from the nodes.
    selected_isotopes = [] # we will load the isotopes from the nodes. We don't allows choose among them, so no trait.
    estimated_convergence = 0
    
    muon = tl.Union(
        [
            tl.Instance(AttributeDict),
            tl.Instance(list), # for the shelljob case, or anyway if we load externally a list of undi nodes.
        ],
        allow_none=True,
    )
    
    
    
    sample_orientation = tl.Enum(["z","y","x", "powder"], default_value="z")
    mode = tl.Enum(["plot","analysis"], default_value="plot")  # "analysis" for the convergence analysis
    max_hdims = tl.List(
        trait=tl.Float(),
        value=[1e5],
    )
    plotting_quantity = tl.Unicode("P")  # for the convergence analysis
    selected_fields = tl.List(
        trait=tl.Float(),
        value=[0.0],
    )
    field_direction = tl.Enum(["lf", "tf"], default_value="lf")
    plot_KT = tl.Bool(False)
    
    def __init__(self, undi_nodes=[], KT_node=None, mode="plot"):
        self.mode = mode
        self.nodes = [orm.load_node(node_pk) for node_pk in undi_nodes]
        if len(self.nodes):
            self.fetch_data()
        if KT_node:
            self.load_KT(KT_node)

    def get_data_plot(
        self,
    ):
        """Prepare the data to just be plugged in in the FigureWidget."""

        self.data = {
            "y": {
                "lf": self.compute_isotopic_averages(field_direction="lf"),
                "tf": self.compute_isotopic_averages(field_direction="tf")
                if self.mode == "plot"
                else None,  # one element each node. These elements are dictionaries containing x,y,z signals averaged wrt the isotopes.
            }
        }

        self.data["x"] = np.array(self.results[0][0]["t"]) * 1e6

    def create_cluster_matrix(
        self,
    ):
        rows = []
        for t, cluster in enumerate(self.isotopes):
            elements = ", ".join([str(j) + i for i, j in cluster[0].items()])
            spins = ", ".join([i + ": " + str(j) for i, j in cluster[1].items()])
            probability = np.round(cluster[2], 3)
            rows.append([t, elements, spins, probability])
        return rows

    def load_KT(self):
        "in case we want to provide a shelljob for the KT run"
        raise NotImplementedError(
            "This method is not implemented yet, and will be only useful for ShellJobs. \
                                  Please use the aiida-workgraph plugin."
        )

    def fetch_data(
        self,
    ):
        """Load the data from the nodes of undi runs.
        we distinguish if nodes are shelljobs (done as in examples_aiida/shelljob.py) or not,
        i.e. in case we submitted pythonjobs via the aiida-workgraph plugin.
        """

        # workgraph case - always the case in standard situations (qe app usage)
        if len(self.nodes) == 1 and "workgraph" in self.nodes[0].process_type:
            # this loops can be improved, for sure there is a smarter way to do this.
            main_node = self.nodes[0].called[0]

            search = "undi_runs"
            if self.mode == "analysis":
                search = "Convergence"

            descendants = (
                main_node.base.links.get_outgoing().get_node_by_label(search).called
            )
            self.fields = [
                node.inputs.function_kwargs.Bmod.value * 1000 for node in descendants
            ]  # mT
            self.selected_fields = [
                node.inputs.function_kwargs.Bmod.value * 1000 for node in descendants
            ]  # mT
            self.max_hdims = [
                node.inputs.function_kwargs.max_hdim.value for node in descendants
            ]
            self.results = [
                node.outputs.result.value["results"] for node in descendants
            ]
            self.isotopes = [
                [res["cluster_isotopes"], res["spins"], res["probability"]]
                for res in self.results[0]
            ]

            self.selected_isotopes = list(range(len(self.isotopes)))

            if self.mode == "plot":
                self.KT_output = (
                    main_node.base.links.get_outgoing()
                    .get_node_by_label("KuboToyabe_run")
                    .outputs.result.get_dict()
                )
        else:
            # shelljob case - Will never be the case in the app.
            self.fields = [
                node.inputs.nodes.Bmod.value * 1000 for node in self.nodes
            ]  # mT
            self.selected_fields = [
                node.inputs.nodes.Bmod.value * 1000 for node in self.nodes
            ]  # mT
            self.max_hdims = [node.inputs.nodes.max_hdim.value for node in self.nodes]
            self.results = [
                json.loads(node.outputs.results_json.get_content())
                for node in self.nodes
            ]
            self.isotopes = [
                [res["cluster_isotopes"], res["spins"], res["probability"]]
                for res in self.results[0]
            ]
            self.selected_isotopes = list(range(len(self.isotopes)))

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
    
    def _prepare_data_for_download(self):
        """Prepare the data for download.
        This method is called by the controller to get the data for download.
        """
        # prepare the data for download as csv file
        csv_dict = {"t (μs)": self.data["x"]}

        for i, Bvalue in enumerate(self.fields):
            csv_dict[f"B={Bvalue}_mT"] = self.data["y"][
                self.field_direction
            ][i][f"signal_{self.directions}"]

        df = pd.DataFrame.from_dict(csv_dict)
        data = base64.b64encode(df.to_csv(index=True).encode()).decode()
        filename = f"muon_1_dir_{self.directions}_{self.field_direction}.csv"
        return data, filename
    
    @staticmethod
    def compute_isotopic_averages(results, isotopes, field_direction="lf", mode="plot"):
        selected_isotopes = list(range(len(isotopes)))
        weights = [isotopes[int(i)][-1] for i in selected_isotopes if i != ""]
        averages_full = []
        for index in range(len(results)):
            averages = {}
            for direction in ["z", "x", "y", "powder"]:
                if mode == "analysis" and direction in ["x", "y", "powder"]:
                    continue

                values = [
                    results[index][int(i)][f"signal_{direction}_{field_direction}"]
                    for i in selected_isotopes
                    if i != ""
                ]

                # Compute the weighted average
                averages[f"signal_{direction}"] = np.average(
                    values, weights=weights, axis=0
                )

            averages_full.append(averages)

        return averages_full
