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
    
    directions = tl.Enum(["z","y","x", "powder"], default_value="z")
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
    selected_indexes = tl.List( # muon selected indexes. Relevant if multiple sites are computed at the same time.
        trait=tl.Int(),
    )
    
    details_on_the_approximations = (
        """
        The polarization spectra are computed using the <b><a href="https://undi.readthedocs.io/en/latest/index.html"
        target="_blank">UNDI</b></a> package (mUon Nuclear Dipolar Interaction, <a href="https://doi.org/10.1016/j.cpc.2020.107719"
        target="_blank">Bonfà et al., Comput. Phys. Commun. 260, 107719, 2021</a>), 
        a package to obtain the time evolution of the muon spin polarization originating from its 
        interaction with nuclear magnetic dipoles in standard experimental conditions (i.e. when thermal 
        energy is much larger that nuclear interactions). <br>
        Some important approximations are made in the computation of the polarization spectra:
        <ul>
            <li> We compute the polarization function using the Celio's approximated approach, via the Trotter decomposition formula for bounded operators 
            (<a href="https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.56.2720"target="_blank">Celio, Phys. Rev. Lett. 56, 2720, 1986</a>). 
            This is usually is usually in very good agreement with the exact (and much more computationally expensive) solution.</li>
            <li> UNDI assumes that the spin polarization is along z. </li>
            <li> As a consequence, in general, an external field applied along z
                is a Longitudinal Field (LF); external fields in the plane perpendicular to z are then Transverse Fields (TF). </li>
        </ul>
        """
    )
    
    details_on_the_isotope_combinations = (
        "The polarization spectra are computed considering a weighted average of the isotopes combinations, with respect to their relative probability (abundance)."
    )
    
    selected_labels = tl.List(tl.Unicode())
    
    def __init__(self, node=None, undi_nodes=None, KT_node=None, mode="plot"):
        
        self.mode = mode
        
        if node:
            self.muon = node
            
        if undi_nodes:
            self.nodes = [orm.load_node(node_pk) for node_pk in undi_nodes]
            if len(self.nodes):
                self.fetch_data()
        if KT_node:
            self.load_KT(KT_node)
            
        if mode == "analysis":
            self.selected_labels = ["A"]

    def get_data_plot(
        self,
    ):
        """Prepare the data to just be plugged in in the FigureWidget."""

        for muon_index in self.muons.keys():
            
            self.muons[muon_index].data = {
                "y": {
                    "lf": self.compute_isotopic_averages(field_direction="lf", muon_index=muon_index),
                    "tf": self.compute_isotopic_averages(field_direction="tf", muon_index=muon_index)
                    if self.mode == "plot"
                    else None,  # one element each node. These elements are dictionaries containing x,y,z signals averaged wrt the isotopes.
                }
            }

            self.muons[muon_index].data["x"] = np.array(self.muons[muon_index].results[0][0]["t"]) * 1e6
            
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
        if not hasattr(self, "nodes"):
            self.nodes = self.muon.polarization.base.links.get_incoming().get_node_by_label('execution_count').called
        # workgraph case - always the case in standard situations (qe app usage)
        if "workgraph" in self.nodes[0].process_type:
            # this loops can be improved, for sure there is a smarter way to do this.
            
            self.muons = {} # each muon will be a key of this dictionary.
            
            for muon in self.nodes: # this need to be the called of the MultiSites task.
                
                #muon_index = muon.base.extras.get("muon_index", 0)
                muon_index = muon.base.attributes.all.get("metadata_inputs",{}).get("metadata",{}).get("call_link_label","0").replace("polarization_structure_","")
                
                if self.mode == "analysis":
                    if not "convergence_check" in muon.base.links.get_outgoing().all_link_labels():
                        continue
                    
                self.muons[muon_index] = AttributeDict()
                
                main_node = muon

                search = "undi_runs"
                if self.mode == "analysis":
                    search = "convergence_check"

                descendants = (
                    main_node.base.links.get_outgoing().get_node_by_label(search).called
                )

                self.muons[muon_index].results = [
                    node.outputs.result.get_list() for node in descendants
                ]
                
                self.fields = [
                    node.inputs.function_inputs.B_mod.value * 1000 for node in descendants
                ]  # mT
                self.muons[muon_index].fields = self.fields
                self.selected_fields = [
                    node.inputs.function_inputs.B_mod.value * 1000 for node in descendants
                ]  # mT
                
                self.max_hdims = [
                    int(node.inputs.function_inputs.max_hdim.value) for node in descendants
                ]
                
                self.isotopes = [
                    [res["cluster_isotopes"], res["spins"], res["probability"]]
                    for res in self.muons[muon_index].results[0]
                ]

                self.selected_isotopes = list(range(len(self.isotopes)))

                if self.mode == "plot":
                    self.muons[muon_index].KT_output = (
                        main_node.base.links.get_outgoing()
                        .get_node_by_label("KuboToyabe_run")
                        .outputs.result.get_dict()
                    )
            self.selected_indexes = [int(s) for s in self.muons.keys()]
        else:
            # shelljob case - Will never be the case in the app.
            self.fields = [
                node.inputs.nodes.B_mod.value * 1000 for node in self.nodes
            ]  # mT
            self.selected_fields = [
                node.inputs.nodes.B_mod.value * 1000 for node in self.nodes
            ]  # mT
            self.max_hdims = [node.inputs.nodes.max_hdim.value for node in self.nodes]
            self.results = [
                json.loads(node.outputs.resultss_json.get_content())
                for node in self.nodes
            ]
            self.isotopes = [
                [res["cluster_isotopes"], res["spins"], res["probability"]]
                for res in self.results[0]
            ]
            self.selected_isotopes = list(range(len(self.isotopes)))


    def create_html_table(self, first_row=[]):
        """
        Create an HTML table representation of a Nx3 matrix. N is the number of isotope mixtures.

        :param matrix: List of lists representing an Nx3 matrix
        :return: HTML table string
        """
        matrix = self.create_cluster_matrix()
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
        import pandas as pd
        
        data_file_list = []
        
        # prepare the data for download as csv file
        for muon_index in self.selected_indexes:
            csv_dict = {"t (μs)": self.muons[str(muon_index)].data["x"]}

            for i, Bvalue in enumerate(self.fields):
                csv_dict[f"B={Bvalue}_mT"] = self.muons[str(muon_index)].data["y"][
                    self.field_direction
                ][i][f"signal_{self.directions}"]
                
            df = pd.DataFrame.from_dict(csv_dict)
            data = base64.b64encode(df.to_csv(index=True).encode()).decode()
            filename = f"muon_{muon_index}_dir_{self.directions}_{self.field_direction}.csv"
            data_file_list.append((data, filename))
            
            # we download KT if is there and is plotted.
            if hasattr(self.muons[str(muon_index)], "KT_output") and self.plot_KT:
                csv_dict_kt = {"t (μs)": self.muons[str(muon_index)].KT_output["t"]}
                csv_dict_kt["Kubo-Toyabe"] = self.muons[str(muon_index)].KT_output["KT"]
                
                df = pd.DataFrame.from_dict(csv_dict_kt)
                data = base64.b64encode(df.to_csv(index=True).encode()).decode()
                filename = f"muon_{muon_index}_Kubo_Toyabe.csv"
                data_file_list.append((data, filename))
            
            
        return data_file_list
    
    def _download_pol(self, _=None):
        data_file_list = self._prepare_data_for_download()
        for data, filename in data_file_list:
            self._download(payload=data, filename=filename)
            
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
    
    def compute_isotopic_averages(self, field_direction="lf", muon_index = "0"):
        selected_isotopes = list(range(len(self.isotopes)))
        weights = [self.isotopes[int(i)][-1] for i in selected_isotopes if i != ""]
        averages_full = []
        for index in range(len(self.muons[muon_index].results)):
            averages = {}
            for direction in ["z", "x", "y", "powder"]:
                if self.mode == "analysis" and direction in ["x", "y", "powder"]:
                    continue

                values = [
                    self.muons[muon_index].results[index][int(i)][f"signal_{direction}_{field_direction}"]
                    for i in selected_isotopes
                    if i != ""
                ]

                # Compute the weighted average
                averages[f"signal_{direction}"] = np.average(
                    values, weights=weights, axis=0
                )

            averages_full.append(averages)

        return averages_full
