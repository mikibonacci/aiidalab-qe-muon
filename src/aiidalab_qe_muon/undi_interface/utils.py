
from typing import List
from aiida.orm import Node

def fetch_data(
        nodes: List[Node],
        mode: str = "plot",
    ):
    """Load the data from the nodes of undi runs.
    we distinguish if nodes are shelljobs (done as in examples_aiida/shelljob.py) or not,
    i.e. in case we submitted pythonjobs via the aiida-workgraph plugin.
    """

    # workgraph case - always the case in standard situations (qe app usage)
    if len(nodes) == 1 and "workgraph" in nodes[0].process_type:
        # this loops can be improved, for sure there is a smarter way to do this.
        main_node = nodes[0]

        search = "undi_runs"
        if mode == "analysis":
            search = "Convergence"

        descendants = (
            main_node.base.links.get_outgoing().get_node_by_label(search).called
        )
        fields = [
            node.inputs.function_kwargs.Bmod.value * 1000 for node in descendants
        ]  # mT
        selected_fields = [
            node.inputs.function_kwargs.Bmod.value * 1000 for node in descendants
        ]  # mT
        max_hdims = [
            node.inputs.function_kwargs.max_hdim.value for node in descendants
        ]
        results = [
            node.outputs.result.value["results"] for node in descendants
        ]
        isotopes = [
            [res["cluster_isotopes"], res["spins"], res["probability"]]
            for res in results[0]
        ]

        selected_isotopes = list(range(len(isotopes)))

        if mode == "plot":
            KT_output = (
                main_node.base.links.get_outgoing()
                .get_node_by_label("KuboToyabe_run")
                .outputs.result.get_dict()
            )
        else:
            KT_output = None
            
        return {
                "fields": fields,
                "selected_fields": selected_fields,
                "max_hdims": max_hdims,
                "results": results,
                "isotopes": isotopes,
                "selected_isotopes": selected_isotopes,
                "KT_output": KT_output,
            }
    
    else:
        raise NotImplementedError("shelljob case - Will never be the case in the app.")

def export_undi_polarization_data(workgraph_node):
    """Export the data from the undi polarization workgraph node for each different structure.
    
    the structure then needs to be mapped to the corresponding muon site, if findmuon is done.
    """
    results = {}
    for inputs, node in zip(workgraph_node.inputs.wg.tasks, workgraph_node.called):
        
        # TODO: add convergence check results.
        structure = workgraph_node.inputs.wg.tasks[inputs].inputs.structure.property.value
        outputs = fetch_data([node], mode="plot")
        outputs_averaged = UndiModel.computer_isotopic_averages(outputs)
        results[str(structure.pk)] = {}
        results[str(structure.pk)]["undi_output"] = outputs_averaged
        results[str(structure.pk)]["KT_output"] = outputs["KT_output"]
    
    return results