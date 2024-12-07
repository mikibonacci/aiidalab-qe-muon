from ase import Atoms
from aiida_workgraph import task


@task.pythonjob()
def undi_run(
    structure: Atoms,
    Bmod = 0.0,
    atom_as_muon = 'H',
    max_hdim = 1000,
    convergence_check = False,
    algorithm  = 'fast',
    sample_size_average  = 1000
) -> dict:
    from undi.undi_analysis import execute_undi_analysis

    results = execute_undi_analysis(
        structure,
        Bmod=Bmod,
        atom_as_muon=atom_as_muon,
        max_hdim=max_hdim,
        convergence_check=convergence_check,
        algorithm=algorithm,
        sample_size_average=sample_size_average
    )

    return {"results": results}


@task.pythonjob()
def compute_KT(
    structure: Atoms,
):
    import numpy as np
    from aiidalab_qe_muon.workflows.utils.KT import compute_second_moments, kubo_toyabe

    t = np.linspace(0, 20e-6, 1000)  # time is microseconds
    sm = compute_second_moments(structure)
    KT = kubo_toyabe(t, np.sum(list(sm.values())))

    return {
        "results": {
            "t": t,
            "KT": KT,
        },
    }
