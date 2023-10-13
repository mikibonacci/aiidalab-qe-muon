from aiida.orm import load_code, Dict
from aiida.plugins import WorkflowFactory
from aiida_quantumespresso.common.types import ElectronicType, SpinType

ImplantMuonWorkChain = WorkflowFactory("muon_app.implant_muon")

def get_builder(codes, structure, parameters):
    from copy import deepcopy
    
    protocol = parameters["workchain"].pop("protocol", "fast")
    pw_code = codes.get("pw")
    pp_code = codes.get("pp", None)
    
    magmom = parameters["muonic"].pop("magmom",None)
    supercell = parameters["muonic"].pop("supercell_selector", None)
    sc_matrix = [[supercell[0],0,0],[0,supercell[1],0],[0,0,supercell[2]]]

    compute_supercell = parameters["muonic"].pop("compute_supercell", False)
    mu_spacing = parameters["muonic"].pop("mu_spacing",1.0)
    kpoints_distance = parameters["muonic"].pop("kpoints_distance",0.301)
    charge_supercell = parameters["muonic"].pop("charge_supercell",True)
    
    if compute_supercell:
        sc_matrix = None
            
    trigger = "findmuon"
    

    scf_overrides = deepcopy(parameters["advanced"])
    overrides = {
        "relax":{
            "base": scf_overrides,
        },
        "pwscf": scf_overrides,
    }
    
    builder = ImplantMuonWorkChain.get_builder_from_protocol(
        pw_code=pw_code,
        pp_code=pp_code,
        structure=structure,
        protocol=protocol,
        overrides=overrides,
        trigger=trigger,
        relax_musconv=True, #but not true in the construction; in the end you relax in the first step of the QeAppWorkchain.
        magmom=magmom,
        sc_matrix=sc_matrix,
        mu_spacing=mu_spacing,
        kpoints_distance=kpoints_distance,
        charge_supercell=charge_supercell,
        electronic_type=ElectronicType(parameters["workchain"]["electronic_type"]),
        spin_type=SpinType(parameters["workchain"]["spin_type"]),
        initial_magnetic_moments=parameters["advanced"]["initial_magnetic_moments"],
        )

    return builder


workchain_and_builder = {
    "workchain": ImplantMuonWorkChain,
    "exclude": ("clean_workdir",),
    "get_builder": get_builder,
}