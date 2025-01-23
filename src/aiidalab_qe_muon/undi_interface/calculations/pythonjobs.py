import typing as t

from ase import Atoms
from aiida.orm import StructureData

from aiida_workgraph import task

@task.pythonjob(outputs=["results"])
def undi_run(
    structure: t.Union[
        StructureData, Atoms
    ],  # should be StructureData, and then in the pythonjob we deserialize into ASE. for provenance.
    B_mod = 0.0,
    atom_as_muon = 'H',
    max_hdim = 10e6,
    convergence_check = False,
    algorithm  = 'fast',
    angular_integration_steps  = 7,
    deserializers={
        "aiida.orm.nodes.data.structure.StructureData": "aiida_pythonjob.data.deserializer.structure_data_to_atoms"
    },
    # override the default `AtomsData`
    serializers={
        "ase.atoms.Atoms": "aiida_pythonjob.data.serializer.atoms_to_structure_data"
    }
) -> dict:
    from undi.undi_analysis import execute_undi_analysis

    results = execute_undi_analysis(
        structure,
        B_mod=B_mod,
        atom_as_muon=atom_as_muon,
        max_hdim=max_hdim,
        convergence_check=convergence_check,
        algorithm=algorithm,
        angular_integration_steps=angular_integration_steps
    )

    return {"results": results}


@task.pythonjob(outputs=["results"])
def compute_KT(
    structure: t.Union[
        StructureData, Atoms
    ],  # should be StructureData, and then in the pythonjob we deserialize into ASE. for provenance.
    deserializers={
        "aiida.orm.nodes.data.structure.StructureData": "aiida_pythonjob.data.deserializer.structure_data_to_atoms"
    },
    # override the default `AtomsData`
    serializers={
        "ase.atoms.Atoms": "aiida_pythonjob.data.serializer.atoms_to_structure_data"
    }
):
    import numpy as np
    from undi.kubo_toyabe.KT import compute_second_moments, kubo_toyabe

    t = np.linspace(0, 20e-6, 1000)  # time is seconds
    sm = compute_second_moments(structure)
    KT = kubo_toyabe(t, np.sum(list(sm.values())))

    return {
        "results": {
            "t": (np.array(t)*1e6).tolist(), # this time is in microseconds
            "KT": KT,
        },
    }
