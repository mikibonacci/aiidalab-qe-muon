from aiida import orm, load_profile
from aiida.orm import SinglefileData

load_profile()

"""In this example we will launch a shell job that will run the undi script with the given arguments.
"""

max_hdim = 1000
Bmod_list = 0.0  # (0.0, 0.001, 0.003, 0.007, 0.008, 0.01)
nodes = []
for Bmod in Bmod_list:
    results, node = launch_shell_job(
        "/opt/conda/bin/python",
        arguments="-m undi --max-hdim {max_hdim} --atom-as-muon H --Bmod {Bmod} {cifdata} --dump  True",
        nodes={
            "cifdata": SinglefileData(
                "/home/jovyan/work/undi_exps/Cu6H.cif", "Cu6H.cif"
            ),
            "max_hdim": orm.Int(max_hdim),
            "Bmod": orm.Float(Bmod),
        },
        filenames={
            "cifdata": "Cu6H.cif",
        },
        metadata={
            "options": {
                "prepend_text": "export OMP_NUM_THREADS=1",
                "redirect_stderr": True,
            },
        },
        outputs=["results.json"],
        # submit=True,
    )
    nodes.append(node)
    print(f"Submitted undi run at node with pk: {node}")
