import typing as t
from aiida.orm import StructureData
from ase import Atoms

from aiida_workgraph import task, WorkGraph

from aiidalab_qe_muon.undi_interface.calculations.pythonjobs import undi_run, compute_KT


@task.graph_builder(outputs=[{"name": "results", "from": "context.results"}])
def multiple_undi_analysis(
    structure: Atoms,
    Bmods: t.List[t.Union[float, int]] = [0.0],
    atom_as_muon: str = 'H',
    max_hdims: t.List[t.Union[float, int]] = [1e1],
    convergence_check: bool = False,
    algorithm: str = 'fast',
    sample_size_average: int = 1000
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
            tmp = wg.add_task(
                undi_run,
                structure=structure,
                Bmod=Bmod,
                max_hdim=max_hdim,
                atom_as_muon=atom_as_muon,
                convergence_check=convergence_check,
                algorithm=algorithm,
                sample_size_average=sample_size_average,
                metadata=metadata,
                name=f"bmod_{Bmod}.max_hdim_{max_hdim}"
            )
            tmp.set_context({"results.bmod_{Bmod}_max_hdim_{max_hdim}": "tmp.outputs.results"})

    return wg


@task.graph_builder()
def UndiAndKuboToyabe(
    structure: t.Union[
        StructureData, Atoms
    ],  # should be StructureData, and then inside here we transform into ASE. for provenance.
    Bmods: t.List[t.Union[float, int]] = [0.0],
    atom_as_muon: str = 'H',
    max_hdims: t.List[t.Union[float, int]] = [1e1],
    convergence_check: bool = False,
    algorithm: str = 'fast',
    sample_size_average: int = 1000
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
    if convergence_check:
        undi_conv_task = wg.add_task(
            multiple_undi_analysis,
            structure=structure,
            Bmods=[0.0],
            max_hdims=max_hdims,
            atom_as_muon=atom_as_muon,
            convergence_check=convergence_check,
            algorithm=algorithm,
            sample_size_average=sample_size_average,
            name="convergence_check",
        )

    undi_task = wg.add_task(
        multiple_undi_analysis,
        structure=structure,
        Bmods=Bmods,
        max_hdims=max_hdims[-1:],
        atom_as_muon=atom_as_muon,
        convergence_check=False,
        algorithm=algorithm,
        sample_size_average=sample_size_average,
        name="undi_runs",
    )

    return wg
