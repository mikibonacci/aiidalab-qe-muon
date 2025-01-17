import typing as t
from aiida.orm import StructureData
from ase import Atoms

from aiida_workgraph import task, WorkGraph

from aiidalab_qe_muon.undi_interface.calculations.pythonjobs import undi_run, compute_KT

@task.graph_builder(outputs=[{"name": "results", "from": "context.tmp_out"}])
def multiple_undi_analysis(
    structure: Atoms,
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


@task.graph_builder()
def UndiAndKuboToyabe(
    structure: t.Union[
        StructureData, Atoms
    ],  # should be StructureData, and then inside here we transform into ASE. for provenance.
    B_mods: t.List[t.Union[float, int]] = [0.0],
    atom_as_muon: str = 'H',
    max_hdims: t.List[t.Union[float, int]] = [1e1],
    convergence_check: bool = False,
    algorithm: str = 'fast',
    angular_integration_steps: int = 7
):
    wg = WorkGraph()

    if isinstance(structure, StructureData):
        structure = structure.get_ase()

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

    return wg
