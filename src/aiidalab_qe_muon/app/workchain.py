from aiida.orm import load_code, Dict, Bool, load_group
from aiida.plugins import WorkflowFactory, DataFactory
from aiida_quantumespresso.common.types import ElectronicType, SpinType

from aiida_quantumespresso.data.hubbard_structure import HubbardStructureData

ImplantMuonWorkChain = WorkflowFactory("muon_app.implant_muon")

"""try:
    DataFactory("atomistic.structure")
    old_structuredata=False
except:
    old_structuredata=True"""



def create_resource_config(code_details):
    """
    Create a dictionary with resource configuration based on codes for 'pw'.

    Parameters:
        codes (dict): A dictionary containing the code configuration.

    Returns:
        dict: A nested dictionary with structured resource configurations.
    """
    return {
        "options": {
            "resources": {
                "num_machines": code_details["nodes"],
                "num_mpiprocs_per_machine": code_details["ntasks_per_node"],
                "num_cores_per_mpiproc": code_details["cpus_per_task"],
            }
        }
    }


def get_builder(codes, structure, parameters):
    from copy import deepcopy

    protocol = parameters["workchain"].pop("protocol", "fast")
    pw_code = codes.get("pw_muons")["code"]
    pp_code = codes.get("pp_code")["code"]

    magmom = parameters["muonic"].pop("magmoms", None)
    supercell = parameters["muonic"].pop("supercell_selector", None)
    sc_matrix = [[supercell[0], 0, 0], [0, supercell[1], 0], [0, 0, supercell[2]]]

    compute_supercell = parameters["muonic"].pop("compute_supercell", False)
    mu_spacing = parameters["muonic"].pop("mu_spacing", 1.0)
    kpoints_distance = parameters["muonic"].pop("kpoints_distance", 0.301)
    charge_supercell = parameters["muonic"].pop("charged_muon", True)

    disable_hubbard = not parameters["muonic"].pop("hubbard", True) # hubbard = True here means we DISABLE the hubbard correction (the checkbox in setting is for disabling).

    pseudo_family = parameters["muonic"].pop("pseudo_choice", "")
    # dummy logic.
    pseudo_family = pseudo_family if pseudo_family != "" else "SSSP/1.3/PBE/efficiency"


    if not disable_hubbard and not isinstance(structure, HubbardStructureData):
        structure = HubbardStructureData.from_structure(structure)

    trigger = "findmuon"

    scf_overrides = deepcopy(parameters["advanced"])
    overrides = {
        # "relax":{
        "base": scf_overrides,
        #    },
        "pwscf": scf_overrides,
    }
    
    pp_metadata = {
        "options": {
            "max_wallclock_seconds": 60 * 60,
            "resources": {
                "num_machines": 1,
                "num_mpiprocs_per_machine": 1,
            },
        },
    }

    if compute_supercell:
        sc_matrix = None
        overrides["impuritysupercellconv_metadata"] = create_resource_config(
            codes.get("pw_muons")
        )
        overrides["impuritysupercellconv"] = overrides

    overrides["base"]["pw"]["metadata"] = create_resource_config(codes.get("pw_muons"))

    builder = ImplantMuonWorkChain.get_builder_from_protocol(
        pw_muons_code=pw_code,
        pp_code=pp_code,
        pseudo_family=pseudo_family,
        structure=structure,
        protocol=protocol,
        overrides=overrides,
        trigger=trigger,
        relax_unitcell=False,  # but not true in the construction; in the end you relax in the first step of the QeAppWorkchain.
        magmom=magmom,
        sc_matrix=sc_matrix,
        mu_spacing=mu_spacing,
        kpoints_distance=kpoints_distance,
        charge_supercell=charge_supercell,
        hubbard=not disable_hubbard,
        electronic_type=ElectronicType(parameters["workchain"]["electronic_type"]),
        spin_type=SpinType(parameters["workchain"]["spin_type"]),
        initial_magnetic_moments=parameters["advanced"]["initial_magnetic_moments"],
        pp_metadata = pp_metadata if pp_code else None
    )

    if pp_code:
        builder.findmuon.pp_metadata = pp_metadata

    if not disable_hubbard and isinstance(structure, HubbardStructureData):
        builder.structure = HubbardStructureData.from_structure(structure)
    
    return builder


workchain_and_builder = {
    "workchain": ImplantMuonWorkChain,
    "exclude": ("clean_workdir",),
    "get_builder": get_builder,
}
