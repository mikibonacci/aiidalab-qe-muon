from ase import Atoms
from aiida_workgraph import task


@task.pythonjob()
def undi_run(
    structure: Atoms,
    Bmod=0,  # this will not work, I need to import typing: t.Union[float,int] = 0,
    max_hdim=1e3,  # this will not work, I need to import typing: t.Union[float,int] = 1e3,
) -> dict:
    from undi.undi_analysis import execute_undi_analysis

    results = execute_undi_analysis(
        structure,
        Bmod=Bmod,
        max_hdim=max_hdim,
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
