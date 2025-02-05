dictionary_of_names_for_html = {
    "structure_id_pk": "Structure id (pk)",
    "label": "Label",
    "delta_E": "ΔE<sub>total</sub> (meV)",
    "tot_energy":"E<sub>total</sub> (meV)",
    "muon_position_cc": "<vec>R</vec><sub>μ</sub> (crystal coordinates)",
    "B_T": "B<sub>total</sub> (T)",
    "Bdip": "B<sub>dipolar</sub> (T)",
    "B_hf": "B<sub>hf</sub> (T)",
    "B_T_norm": "|B<sub>total</sub>| (T)",
    "Bdip_norm": "|B<sub>dip</sub>| (T)",
    "B_hf_norm": "|B<sub>hf</sub>| (T)",
    "muon_index_global_unitcell": "μ<sub>index</sub>",
}

no_Bfield_sentence = """
<br> <b>Note</b>: no local magnetic field is computed: no magnetic elements and spin-orbit coupling in the simulation.
"""

color_code = {
    "delta_E": "black",
    "B_T_norm": "blue",
    "Bdip_norm": "green",
    "B_hf_norm": "purple",
}

unit_cell_explanation_text = """
Switching to the "Compare muon sites mode", the detected muon sites are placed in the unit cell of the (unrelaxed) structure.
<b>Note</b> that this is not resembling what is done in the simulation, where there is one supercell (not the unit one) for each different muon
trial position. This is just an additional view mode to help the user in comparing muon sites.
"""