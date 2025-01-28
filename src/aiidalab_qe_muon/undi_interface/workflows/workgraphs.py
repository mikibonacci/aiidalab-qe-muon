import typing as t
from aiida.orm import StructureData
from ase import Atoms

from aiida_workgraph import task, WorkGraph

from aiidalab_qe_muon.undi_interface.calculations.pythonjobs import undi_run, compute_KT

@task.graph_builder(outputs=[{"name": "results", "from": "context.tmp_out"}])
def multiple_undi_analysis(
    structure: t.Union[
        StructureData, Atoms
    ],  # should be StructureData, and then in the pythonjob we deserialize into ASE. for provenance.
    B_mods: t.List[t.Union[float, int]] = [0.0],
    atom_as_muon: str = 'H',
    max_hdims: t.List[t.Union[float, int]] = [1e1],
    convergence_check: bool = False,
    algorithm: str = 'fast',
    angular_integration_steps: int = 7
):
    wg = WorkGraph()

    # UNDI RUNS ON 1 THREAD!
    metadata = {
        "options": {
            "custom_scheduler_commands": "export OMP_NUM_THREADS=1",
        }
    }
    
    t = 0
    for B_mod in B_mods:
        for max_hdim in max_hdims:
            tmp = wg.add_task(
                undi_run,
                structure=structure,
                B_mod=B_mod,
                max_hdim=max_hdim,
                atom_as_muon=atom_as_muon,
                convergence_check=convergence_check,
                algorithm=algorithm,
                angular_integration_steps=angular_integration_steps,
                metadata=metadata,
                name=f"iter_{t}"
            )
            tmp.set_context({f"tmp_out.iter_{t}": "results"})
            t+=1

    return wg


@task.graph_builder(
    outputs=[
        {"name": "results", "from": "context.res"},
        ]
)
def UndiAndKuboToyabe(
    structure: t.Union[
        StructureData, Atoms
    ],  # should be StructureData, and then in the pythonjob we deserialize into ASE. for provenance.
    B_mods: t.List[t.Union[float, int]] = [0.0],
    atom_as_muon: str = 'H',
    max_hdims: t.List[t.Union[float, int]] = [1e1],
    convergence_check: bool = False,
    algorithm: str = 'fast',
    angular_integration_steps: int = 7
):
    wg = WorkGraph()

    # This conversion is done in the pythonjob de-serialization
    #if isinstance(structure, StructureData):
    #    structure = structure.get_ase()

    # KT
    # KT RUNS ON 1 THREAD!
    metadata = {
        "options": {
            "custom_scheduler_commands": "export OMP_NUM_THREADS=1",
        }
    }
    KT_task = wg.add_task(
        compute_KT,
        structure=structure,
        name="KuboToyabe_run",
        metadata=metadata,
    )
    KT_task.set_context({f"res.KT_task": "results"})
    
    # Convergence check
    # in the future, we can add a logic to first converge, and then run UNDI for the B_mods list
    if convergence_check:
        undi_conv_task = wg.add_task(
            multiple_undi_analysis,
            structure=structure,
            B_mods=[0.0],
            max_hdims=max_hdims,
            atom_as_muon=atom_as_muon,
            convergence_check=convergence_check,
            algorithm=algorithm,
            angular_integration_steps=angular_integration_steps,
            name="convergence_check",
        )
        undi_conv_task.set_context({f"res.undi_conv_task": "results"})

    undi_task = wg.add_task(
        multiple_undi_analysis,
        structure=structure,
        B_mods=B_mods,
        max_hdims=max_hdims[-1:],
        atom_as_muon=atom_as_muon,
        convergence_check=False,
        algorithm=algorithm,
        angular_integration_steps=angular_integration_steps,
        name="undi_runs",
    )
    undi_task.set_context({f"res.undi_task": "results"})

    return wg

@task.graph_builder(outputs=[{"name": "results", "from": "context.res"}])
def MultiSites(
    structure_group,
    ):
    
    wg = WorkGraph("PolarizationMultiSites")
    
    for i, (idx, structure) in enumerate(structure_group.items()):
        res = wg.add_task(
            UndiAndKuboToyabe,
            structure=structure,
            B_mods=[0, 2e-3, 4e-3, 6e-3, 8e-3],  # for now, hardcoded.
            max_hdims=[10**2, 10**3, 10**4],  # for now, hardcoded.
            convergence_check=i==0,  # maybe the convergence can be done for only one site, as done here now.
            algorithm='fast',
            name=f"polarization_structure_{idx}",
        )
        res.set_context({f"res.site_{idx}": "results"})
    
    return wg