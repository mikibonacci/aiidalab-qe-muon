from aiidalab_qe.common.mvc import Model
import traitlets as tl
from traitlets import observe
from aiida.common.extendeddicts import AttributeDict
import numpy as np
import base64
import json


from aiida_muon.utils.export_findmuon import export_findmuon_data
from aiidalab_qe_muon.utils.data import (
    dictionary_of_names_for_html, 
    no_Bfield_sentence,
    color_code,
)

from aiida import orm
import ase


class FindMuonModel(Model):
    """Model for the FindMuon data.
    
    """
    view_mode_options = [ # does not need to be a trait
            ("Compare sites", 0),
            ("Inspect site", 1),
    ]
    
    muon = tl.Instance(AttributeDict, allow_none=True)
    selected_muons = tl.List(
        trait=tl.Int(),
    )
    selected_view_mode = tl.Int(0)
    structure = tl.Union(
        [
            tl.Instance(ase.Atoms),
            tl.Instance(orm.StructureData),
        ],
        allow_none=True,
    )
    html_table = tl.Unicode("")
    table_data = tl.List(tl.List())
    
    advanced_table = tl.Bool(False)
    table_legend_text = tl.Unicode("")
    
    supercell_was_small = tl.Bool(False)
    
    selected_labels = tl.List(tl.Unicode())
    
    full_muon_indexes = tl.List(
        trait=tl.Int(),
    )
    
    full_muon_labels = tl.List(
        trait=tl.Unicode(),
    )
    
    distortions_y = tl.Unicode("delta_distance") # delta_distance (difference of the norms of the distances from the muon, final and init.), distortion (norm of vector difference)
    distortions_x = tl.Unicode("atm_distance_final") # atm_distance_init, atm_distance_final
    
    @observe("selected_muons")
    def _on_selected_muons(self, _=None):
        self.selected_labels = self.findmuon_data["table"].loc[self.selected_muons, "label"].tolist()
    
    def fetch_data(self):
        """Fetch the findmuon data from the FindMuonWorkChain outputs."""
        self.findmuon_data = export_findmuon_data(self.muon.findmuon)
        self.muon_index_list = self.findmuon_data["table"].index.tolist()
        self.selected_muons = self.muon_index_list[0:1]
        
        #needed to sync with undimodel stuff.
        self.full_muon_indexes = self.muon_index_list
        self.full_muon_labels = self.findmuon_data["table"]["label"].tolist()
        
        self.distortions = self.findmuon_data["distortions"]

        
        self.sc_matrix = self.muon.findmuon.all_index_uuid.creator.caller.inputs.sc_matrix.get_list()
        suggested_supercell = self.muon.findmuon.all_index_uuid.creator.caller.inputs.structure.base.extras.get("suggested_supercell", [1,1,1])
        if any([self.sc_matrix[i][i]<suggested_supercell[i] for i in range(3)]):
            self.supercell_was_small = True
            
        if "Bdip_norm" not in self.findmuon_data["table"].columns.tolist():
            self.no_B_in_DFT = True
        else: 
            self.no_B_in_DFT = False

    def select_structure(self):
        """Select a structure to be displayed.
        
        if we have multiple sites selected, we need to show the unrelaxed unit cell with all sites.
        Otherwise, we show the relaxed supercell with the single selected site.
        And then in the view we select only the one we want to inspect.
        """
        if len(self.selected_muons) == 1 and self.selected_view_mode == 0:
            self.structure = orm.load_node(self.findmuon_data["table"].loc[self.selected_muons[0],"structure_id_pk"])
        elif self.selected_view_mode == 1:
            self.structure = self.findmuon_data["unit_cell"]
    
    def convert_label_to_html(self, entry) -> str:
        # to have nice names in the html, instead of the column names.
        return dictionary_of_names_for_html[entry]
    
    
    
    def _generate_table_data(self,) -> str:
        """Generate a table from the selected data.
        
        This method is called by the controller to get the html table.
        """
        excluded_columns = ["tot_energy","muon_index_global_unitcell","muon_index"]
        if self.advanced_table:
            excluded_columns = ["muon_index"]
            
        data = [[self.convert_label_to_html(entry) for entry in self.findmuon_data["table"].columns.to_list() if entry not in excluded_columns]]
        #data[-1].pop(-3)
        for index in self.findmuon_data["table"].index:
            data.append(self.findmuon_data["table"].drop(excluded_columns, axis=1).loc[index].to_list())
            #data[-1].pop(-3)
        self.table_data = data
        
    def get_distorsion_data(self):
        """Get the distorsion data for the selected site.
        
        This method is called by the controller to get the data for the distorsion plot.
        """        
        return self.distortions[str(self.selected_muons[-1])]
    
    @staticmethod
    def _prepare_single_structure_for_download(structure) -> str:
        from tempfile import NamedTemporaryFile

        tmp = NamedTemporaryFile()
        structure.write(tmp.name, format="cif")
        with open(tmp.name, "rb") as raw:
            return base64.b64encode(raw.read()).decode()
    
    def _prepare_structures_for_download(self) -> str:
        """Prepare the structures for download.
        
        This method is called by the controller to get the data for download.
        """
        # prepare (all) the structures for download as ase atoms objects
        structures = {}
        for index, label in zip(self.findmuon_data["table_all"]["muon_index"],self.findmuon_data["table_all"]["label"]):
            node_id = self.findmuon_data["table_all"].loc[self.findmuon_data["table_all"]["muon_index"] == index, "structure_id_pk"].values[0]
            structure = orm.load_node(node_id).get_ase()
            structures[label] = structure
        
        structures["unit_cell"] = self.findmuon_data["unit_cell"].get_ase()
        structures["unit_cell_all"] = self.findmuon_data["unit_cell_all"].get_ase()
        structures["supercell_all"] = self.findmuon_data["supercell_all"].get_ase()
        
        return structures
    
    def _prepare_distortions_for_download(self) -> str:
        """Prepare the distortions for download.
        
        This method is called by the controller to get the data for download.
        """
        # prepare the distortions for download as json
        import pandas as pd
        
        distortions_df = {}
        for index, label in zip(self.findmuon_data["table_all"]["muon_index"],self.findmuon_data["table_all"]["label"]):
            distortion = {}
            distortion["atm_distance_init"] = []
            distortion["atm_distance_final"] = []
            distortion["distortion"] = []
            distortion["delta_distances"] = []
            distortion["element"] = []
            
            for element,data in self.distortions[index].items():
                for i in range(len(data["atm_distance_init"])):
                    distortion["atm_distance_init"].append(data["atm_distance_init"][i])
                    distortion["atm_distance_final"].append(data["atm_distance_final"][i])
                    distortion["delta_distances"].append(data["delta_distance"][i])
                    distortion["distortion"].append(data["distortion"][i])
                    distortion["element"].append(element)
                    
            df = pd.DataFrame.from_dict(distortion).sort_values(by="atm_distance_init")
            distortions_df[label] = df
        
        return distortions_df
    
    def _prepare_data_for_download(self) -> str:
        """Prepare the data for download.
        
        This method is called by the controller to get the data for download.
        """
        # prepare the data for download as csv file
        files_dict = {}
        files_dict["table"] = self.findmuon_data['table']
        files_dict["table_all"] = self.findmuon_data['table_all']
        files_dict["structures"] = self._prepare_structures_for_download()
        formula = orm.load_node(self.findmuon_data["table"].loc[self.muon_index_list[0],"structure_id_pk"]).get_formula()
        files_dict["filename"] = f"exported_mu_res_{formula}_WorkflowID_{self.muon.findmuon.all_index_uuid.creator.caller.caller.caller.pk}.zip"
        
        files_dict["distortions"] = self._prepare_distortions_for_download()
        
        self.generate_table_legend(download_mode=True)
        files_dict["readme"] = self.readme_text
        return files_dict
    
    @staticmethod
    def produce_bitestream(files_dict):
        import tempfile
        import pathlib
        import shutil
        import os
        
        with tempfile.TemporaryDirectory() as dirpath:
            path = pathlib.Path(dirpath) / "downloadable_data"
            output_zip_path = pathlib.Path(dirpath) / "downloadable_data.zip"
            
            os.mkdir(path)
            
            # Tables
            files_dict["table"].drop(columns="muon_index").to_csv(path / "Summary_table.csv", index=True)
            files_dict["table_all"].drop(columns="muon_index").to_csv(path / "Summary_table_before_clustering.csv", index=True)
            
            # Structures
            for label, structure in files_dict["structures"].items():
                if label == "unit_cell":
                    structure.write(path / f"Allsites_unitcell.cif", format="cif")
                elif label == "unit_cell_all":
                    structure.write(path / f"Allsites_before_clustering_unitcell.cif", format="cif")
                elif label == "supercell_all":
                    structure.write(path / f"Allsites_before_clustering_supercell.cif", format="cif")
                else:
                    structure.write(path / f"Supercell_{label}.cif", format="cif")
            
            # Distortions
            for label, df in files_dict["distortions"].items():
                df.to_csv(path / f"Distortion_supercell_{label}.csv", index=False)
            
            # README
            with open(path / "README.txt", "w") as f:
                f.write(files_dict["readme"])
            
            shutil.make_archive(path, "zip", path)
                    
            with open(output_zip_path, "rb") as f:
                    raw_data = f.read()

            # Convert the raw_data to base64 so it can be used as a payload in JavaScript
            bitestream = base64.b64encode(raw_data).decode()

        return bitestream
    
    @staticmethod
    def _download(payload, filename):
        """Download payload as a file named as filename."""
        from IPython.display import Javascript

        javas = Javascript(
            f"""
            var link = document.createElement('a');
            link.href = 'data:text/json;charset=utf-8;base64,{payload}'
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """
        )
        display(javas)
    
    @staticmethod 
    def populate_distortion_figure(
        distortion_data, 
        distortions_figure,
        callback, # go.Scatter, but I don't want to import plotly here.
        muon_label = "A",
        x_quantity = "atm_distance_final",
        y_quantity = "distortion",
        just_update = False,
    ):
        distortions_figure.add_hline(y=0, line_dash="dash")
        symbols = []
        for i, (element,data) in enumerate(distortion_data.items()):
            if not just_update:
                distortions_figure.add_trace(
                    callback(
                        x=data[x_quantity],
                        y=data[y_quantity],
                        mode="markers",
                        name=element,
                        marker=dict(
                            size=12,
                            opacity=1,
                        ),
                    )
                )
                
            else:
                distortions_figure.data[i].x = data[x_quantity]
                distortions_figure.data[i].y = data[y_quantity]
                
                
            
        if y_quantity == "distortion":
            ylabel = "|r<sub>&mu;, f</sub> - r<sub>&mu;, i</sub>| (Å)"
        else:
            ylabel = "|r<sub>&mu;, f</sub>|-|r<sub>&mu;, i</sub>| (Å)"
        
        if x_quantity == "atm_distance_final":
            xlabel = "Final distance from the muon (Å)"
        else:   
            xlabel = "Initial distance from the muon (Å)"           
        
        distortions_figure.update_layout(
            title=dict(
                text=f"Distortion induced by muon {muon_label}",
                font=dict(size=18),
                x=0.5,  # Center horizontally
                y=0.95,  # Fix vertical position
                xanchor="center",
                yanchor="top",
            ),
            margin=dict(l=5, r=5, t=45, b=5),
            xaxis=dict(
                    title=xlabel,
                    tickmode="linear",
                    dtick=0.5,
                    color="black",
                ),
            yaxis=dict(
                    title=ylabel,
                    dtick=0.25,
                    side="left",
                    showticklabels=True,
                    showgrid=True,
                    color="black",
                ),
            font=dict(  # Font size and color of the labels
                    size=15,
                    color="black",
                ),
            legend=dict(
                    font=dict(
                        size=15,
                        color="black",
                    ),
            ),
        )

    def download_data(self, _=None):
        """Function to download the data."""
        files_dict = self._prepare_data_for_download()
        payload = self.produce_bitestream(files_dict)
        self._download(payload=payload, filename=files_dict["filename"])
        
    def generate_table_legend(self, download_mode=False):
        """Generate the table legend."""
        from importlib_resources import files
        from jinja2 import Environment
        from aiidalab_qe_muon.app.static import templates
        
        env = Environment()
        table_legend_template = files(templates).joinpath("table_legend.html.j2").read_text()
        table_legend_text = env.from_string(table_legend_template).render(
            {"B_fields": not self.no_B_in_DFT, 
             "advanced_table":self.advanced_table,
             "data":dictionary_of_names_for_html,
             "download_mode":download_mode,
            }
        )
        
        if download_mode:
            self.readme_text = table_legend_text 
        else:
            self.table_legend_text = table_legend_text
    
     # NOTE: This is commented because I don't think we need it... no additional information to the panel. 
    # It works in conjunction with the _update_barplot of the widget. 
    # def get_data_plot(self) -> dict:
    #     """Get the data for the plot.
        
    #     This method is called by the controller to get the data for the plot.
    #     I put it in the model as it can also be used to reorganize the data for other
    #     purposes than the view.
    #     """
        
    #     self.data_plot = {
    #         "x":self.selected_labels,
    #         "y":[],
    #         "entry":[],
    #         "color_code":[],
    #     }
        
    #     entries = ["delta_E", "B_T_norm", "Bdip_norm", "B_hf_norm"]
        
    #     self.data_plot["y"] = [
    #         self.findmuon_data["table"].loc[self.selected_muons, entry].tolist() for entry in entries
    #         if entry in self.findmuon_data["table"].columns.tolist()
    #     ]
        
    #     self.data_plot["entry"] = [
    #         self.convert_label_to_html(entry) for entry in entries
    #         if entry in self.findmuon_data["table"].columns.tolist()
    #     ]
        
    #     self.data_plot["color_code"] = [
    #         color_code[entry] for entry in entries
    #         if entry in self.findmuon_data["table"].columns.tolist()
    #     ]
                
    #     return self.data_plot