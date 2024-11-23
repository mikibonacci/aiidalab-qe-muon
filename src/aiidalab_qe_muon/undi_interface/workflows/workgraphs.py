import typing as t
from aiida.orm import StructureData
from ase import Atoms

from aiida_workgraph import task, WorkGraph

from aiidalab_qe_muon.undi_interface.calculations.pythonjobs import undi_run, compute_KT


@task.graph_builder()
def multiple_undi_analysis(
    structure: Atoms,
    Bmods: t.List[t.Union[float, int]] = [0.0],
    max_hdims: t.List[t.Union[float, int]] = [1e1],
):
    wg = WorkGraph(name="undi_runs")

    # UNDI RUNS ON 1 THREAD!
    metadata = {
        "options": {
            "custom_scheduler_commands": "export OMP_NUM_THREADS=1",
        }
    }

    for Bmod in Bmods:
        for max_hdim in max_hdims:
            wg.add_task(
                undi_run,
                structure=structure,
                Bmod=Bmod,
                max_hdim=max_hdim,
                metadata=metadata,
                # name=f"undi_single_run"
            )

    return wg


@task.graph_builder()
def UndiAndKuboToyabe(
    structure: t.Union[
        StructureData, Atoms
    ],  # should be StructureData, and then inside here we transform into ASE. for provenance.
    Bmods: t.List[float] = [0.0],
    max_hdims: t.List[int] = [1e1],
    convergence: bool = False,
):
    wg = WorkGraph(name="Full_Undi_and_KT_subworkflow")

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
    # in the future, we can add a logic to first converge, and then run UNDI for the Bmods list
    if convergence:
        undi_conv_task = wg.add_task(
            multiple_undi_analysis,
            structure=structure,
            Bmods=[0.0],
            max_hdims=max_hdims,
            name="Convergence",
        )

    undi_task = wg.add_task(
        multiple_undi_analysis,
        structure=structure,
        Bmods=Bmods,
        max_hdims=max_hdims[-1:],
        name="undi_runs",
    )

    return wg
