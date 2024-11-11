import numpy as np

import json

from aiida import orm


class PolarizationModel:
    """PolarizationModel is a class designed for handling polarization plots and convergence analysis.
    Attributes:
        nodes (list): List of nodes used in the model.
        directions (str): str of directions for polarization, default is "z", but can be also x, y or powder.
        fields (list): List of magnetic field values in mT.
        mode (str): Mode of operation, either "plot" or "analysis".
        max_hdims (list): List of maximum hyperfine dimensions.
        estimated_convergence (int): Estimated convergence value.
        REMOVED -> selected_isotopes (list): List of selected isotopes for analysis.
    Methods:
        __init__(self, nodes_pk=[]):
            Initializes the PolarizationModel with given node primary keys.
        prepare_data_for_plots(self):
            Prepares the data to be used in the UndiWidget for plotting.
        compute_isotopic_averages(self):
            Computes the isotopic averages for the selected isotopes and returns them.
            We always average over all the isotopes.
    """

    nodes = []
    directions = "z"  # ,"y","x", "powder"]
    fields = [0.0]
    mode = "plot"  # "analysis" for the convergence analysis
    max_hdims = [1e5]
    estimated_convergence = 0
    selected_isotopes = []
    field_direction = "lf"  # "tf", longitudinal and transverse.

    def __init__(self, nodes_pk=[]):
        self.nodes = [orm.load_node(node_pk) for node_pk in nodes_pk]
        if len(nodes_pk):
            self.fields = [
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

    def prepare_data_for_plots(
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

    def compute_isotopic_averages(self, field_direction="lf"):
        weights = [self.isotopes[int(i)][-1] for i in self.selected_isotopes if i != ""]
        averages_full = []
        for index in range(len(self.nodes)):  # field, or calculation.
            averages = {}
            for direction in ["z", "x", "y", "powder"]:
                if self.mode == "analysis" and direction in ["x", "y", "powder"]:
                    continue

                values = [
                    self.results[index][int(i)][f"signal_{direction}_{field_direction}"]
                    for i in self.selected_isotopes
                    if i != ""
                ]

                # Compute the weighted average
                averages[f"signal_{direction}"] = np.average(
                    values, weights=weights, axis=0
                )

            averages_full.append(averages)

        return averages_full

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
