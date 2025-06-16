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

def get_magmom_from_starting_magnetization(structure, starting_magnetization: dict) -> list:
    """
    Get the starting magmom list from the starting_magnetization key in the
    parameters dictionary.
    """
    magmom = []
    for site in structure.sites:
        if site.kind_name in starting_magnetization:
            magmom.append([starting_magnetization[site.kind_name],0.0, 0.0])
        else:
            magmom.append([0.0, 0.0, 0.0])
    return magmom

def create_resource_config(code_details):
    """
    Create a dictionary with resource configuration based on codes for 'pw'.

    Parameters:
        codes (dict): A dictionary containing the code configuration.

    Returns:
        dict: A nested dictionary with structured resource configurations.
    """
    metadata = {
        "options": {
            "resources": {
                "num_machines": code_details["nodes"],
                "num_mpiprocs_per_machine": code_details["ntasks_per_node"],
                "num_cores_per_mpiproc": code_details["cpus_per_task"],
            },
        }
    }

    if "max_wallclock_seconds" in code_details:
        metadata["options"]["max_wallclock_seconds"] = code_details[
            "max_wallclock_seconds"
        ]

    return metadata


def get_builder(codes, structure, parameters):
    from copy import deepcopy

    protocol = parameters["workchain"].pop("protocol", "fast")
    pw_code = codes.get("pw_muons")["code"]
    pp_code = codes.get("pp_muons")["code"]
    undi_code = codes.get("undi_code")["code"]

    # TODO: magmoms are not parsed up to now!!!
    magmom = parameters["muonic"].pop("magmoms", None)
    if not magmom or len(magmom) != len(structure.sites):
        magmom = structure.base.extras.all.get("magmom", None)
    supercell_x = parameters["muonic"].pop("supercell_x", 1)
    supercell_y = parameters["muonic"].pop("supercell_y", 1)
    supercell_z = parameters["muonic"].pop("supercell_z", 1)
    sc_matrix = [[supercell_x, 0, 0], [0, supercell_y, 0], [0, 0, supercell_z]]

    # The three step of the workflow.
    compute_supercell = parameters["muonic"].pop("compute_supercell", False)
    compute_findmuon = parameters["muonic"].pop("compute_findmuon", False)
    compute_polarization_undi = parameters["muonic"].pop("compute_polarization_undi", False)
    
    mu_spacing = parameters["muonic"].pop("mu_spacing", 1.0)
    kpoints_distance = parameters["muonic"].pop("kpoints_distance", 0.301)
    charge_supercell = parameters["muonic"].pop("charge_state", True)

    gamma_pre_relax = parameters["muonic"].pop("compute_gamma_pre_relax", True)

    hubbard = not parameters["muonic"].pop("hubbard", False) # hubbard = True here means we DISABLE the hubbard correction (the checkbox in setting is for disabling).

    enforce_defaults = parameters["muonic"].pop("use_defaults", True)
    
    trigger = "findmuon"

    spin_pol_dft = parameters["muonic"].pop("spin_polarized", True)
    scf_overrides = deepcopy(parameters["advanced"])
    
    spin_type = SpinType.NONE # we don't use the spin type in the workchain.
    
    if "initial_magnetic_moments" in scf_overrides:
        if isinstance(scf_overrides["initial_magnetic_moments"], dict):
            if len(scf_overrides["initial_magnetic_moments"])>0:
                magmom = get_magmom_from_starting_magnetization(structure, scf_overrides.pop("initial_magnetic_moments"))
                scf_overrides["pw"]["parameters"]["SYSTEM"].pop("starting_magnetization", None)
                scf_overrides["pw"]["parameters"]["SYSTEM"].pop("nspin", None)
         
    overrides = {
        # "relax":{
        "base": scf_overrides,
        #    },
        "pwscf": scf_overrides,
    }
        
    # we always enforce the mixing mode and num_steps
    overrides["base"]["pw"]["parameters"]["ELECTRONS"]["mixing_mode"] = "local-TF"
    overrides["pwscf"]["pw"]["parameters"]["ELECTRONS"]["mixing_mode"] ="local-TF"
    overrides["base"]["pw"]["parameters"]["ELECTRONS"]["electron_maxstep"] = 500
    overrides["pwscf"]["pw"]["parameters"]["ELECTRONS"]["electron_maxstep"] = 500

    
    #pseudo_family = parameters["muonic"].pop("pseudo_choice", "")
    # dummy logic.
    pseudo_family = overrides["base"]["pseudo_family"]
        
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
    
    undi_metadata = create_resource_config(codes.get("undi_code"))
    #undi_metadata["options"]["prepend_text"] =  \
    #    f'export OMP_NUM_THREADS={undi_metadata["options"]["resources"]["num_cores_per_mpiproc"]}'
    
    if compute_polarization_undi:
        undi_fields = list(set(parameters["muonic"].pop("undi_fields", [])))
        # conversion from mT to T: 
        undi_fields = [field * 1e-3 for field in undi_fields]
        
        if protocol == "fast":
            undi_max_hdims = [10**2, 10**4, 10**6]
        else:
            undi_max_hdims = []
    else:
        undi_fields = []
        undi_max_hdims = []
    
    builder = ImplantMuonWorkChain.get_builder_from_protocol(
        pw_muons_code=pw_code,
        pp_code=pp_code,
        undi_code=undi_code,
        undi_metadata=undi_metadata,
        pseudo_family=pseudo_family,
        structure=structure,
        protocol=protocol,
        enforce_defaults = enforce_defaults,
        compute_findmuon=compute_findmuon,
        compute_polarization_undi=compute_polarization_undi,
        undi_fields=undi_fields if len(undi_fields) > 0 else None,
        undi_max_hdims=undi_max_hdims if len(undi_max_hdims) > 0 else None,
        overrides=overrides,
        trigger=trigger,
        relax_unitcell=False,  # but not true in the construction; in the end you relax in the first step of the QeAppWorkchain.
        magmom=magmom,
        sc_matrix=sc_matrix,
        mu_spacing=mu_spacing,
        kpoints_distance=kpoints_distance,
        charge_supercell=charge_supercell,
        hubbard=hubbard,
        electronic_type=ElectronicType(parameters["workchain"]["electronic_type"]),
        spin_type=spin_type,
        pp_metadata = pp_metadata if pp_code else None,
        spin_pol_dft=spin_pol_dft,
        gamma_pre_relax=gamma_pre_relax,
    )

    if "parallelization" in codes.get("pw_muons"):
        parallelization = codes.get("pw_muons")["parallelization"]
        builder.findmuon.relax.base.pw.parallelization = Dict(
            dict=parallelization
        )
        builder.findmuon.pwscf.pw.parallelization = Dict(
            dict=parallelization
        )

    if pp_code:
        builder.findmuon.pp_metadata = pp_metadata
    
    
    return builder


workchain_and_builder = {
    "workchain": ImplantMuonWorkChain,
    "exclude": ("clean_workdir",),
    "get_builder": get_builder,
}
