# -*- coding: utf-8 -*-
"""Panel for FindMuonWorkchain plugin.

Authors:

    * Miki Bonacci <miki.bonacci@psi.ch>
    Inspired by Xing Wang <xing.wang@psi.ch>
"""
import ipywidgets as ipw
from aiida import orm
import traitlets as tl
import numpy as np
from aiida_quantumespresso.calculations.functions.create_kpoints_from_distance import (
    create_kpoints_from_distance,
)
from aiidalab_qe.common.panel import Panel
from ase.build import make_supercell
from aiida_muon.workflows.find_muon import gensup, niche_add_impurities

from aiidalab_qe_muon.app.utils_results import spinner_html

class Setting(Panel):
    title = "Muon Settings"
    identifier = "muonic"

    input_structure = tl.Instance(orm.StructureData, allow_none=True)

    def __init__(self, **kwargs):

        self.Warning_button = ipw.HTML(
            """<div style="padding-top: 0px; padding-bottom: 0px; color: #ff6347">
            <h1>Muon spectroscopy does not yet support low-dimensional systems: please note that the simulation will except.</h1></div>""",
        )
        self.Warning_button.layout.display = "none"

        self.settings_title = ipw.HTML(
            """<div style="padding-top: 0px; padding-bottom: 0px">
            <h4>Muon spectroscopy settings</h4></div>"""
        )
        self.settings_help = ipw.HTML(
            """<div style="line-height: 140%; padding-top: 0px; padding-bottom: 5px">
            Please select desired inputs to compute muon stopping sites and related properties. The muon is considered infinite-dilute
            in the crystal, so we should select a supercell in which the muon will stay and do not interact with its replica.
            If you do not provide a size for the supercell size and select "Compute supercell", a pre-processing step will be submitted
            to estimate it.
            </div>"""
        )

        # start charge
        self.charge_help = ipw.HTML(
            """<div style="line-height: 140%; padding-top: 5px; padding-bottom: 5px">
            <h5><b>Muon charge state</b></h5>
            If you select a neutral muon, this will resemble the "muonium" state. It represents the analogous of the hydrogen
            atom (it can be thought as one of its lightest isotopes), which is the
            most simplest defects in a semiconductor. The electronic structure of H
            and muonium are then expected to be identical;
            at variance, vibrational properties are not, as the involved masses are different.
            </div>"""
        )

        self.charged_muon_ = ipw.ToggleButtons(
            options=[("Muon (+1)", True), ("Muonium (neutral)", False)],
            value=True,
            style={"description_width": "initial"},
        )
        # end charge

        # start pseudo. VERY BAD. but needed to use gbrv in muons. because of the routine get_pseudos.
        # to change.
        ## there should be the choice between installed pseudos... use group query maybe.
        ### gbrv automatic install TODO.
        self.pseudo_choice_ = ipw.Text(
            value="",
            disabled=False,
        )
        self.pseudo_choice_.observe(self._validate_pseudo_family, "value")
        self.pseudo_label = ipw.HTML("Ad-hoc installed pseudo family:")

        self.warning_pseudo_widget = ipw.HTML(
            f"Errors... Are you sure that the written pseudo family is installed?/has every element in the structure? We rely on the SSSP/1.2/PBEsol/efficiency"
        )
        self.warning_pseudo_widget.layout.display = "none"

        # end pseudo

        self.workchain_protocol = ipw.ToggleButtons(
            options=["fast", "moderate", "precise"],
            value="moderate",
        )

        # start Supercell
        self.supercell = [1, 1, 1]

        def change_supercell(_=None):
            self.supercell = [
                self._sc_x.value,
                self._sc_y.value,
                self._sc_z.value,
            ]
            self._display_mesh()
            self._write_html_supercell()

        for elem in ["x", "y", "z"]:
            setattr(
                self,
                "_sc_" + elem,
                ipw.BoundedIntText(
                    value=1, min=1, layout={"width": "40px"}, disabled=True
                ),
            )

        for elem in [self._sc_x, self._sc_y, self._sc_z]:
            elem.observe(change_supercell, names="value")

        self.supercell_selector = ipw.HBox(
            children=[
                self._sc_x,
                self._sc_y,
                self._sc_z,
            ],
        )

        # SCell widget
        self.supercell_label = ipw.HTML(
            "Compute supercell: ",
            layout=ipw.Layout(width="120px"),
        )
        self.compute_supercell_ = ipw.Checkbox(
            description="",
            indent=False,
            value=True,
            layout=ipw.Layout(width="150px"),
        )
        # enable supercell setting
        self.compute_supercell_.observe(self._compute_supercell, "value")

        # supercell data
        self.supercell_hint_button = ipw.Button(
            description="Supercell hint",
            disabled=True,
            button_style="info",
        )
        # supercell hint (9A lattice params)
        self.supercell_hint_button.on_click(self._suggest_supercell)

        # supercell data
        self.supercell_reset_button = ipw.Button(
            description="Reset supercell",
            disabled=True,
            button_style="warning",
        )
        # supercell hint (9A lattice params)
        self.supercell_reset_button.on_click(self._reset_supercell)

        self.supercell_html = ipw.HTML(display="none")

        self.supercell_known_widget = ipw.VBox(
            [
            ipw.HBox(
                [
                self.supercell_label,
                self.compute_supercell_,
                self.supercell_hint_button,
                self.supercell_selector,
                self.supercell_reset_button,
                ],
                layout=ipw.Layout(align_items="center"),
            ),
            self.supercell_html,
            ],
        )
        # end Supercell.

        # start enable Hubbard. Temporary, with the LegacyStructureData.
        self.hubbard__label = ipw.Label(
            "Disable Hubbard correction (if any): ",
            layout=ipw.Layout(justify_content="flex-start"),
        )
        self.hubbard_ = ipw.Checkbox(
            description="",
            indent=False,
            value=False,
        )
        self.hubbard__widget = ipw.HBox(
            [self.hubbard__label, self.hubbard_],
            layout=ipw.Layout(justify_content="flex-start"),
        )
        # end enable Hubbard.

        # start enable spin_polarised DFT calcs.
        self.spin_pol_label = ipw.Label(
            "Enable spin polarised DFT: ",
            layout=ipw.Layout(justify_content="flex-start"),
        )
        self.spin_pol_ = ipw.Checkbox(
            description="",
            indent=False,
            value=True,
            layout=ipw.Layout(justify_content="flex-start"),
        )
        self.spin_pol_description = ipw.Label(
            """In case of magnetic system, it computes also the contact hyperfine field."""
        )
        self.spin_pol_widget = ipw.HBox(
            [self.spin_pol_label, self.spin_pol_, self.spin_pol_description],
            # layout=ipw.Layout(justify_content="flex-start"),
        )
        # end enable spin_polarised DFT calcs.

        # start kpoints distance: the code is the same as the advanced settings.
        self.kpoints_description = ipw.HTML(
            """<div style="line-height: 140%; padding-top: 5px; padding-bottom: 5px">
            <h5><b>K-points mesh density</b></h5>
            The k-points mesh density for the relaxation of the muon supecells.
            The value below represents the maximum distance between the k-points in each direction of
            reciprocal space.</div>"""
        )

        self.kpoints_distance_ = ipw.BoundedFloatText(
            min=0.0,
            step=0.05,
            value=0.3,
            description="K-points distance (1/Å):",
            disabled=False,
            style={"description_width": "initial"},
        )
        self.kpoints_distance_.observe(self._display_mesh, "value")
        self.mesh_grid = ipw.HTML()
        # end kpoints distance.

        # start mu spacing. We should provide also some estimation on the # of the supercell generated.
        # in conjunction with the supercell size.
        self.mu_spacing_description = ipw.HTML(
            """<div style="line-height: 140%; padding-top: 5px; padding-bottom: 5px">
            <h5><b>Muons site distance</b></h5>
            Muons distance in Å for different candidate positions in the choosen supercell. Default is 1 Å.</div>"""
        )

        self.mu_spacing_ = ipw.BoundedFloatText(
            min=0.05,
            step=0.05,
            value=1.0,
            description="mu_spacing (Å):",
            disabled=False,
            style={"description_width": "initial"},
        )
        self.mu_spacing_.observe(self._on_change_muspacing, "value")
        self.estimate_number_of_supercells_button = ipw.Button(
            description="Estimate number of muon trial sites ➡",
            disabled=False,
            layout=ipw.Layout(width="240px"),
            button_style="info",
            tooltip="Number of muon trial sites (i.e. different supercells);\nwarning: for large systems, this may take some time.",
        )
        # supercell reset reaction
        self.estimate_number_of_supercells_button.on_click(self._estimate_supercells)
        self.number_of_supercells = ipw.HTML("?")
        # end mu spacing.

        # start TEMPORARY magnetic moments settings. this should be in the structure creation.
        # self.sites_widget = SitesWidgets(self)
        self.moments = ipw.HTML()
        # end

        self.children = [
            self.Warning_button,
            self.settings_title,
            self.settings_help,
            self.supercell_known_widget,
            self.hubbard__widget,
            self.spin_pol_widget,
            self.charge_help,
            ipw.HBox(
                children=[
                    ipw.Label(
                        "Charge state:",
                        layout=ipw.Layout(justify_content="flex-start"),
                    ),
                    self.charged_muon_,
                ]
            ),
            self.kpoints_description,
            ipw.HBox([self.kpoints_distance_, self.mesh_grid]),
            self.mu_spacing_description,
            ipw.HBox([self.mu_spacing_, self.estimate_number_of_supercells_button,self.number_of_supercells]),
            ipw.VBox(
                [
                    ipw.HBox([self.pseudo_label, self.pseudo_choice_]),
                    self.warning_pseudo_widget,
                ]
            ),
            self.moments,
        ]
        super().__init__(**kwargs)

    @tl.observe("input_structure")
    def _update_input_structure(self, change):
        if self.input_structure is not None:
            self._display_mesh()
            self.number_of_supercells.value = "?"
            self.estimate_number_of_supercells_button.disabled = False
            self._display_moments()
            
    def _on_change_muspacing(self, _=None):
        self.number_of_supercells.value = "?"
        self.estimate_number_of_supercells_button.disabled = False

    def _validate_pseudo_family(self, change):
        """try to load the pseudo family and raise warning/exception"""
        if len(change["new"]) > 0:
            try:
                family = orm.load_group(change["new"])
                if self.input_structure:
                    pseudos = family.get_pseudos(structure=self.input_structure)
                    self.warning_pseudo_widget.layout.display = "none"
            except:
                self.warning_pseudo_widget.layout.display = "block"
        else:
            self.warning_pseudo_widget.layout.display = "none"

    def _compute_supercell(self, change):
        for elem in [self._sc_x, self._sc_y, self._sc_z]:
            elem.disabled = change["new"]
        self.supercell_hint_button.disabled = change["new"]
        self.supercell_reset_button.disabled = change["new"]
        self._write_html_supercell()
        self.supercell_html.layout.display = "none" if change["new"] else "block"
        
    def _reset_supercell(self, _=None):
        if self.input_structure is not None:
            for direction  in[self._sc_x, self._sc_y, self._sc_z]:
                direction.value = 1
        return

    def _display_mesh(self, _=None):
        if self.input_structure is None:
            return
        if self.kpoints_distance_.value > 0:
            # make supercell now supports only diagonal transformation matrices.
            supercell_ = self.input_structure.get_ase()
            supercell_ = make_supercell(
                supercell_,
                [
                    [self.supercell[0], 0, 0],
                    [0, self.supercell[1], 0],
                    [0, 0, self.supercell[2]],
                ],
            )
            supercell = orm.StructureData(ase=supercell_)
            mesh = create_kpoints_from_distance(
                supercell,
                orm.Float(self.kpoints_distance_.value),
                orm.Bool(False),
                metadata={"store_provenance": False},
            )
            self.mesh_grid.value = "Mesh " + str(mesh.get_kpoints_mesh()[0])
        else:
            self.mesh_grid.value = "Please select a number higher than 0.0"

    def _suggest_supercell(self, _=None):
        """
        minimal supercell size for muons, imposing a min_dist (lattice parameter) of 9 A.
        Around 8 for metal is fine, for semiconductors it has to be verified.
        """
        if self.input_structure:
            s = self.input_structure.get_ase()
            suggested = 9 // np.array(s.cell.cellpar()[:3]) + 1
            self._sc_x.value = suggested[0]
            self._sc_y.value = suggested[1]
            self._sc_z.value = suggested[2]
        else:
            return

    def _write_html_supercell(self, _=None):
        # write html for supercell data:
        if self.input_structure:
            s = self.input_structure.get_ase()
            s = make_supercell(
                s,
                [
                    [self.supercell[0], 0, 0],
                    [0, self.supercell[1], 0],
                    [0, 0, self.supercell[2]],
                ],
            )
            sc_html = "Supercell lattice parameters, angles and volume: "
            abc = np.round(s.cell.cellpar()[:3], 3)
            alfa_beta_gamma = np.round(s.cell.cellpar()[3:], 1)
            sc_html += f"a=" + str(abc[0]) + "Å, "
            sc_html += f"b=" + str(abc[1]) + "Å, "
            sc_html += f"c=" + str(abc[2]) + "Å; "

            sc_html += f"α=" + str(alfa_beta_gamma[0]) + "Å, "
            sc_html += f"β=" + str(alfa_beta_gamma[1]) + "Å, "
            sc_html += f"γ=" + str(alfa_beta_gamma[2]) + "Å; "

            sc_html += f"V={round(s.get_volume(),3)}Å<sup>3</sup>"

            self.supercell_html.value = sc_html

    def _estimate_supercells(self, _=None):
        """estimate the number of supercells, given sc_matrix and mu_spacing.
        this is copied from the FindMuonWorkChain, it is code duplication.
        should be not.
        """
        if self.input_structure is None:
            return
        else:
            if False in self.input_structure.pbc:
                self.Warning_button.layout.display = "block"
            else:
                self.number_of_supercells.value = "Number of supercells: " + spinner_html
                mu_lst = niche_add_impurities(
                    self.input_structure,
                    orm.Str("H"),
                    orm.Float(self.mu_spacing_.value),
                    orm.Float(1.0),
                    metadata={"store_provenance": False},
                )

                sc_matrix = [
                    [self.supercell[0], 0, 0],
                    [0, self.supercell[1], 0],
                    [0, 0, self.supercell[2]],
                ]
                supercell_list = gensup(
                    self.input_structure.get_pymatgen(), mu_lst, sc_matrix
                )  # ordinary function
                self.number_of_supercells.value = "Number of supercells: " + str(
                    len(supercell_list)
                )
        self.estimate_number_of_supercells_button.disabled = True
        

    def _display_moments(self, _=None):
        """
        Display the magnetic moments and set the magmoms inputs for the simulation.
        """
        if self.input_structure is None:
            self.moments = ipw.HTML()
            self.magmoms = None
        elif (
            self.input_structure and "magmom" in self.input_structure.base.extras.keys()
        ):
            text = ""
            magmoms = self.input_structure.base.extras.get("magmom")
            text += "<h5><b>Magnetic moments in the unit cell</b></h5>"
            for site, magmom in zip(self.input_structure.sites, magmoms):
                text += (
                    f"<p>{site.kind_name}, in {str(site.position)}: {str(magmom)}</p>"
                )
            self.moments.value = text
            self.magmoms = magmoms
        else:
            self.magmoms = None

        if not self.magmoms:
            self.spin_pol_.value = False
            self.spin_pol_.disabled = True
        pass

    def SitesWidget(
        self,
    ):
        """
        Widget to display sites and relative magnetic moment.
        For now, magmoms can be modified by the user.
        """
        if self.input_structure is None:
            return
        else:
            for site in self.input_structure.sites:
                pass

        return

    def get_panel_value(self):
        """Return a dictionary with the input parameters for the plugin."""

        return {
            "supercell_selector": self.supercell,
            "charged_muon": self.charged_muon_.value,
            "kpoints_distance": self.kpoints_distance_.value,
            "mu_spacing": self.mu_spacing_.value,
            "compute_supercell": self.compute_supercell_.value,
            "magmoms": self.magmoms,
            "hubbard": self.hubbard_.value,
            "spin_pol": self.spin_pol_.value,
            "pseudo_choice": self.pseudo_choice_.value,
        }

    def load_panel_value(self, input_dict):
        """Load a dictionary with the input parameters for the plugin."""
        self.charged_muon_.value = input_dict.get("charged_muon", True)
        self.compute_supercell_.value = input_dict.get("compute_supercell", False)
        self.supercell = input_dict.get("supercell_selector", [1, 1, 1])
        self.kpoints_distance_.value = input_dict.get("kpoints_distance", 0.3)
        self.mu_spacing_.value = input_dict.get("mu_spacing", 1)
        self.magmoms = input_dict.get("magmoms", None)
        self.hubbard_.value = input_dict.get("hubbard", False)
        self.spin_pol_.value = input_dict.get("spin_pol", True)
        self.pseudo_choice_.value = input_dict.get("pseudo_choice", True)

    def reset(self):
        """Reset the panel"""
        self.charged_muon_.value = True
        self.compute_supercell_.value = True
        self.supercell = [1, 1, 1]
        self.kpoints_distance_.value = 0.3
        self.mu_spacing_.value = 1
        self.magmoms = None
        self.hubbard_.value = False
        self.spin_pol_.value = True
        self.pseudo_choice_.value = ""
