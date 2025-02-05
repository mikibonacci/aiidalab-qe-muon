from aiida import orm

import base64
import numpy as np
import pandas as pd

from pymatgen.core import Structure



def produce_muonic_dataframe(findmuon_output_node: orm.Node) -> pd.DataFrame:
    bars = {
        "magnetic_units": "tesla",
        "magnetic_keys": [
            "B_T",
            "Bdip",
            "B_T_norm",
            "hyperfine_norm",
            "hyperfine",
            "Bdip_norm",
        ],
        "muons": {},
    }
    for i, (idx, uuid) in enumerate(findmuon_output_node.all_index_uuid.get_dict().items(), start=1):
        if idx in findmuon_output_node.unique_sites.get_dict().keys():
            relaxwc = orm.load_node(uuid)
            bars["muons"][idx] = {}
            bars["muons"][idx]["structure_id_pk"] = relaxwc.outputs.output_structure.pk
            bars["muons"][idx]["label"] = idx # a label to recognise the supercell/muon site
            bars["muons"][idx]["muon_index"] = idx # sure that we need it?
            bars["muons"][idx]["tot_energy"] = (
                np.round(relaxwc.outputs.output_parameters.get_dict()["energy"]*10**3,1)
            )
            bars["muons"][idx]["muon_position_cc"] = list(
                np.round(
                    np.array(
                        findmuon_output_node.unique_sites.get_dict()[idx][0]["sites"][
                            -1
                        ]["abc"]
                    ),
                    3,
                ),
            )
            bars["muons"][idx]["muon_index_global_unitcell"] = len(relaxwc.outputs.output_structure.sites) - 1 + i # we start counting from 1. 

    fields_list = []
    if "unique_sites_dipolar" in findmuon_output_node:
        fields_list = ["B_T", "Bdip", "hyperfine", "B_T_norm", "Bdip_norm", "hyperfine_norm"]
        for configuration in findmuon_output_node.unique_sites_dipolar.get_list():
            for B in ["B_T", "Bdip"]:
                bars["muons"][str(configuration["idx"])][B] = list(
                    np.round(np.array(configuration[B]), 3)
                )
                if B in ["B_T"]:
                    bars["muons"][str(configuration["idx"])]["B_T_norm"] = round(
                        np.linalg.norm(np.array(configuration[B])), 3
                    )
                if B in ["Bdip"]:
                    bars["muons"][str(configuration["idx"])]["Bdip_norm"] = round(
                        np.linalg.norm(np.array(configuration[B])), 3
                    )
            if "unique_sites_hyperfine" in findmuon_output_node:
                v = findmuon_output_node.unique_sites_hyperfine.get_dict()[
                    str(configuration["idx"])
                ]
                # bars["muons"][str(configuration["idx"])]["hyperfine"] = v
                bars["muons"][str(configuration["idx"])]["hyperfine_norm"] = round(
                    abs(v[-1]), 3
                )  # <-- we select the last, is in T (the first is in Atomic units).


    df = pd.DataFrame.from_dict(bars["muons"])
    df.columns = df.columns.astype(int)
    # sort
    df = df.sort_values("tot_energy", axis=1)
    
    # deltaE
    # round deltaE to integer meV
    df.loc["delta_E"] = df.loc["tot_energy"] - df.loc["tot_energy"].min() 
    
    # Insert the delta_E row as third row
    df = df.reindex(
        [
            "structure_id_pk", 
            "label", 
            "delta_E", 
            "tot_energy", 
            "muon_position_cc",
        ]+ fields_list
        +["muon_index_global_unitcell"]
        +["muon_index"],
    )
        
    # then swap row and columns (for sure can be done already above)
    df = df.transpose()
    return df


# (2) unit cell with all muonic sites.
def produce_collective_unit_cell(findmuon_output_node: orm.Node) -> orm.StructureData:
    # e_min=np.min([qeapp_node.outputs.unique_sites.get_dict()[key][1] for key in qeapp_node.outputs.unique_sites.get_dict()])
    sc_matrix = [
        findmuon_output_node.all_index_uuid.creator.caller.inputs.sc_matrix.get_list()
    ]  # WE NEED TO HANDLE also THE CASE IN WHICH IS GENERATED BY MUSCONV.
    input_str = findmuon_output_node.all_index_uuid.creator.caller.inputs.structure.get_pymatgen().copy()

    # append tags to recognize the muon site.
    input_str.tags = [None] * input_str.num_sites

    for key in findmuon_output_node.unique_sites.get_dict():
        # print("H"+key, qeapp_node.outputs.unique_sites.get_dict()[key][1], (qeapp_node.outputs.unique_sites.get_dict() [key][1]-e_min))
        # fo.write("%s %16f %16f \n "%  ("H"+key, uniquesites_dict[key][1], (uniquesites_dict[key][1]-e_min)))
        py_struc = Structure.from_dict(
            findmuon_output_node.unique_sites.get_dict()[key][0]
        )
        musite = py_struc.frac_coords[py_struc.atomic_numbers.index(1)]
        mupos = np.dot(musite, sc_matrix) % 1
        # bad workaround for strange bug.
        if len(mupos) == 1:
            mupos = mupos[0]
            if len(mupos) == 1:
                mupos = mupos[0]
        input_str.append(
            species="H" + key,
            coords=mupos,
            coords_are_cartesian=False,
            validate_proximity=True,
        )
        input_str.tags.append(key)

    kind_properties = []
    for i in input_str.sites:
        i.properties["kind_name"] = i.label
        kind_properties.append(i.properties)
    # raise ValueError(l)

    # We convert from pymatgen Structure to orm.StructureData, so we can use directly StructureDataViewer.
    structure = orm.StructureData(pymatgen=input_str)
    
    # Tags are used for the StructureDataViewer to highlight the muon sites.
    structure.tags = input_str.tags
    
    return structure

def export_findmuon_data(findmuon_output_node: orm.Node) -> dict:
    return {
        "table": produce_muonic_dataframe(findmuon_output_node),
        "unit_cell": produce_collective_unit_cell(findmuon_output_node),
    }