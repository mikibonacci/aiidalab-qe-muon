import typing as t
from aiida_workgraph import task, WorkGraph, TaskPool
#from aiidalab_qe_muon.undi_interface.calculations.pythonjobs import undi_run, compute_KT

from aiida_workgraph import task

@task.graph_builder(outputs=[{"name": "results", "from": "ctx.tmp_out"}])
def multiple_undi_analysis(
    structure,
    B_mods: t.List[t.Union[float, int]] = [0.0], # Units are Tesla.
    atom_as_muon: str = 'H',
    max_hdims: t.List[t.Union[float, int]] = [1e1],
    convergence_check: bool = False,
    algorithm: str = 'fast',
    angular_integration_steps: int = 7,
    code = None, # if None, default python3@localhost will be used.
    metadata = {"options": {"custom_scheduler_commands": "export OMP_NUM_THREADS=1"}},
):
    
    def undi_run(
        structure, # should be StructureData, and then in the pythonjob we deserialize into ASE. for provenance.
        B_mod = 0.0,
        atom_as_muon = 'H',
        max_hdim = 10e6,
        convergence_check = False,
        algorithm  = 'fast',
        angular_integration_steps  = 7,
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

        return {"result": results}
    
    wg = WorkGraph()
    
    t = 0
    for B_mod in B_mods:
        for max_hdim in max_hdims:
            tmp = wg.add_task(
                TaskPool.workgraph.pythonjob,
                function=undi_run,
                structure=structure,
                B_mod=B_mod,
                max_hdim=max_hdim,
                atom_as_muon=atom_as_muon,
                convergence_check=convergence_check,
                algorithm=algorithm,
                angular_integration_steps=angular_integration_steps,
                metadata=metadata,
                name=f"iter_{t}",
                deserializers={
                    "aiida.orm.nodes.data.structure.StructureData": "aiida_pythonjob.data.deserializer.structure_data_to_atoms"
                },
                # override the default `AtomsData`
                serializers={
                    "ase.atoms.Atoms": "aiida_pythonjob.data.serializer.atoms_to_structure_data"
                },
                code = code,
                register_pickle_by_value=True,
            )
            wg.update_ctx({f"tmp_out.iter_{t}": tmp.outputs.result})
            t+=1

    return wg


@task.graph_builder(
    outputs=[
        {"name": "results", "from": "ctx.res"},
        ]
)
def UndiAndKuboToyabe(
    structure,
    B_mods: t.List[t.Union[float, int]] = [0.0], # Units are Tesla.
    atom_as_muon: str = 'H',
    max_hdims: t.List[t.Union[float, int]] = [1e1],
    convergence_check: bool = False,
    algorithm: str = 'fast',
    angular_integration_steps: int = 7,
    code=None, # if None, default python3@localhost will be used.
    metadata = {"options": {"custom_scheduler_commands": "export OMP_NUM_THREADS=1"}},
):
    wg = WorkGraph()

    # This conversion is done in the pythonjob de-serializat:qion
    #if isinstance(structure, StructureData):
    #    structure = structure.get_ase()
    
    def compute_KT(
        structure,  # should be StructureData, and then in the pythonjob we deserialize into ASE. for provenance.
        ):
        import numpy as np
        from undi.kubo_toyabe.KT import compute_second_moments, kubo_toyabe

        t = np.linspace(0, 20e-6, 1000)  # time is seconds
        sm = compute_second_moments(structure)
        KT = kubo_toyabe(t, np.sum(list(sm.values())))

        return {
            "result": {
                "t": (np.array(t)*1e6).tolist(), # this time is in microseconds
                "KT": KT,
            },
        }

    KT_task = wg.add_task(
        TaskPool.workgraph.pythonjob,
        function=compute_KT,
        structure=structure,
        name="KuboToyabe_run",
        code = code,
        metadata=metadata,
        deserializers={
            "aiida.orm.nodes.data.structure.StructureData": "aiida_pythonjob.data.deserializer.structure_data_to_atoms"
        },
        # override the default `AtomsData`
        serializers={
            "ase.atoms.Atoms": "aiida_pythonjob.data.serializer.atoms_to_structure_data"
        },
        register_pickle_by_value=True,
    )
    wg.update_ctx({f"res.KT_task": KT_task.outputs.result})
    
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
            code = code,
            metadata=metadata,
        )
        wg.update_ctx({f"res.undi_conv_task": undi_conv_task.outputs.results})

    undi_task = wg.add_task(
        multiple_undi_analysis,
        structure=structure,
        B_mods=B_mods,
        max_hdims=max_hdims[-2:-1],
        atom_as_muon=atom_as_muon,
        convergence_check=False,
        algorithm=algorithm,
        angular_integration_steps=angular_integration_steps,
        name="undi_runs",
        code = code,
        metadata=metadata,
    )
    wg.update_ctx({f"res.undi_task": undi_task.outputs.results})

    return wg

@task.graph_builder(outputs=[{"name": "results", "from": "ctx.res"}])
def MultiSites(
    structure_group,
    code=None, # if None, default python3@localhost will be used.
    B_mods: t.List[t.Union[float, int]] = [0, 2e-3, 4e-3, 6e-3, 8e-3], # Units are Tesla.
    max_hdims: t.List[t.Union[float, int]] = [10**2, 10**4, 10**6, 10**8], # we use the [-2:-1] for the undi run (not the convergence check, let's say).
    metadata = {"options": {"custom_scheduler_commands": "export OMP_NUM_THREADS=1"}}, # just a default.
    ):
    
    wg = WorkGraph("PolarizationMultiSites")
    
    for i, (idx, structure) in enumerate(structure_group.items()):
        res = wg.add_task(
            UndiAndKuboToyabe,
            structure=structure,
            B_mods=B_mods,
            max_hdims=max_hdims,
            convergence_check=i==0,  # maybe the convergence can be done for only one site, as done here now.
            algorithm='fast',
            name=f"polarization_structure_{idx}",
            code=code,
            metadata=metadata,
        )
        wg.update_ctx({f"res.site_{idx}": res.outputs.results})
    
    return wg