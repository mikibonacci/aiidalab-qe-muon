# -*- coding: utf-8 -*-
"""Panel for FindMuonWorkchain plugin.

Authors:

    * Miki Bonacci <miki.bonacci@psi.ch>
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

import ipywidgets as ipw

from aiidalab_qe.common.panel import ConfigurationSettingsPanel
from aiidalab_qe.common.infobox import InAppGuide

from aiidalab_qe_muon.app.configuration.model import MuonConfigurationSettingsModel

from aiidalab_qe_muon.app.configuration.helper_widgets import ExternalMagneticFieldUndiWidget, SettingsInfoBoxWidget

from aiida.plugins import DataFactory

HubbardStructureData = DataFactory("quantumespresso.hubbard_structure")


class MuonConfigurationSettingPanel(
    ConfigurationSettingsPanel[MuonConfigurationSettingsModel],
):
    title = "Muon settings"
    identifier = "muonic"
    
    def __init__(self, model: MuonConfigurationSettingsModel, **kwargs):
        super().__init__(model, **kwargs)

        self._model.observe(
            self._on_input_structure_change,
            "input_structure",
        )
        
    def render(self):
        if self.rendered:
            return
           
        self.settings_help = ipw.HTML(
            """<div style="line-height: 140%; padding-top: 0px; padding-bottom: 5px">
            <h3><b>Muon spectroscopy settings</b></h3>
            Please select desired inputs to compute muon stopping sites and related properties. The muon is considered infinite-dilute
            in the crystal, so we should select a supercell in which the muon will stay and do not interact with its replica.
            If you do not provide a size for the supercell size and select "Compute supercell", a pre-processing set of simulation will be submitted
            to estimate it.<br>
            You can select the three main steps of the workflow: <b>Compute supercell size</b>, <b>Search for muon sites</b>, and <b>Compute polarization </b>.
            Computing only the polarization requires the muon (H atom) already placed in the structure as last site. 
            Supercell size and muon stopping sites are computed by means of the <b><a href="https://positivemuon.github.io/aiida-muon/"
            target="_blank">aiida-muon</b></a> plugin (<a href="https://doi.org/10.1039/D4DD00314D"
            target="_blank">Onuorah et al., Digital Discovery, 2025</a>). The polarization is computed via the <b><a href="https://undi.readthedocs.io/en/latest/index.html"
            target="_blank">UNDI</b></a> package (<a href="https://doi.org/10.1016/j.cpc.2020.107719"
            target="_blank">Bonfà et al., Comput. Phys. Commun. 260, 107719, 2021</a>), using the method by Celio
            (<a href="https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.56.2720"target="_blank">Celio, Phys. Rev. Lett. 56, 2720, 1986</a>), and considering only the muon-nuclear interactions.
            </div>"""
        )
        
        self.warning_banner = ipw.HTML('Please select at list on among the three main steps of the workflow.')
        self.warning_banner.layout.display = "none"
        
        self._model.check_polarization_allowed()
        
        # Supercell size view and control
        self.compute_supercell = ipw.Checkbox(
            description="Compute supercell size ",
            indent=False,
            value=self._model.compute_supercell,
            tooltip="Compute the supercell size by running an additional set of simulations.",
            layout=ipw.Layout(width="250px"),
        )
        ipw.link(
            (self.compute_supercell, "value"),
            (self._model, "compute_supercell"),
        )
        
        self.compute_findmuon = ipw.Checkbox(
            description="Search for muon sites ",
            indent=False,
            value=self._model.compute_findmuon,
            tooltip="Run the workflow to find candidate muon resting sites.",
            layout=ipw.Layout(width="250px"),
        )
        ipw.link(
            (self.compute_findmuon, "value"),
            (self._model, "compute_findmuon"),
        )
        ipw.dlink(
            (self.compute_findmuon, "value"),
            (self.compute_supercell, "disabled"),
            lambda x: not x, # disable if compute_findmuon is not selected
        )
        self.compute_findmuon.observe(self._on_compute_findmuon_change, "value")
        
        self.compute_polarization_undi = ipw.Checkbox(
            description="""Compute polarization (only &mu;-nuclei interactions) """,
            indent=False,
            value=self._model.compute_polarization_undi,
            tooltip="Compute the compute polarization for muon resting site(s).",
            layout=ipw.Layout(width="500px"),
        )
        ipw.link(
            (self.compute_polarization_undi, "value"),
            (self._model, "compute_polarization_undi"),
        )
        ipw.dlink(
            (self._model, "polarization_allowed"),
            (self.compute_polarization_undi, "disabled"),
            lambda x: not x, # disable if polarization is not allowed
        )
        
        self.why_no_pol_text = ipw.HTML(
            """
             - <b>Disabled</b>: no abundant isotopes with spin > 1/2 are found in the structure.        
            """
        )
        self.why_no_pol_text.layout.display = "none" if self._model.polarization_allowed else "block"               
        
        self.compute_options_box = ipw.VBox(
            children=[
            self.compute_findmuon,
            ipw.HBox([self.compute_supercell], layout=ipw.Layout(padding="0 0 0 20px")),
            ipw.HBox([self.compute_polarization_undi, self.why_no_pol_text], layout=ipw.Layout(padding="0 0 0 20px")),
            ],
        )
        
        self.override_defaults_help_title = ipw.HTML("<h5><b> - Override default DFT+&mu; parameters</b></h5>")
        self.override_defaults_help = SettingsInfoBoxWidget(
            info="""&#8613; Override defaults - <b>only for experts</b><br>Due to the large computational cost of muon calculations (infinite dilute defect), the suggested parameters are based on a rule of thumb/experience
                of the experts (the develop of this plugin and the aiida-muon plugin): 
                <br>
                <ul>
                    <li>the k-points distance is set to 0.3 Å<sup>-1</sup>;</li>
                    <li>the convergence threshold for SCF step is set to 10<sup>-6</sup>;</li>
                    <li>the smearing is "gaussian" with a width of 0.01 Ry;</li>
                </ul>
                <br>
                It is possible to override this defaults and use the convergence settings and k-points distance defined in the "Advanced settings" tab.
                """,
        )
        self.override_defaults = ipw.Checkbox(
            description="Override default settings",
            indent=False,
            value=False,
            tooltip="Override the default settings for the workflow.",
        )
        ipw.dlink(
            (self.override_defaults, "value"),
            (self._model, "override_defaults"),
        )
        self.override_defaults_box = ipw.VBox([
            ipw.HBox([
                self.override_defaults_help_title,
                self.override_defaults_help,
                self.override_defaults,
                ]),
                self.override_defaults_help.infobox,
        ])
        
        # Charge state view and control (the control is the link, and observe() if any)
        self.charge_help_title = ipw.HTML("<h5><b> - Muon charge state</b></h5>")
        self.charge_help = SettingsInfoBoxWidget(
            info="""&#8613; Charge of the muon<br>If you select a neutral muon, this will resemble the "muonium" state. It represents the analogous of the hydrogen
            atom (it can be thought as one of its lightest isotopes), which is the
            most simplest defects in a semiconductor. The electronic structure of H
            and muonium are then expected to be identical;
            at variance, vibrational properties are not, as their mass is different.
                """,
        )
        self.charge_options = ipw.ToggleButtons(
            options=self._model.charge_options,
            value=True,
            style={"description_width": "initial"},
        )
        ipw.link(
            (self.charge_options, "value"),
            (self._model, "charge_state"),
        )
        self.charge_box = ipw.VBox([
            ipw.HBox([
                self.charge_help_title,
                self.charge_options,
                self.charge_help,
            ]),
            self.charge_help.infobox,
        ])
        
        supercell_size_title = ipw.HTML("<h5><b> - Muon supercell</b></h5>")
        supercell_size_text = SettingsInfoBoxWidget(
            info="""&#8613; Defective supercell<br>Here you can specify the supercell size for the search of muon resting sites in the infinite dilute defect limit. 
            If `compute_supercell` is not selected, this will be the supercell 
            size used in the search for muon resting sites. <br>
            
            <b>Note</b>:The hint supercell is computed based on a minimum requirement of 9 Å for the length of each lattice vector of the cell.
            """,
        )
        self.supercell_x = ipw.BoundedIntText(
            min=1,
            layout={"width": "40px"},
            continuous_update=True,
        )
        ipw.link(
            (self._model, "supercell_x"),
            (self.supercell_x, "value"),
        )
        ipw.link(
            (self._model, "disable_x"),
            (self.supercell_x, "disabled"),
        )
        ipw.dlink(
            (self.compute_supercell, "value"),
            (self.supercell_x, "disabled"),
            lambda x: not (not x and self._model.compute_findmuon), # disable if compute_supercell is selected or we don't want to compute findmuon
        )
        self.supercell_x.observe(self._on_supercell_change, "value")
        self.supercell_y = ipw.BoundedIntText(
            min=1,
            layout={"width": "40px"},
            continuous_update=True,
        )       
        ipw.link(
            (self._model, "supercell_y"),
            (self.supercell_y, "value"),
        )
        ipw.link(
            (self._model, "disable_y"),
            (self.supercell_y, "disabled"),
        )
        ipw.dlink(
            (self.compute_supercell, "value"),
            (self.supercell_y, "disabled"),
            lambda x: not (not x and self._model.compute_findmuon),
        )
        self.supercell_y.observe(self._on_supercell_change, "value")
        self.supercell_z = ipw.BoundedIntText(
            min=1,
            layout={"width": "40px"},
            continuous_update=True,
        )
        ipw.link(
            (self._model, "supercell_z"),
            (self.supercell_z, "value"),
        )
        ipw.link(
            (self._model, "disable_z"),
            (self.supercell_z, "disabled"),
        )
        ipw.dlink(
            (self.compute_supercell, "value"),
            (self.supercell_z, "disabled"),
            lambda x: not (not x and self._model.compute_findmuon),
        )
        self.supercell_z.observe(self._on_supercell_change, "value")
        
        ## Supercell size hint
        self.supercell_hint = ipw.Button(
            description="Supercell hint",
            disabled=False,
            tooltip="Estimate the supercell size based on a minimum requirement of 9 Angstrom for the lattice vectors.",
            button_style="info",
        )
        self.supercell_hint.on_click(self._suggest_supercell)
        
        self.supercell_reset_button = ipw.Button(
            description="Reset supercell",
            disabled=False,
            button_style="warning",
        )
        # supercell hint (9A lattice params)
        self.supercell_reset_button.on_click(self._reset_supercell)
        
        self.supercell_selector = ipw.VBox(
            children=[
                ipw.HBox([
                    supercell_size_title,
                    self.supercell_x,
                    self.supercell_y,
                    self.supercell_z,
                    self.supercell_hint,
                    self.supercell_reset_button,
                    supercell_size_text,
                ],),
                supercell_size_text.infobox,
            ],
        )
        
        # Kpoints view and control
        self.kpoints_title = ipw.HTML("<h5><b> - K-points distance (Å<sup>-1</sup>)</b></h5>")
        self.kpoints_description = SettingsInfoBoxWidget(
            info="""&#8613; K-points distance<br>The k-points mesh density for the relaxation of the muon supecells.
            The value below represents the maximum distance (in Å<sup>-1</sup>) between the k-points in each direction of
            reciprocal space. <br> 
            
            <b>Note</b>: by default, the grids contain the Gamma point and are not shifted.
                """,
        )
        self.kpoints_distance = ipw.BoundedFloatText(
            min=0.0,
            step=0.05,
            value=0.3,
            disabled=False,
            continuous_update=True,
            layout=ipw.Layout(width="10%"),
        )
        ipw.link(
            (self.kpoints_distance, "value"),
            (self._model, "kpoints_distance"),
        )
        ipw.dlink(
            (self.override_defaults, "value"),
            (self.kpoints_distance, "disabled"),
        )
        self.kpoints_distance.observe(self._on_kpoints_distance_change, "value")
        
        self.reset_kpoints_distance = ipw.Button(
            description="Reset k-points",
            disabled=False,
            button_style="warning",
        )
        ipw.dlink(
            (self.override_defaults, "value"),
            (self.reset_kpoints_distance, "disabled"),
        )
        self.reset_kpoints_distance.on_click(self._reset_kpoints_distance)
                
        self.mesh_grid = ipw.HTML(value=self._model.mesh_grid)
        ipw.dlink(
            (self._model, "mesh_grid"),
            (self.mesh_grid, "value"),
        )
        ipw.dlink(
            (self.override_defaults, "value"),
            (self.mesh_grid, "value"),
            lambda x: "" if x else self._model.mesh_grid,
        )
        
        self.kpoints_box = ipw.VBox(
            [
                ipw.HBox([
                    self.kpoints_title,
                    self.kpoints_distance,
                    self.reset_kpoints_distance,
                    self.mesh_grid,
                    self.kpoints_description,
                ],
                ),
                self.kpoints_description.infobox,
            ],
        )
        ipw.dlink(
            (self.override_defaults, "value"),
            (self.kpoints_box, "layout"),
            lambda x: {"display": "none"} if x else {"display": "block"},
        )
        
        self.hubbard = ipw.Checkbox(
            description="Disable Hubbard correction (if any)",
            indent=False,
            value=False,
        )
        ipw.dlink(
            (self.hubbard, "value"),
            (self._model, "hubbard"),
        )
        
        self.spin_polarized = ipw.Checkbox(
            description="Enable spin polarised DFT (if magnetic sample)",
            indent=False,
            value=True,
            layout=ipw.Layout(justify_content="flex-start"),
        )
        ipw.dlink(
            (self.spin_polarized, "value"),
            (self._model, "spin_polarized"),
        )
        
        # Muon spacing view and control, included the estimator for the number of supercells
        self.mu_spacing_help_title = ipw.HTML("<h5><b> - Spacing for trial grid for initial muon sites (Å):</b></h5>")
        self.mu_spacing_help = SettingsInfoBoxWidget(
            info="""&#8613; &mu; spacing<br>Minimum muons distance in Å for different candidate positions in the choosen supercell. Default is 1 Å.
                The positions are generated by the aiida-muon plugin, which uses a regularly spaced grid of points in the supercell to find the best muon site.
                Symmetry equivalent sites are removed, as well as sites too close (< 1 Å) to the atoms of the structure. <br>
                <br>
                You can estimate the number of supercells (i.e. the number of trial sites) by clicking the button below.
                """,
        )
        self.mu_spacing = ipw.BoundedFloatText(
            min=0.4,
            step=0.1,
            value=1.0,
            disabled=False,
            layout = ipw.Layout(width="10%"),
            #continuous_update=True,
        )
        ipw.link(
            (self.mu_spacing, "value"),
            (self._model, "mu_spacing"),
        )
        self.mu_spacing.observe(self._on_mu_spacing_change, "value")
        
        self.mu_spacing_reset_button = ipw.Button(
            description="Reset μ-spacing",
            disabled=False,
            button_style="warning",
        )
        self.mu_spacing_reset_button.on_click(self._reset_mu_spacing)
        
        self.mu_spacing_box = ipw.VBox([
            ipw.HBox([
                self.mu_spacing_help_title,
                self.mu_spacing,
                self.mu_spacing_reset_button,
                self.mu_spacing_help,
            ]),
            self.mu_spacing_help.infobox,
        ])
        
        self.estimate_number_of_supercells = ipw.Button(
            description="Click to estimate number of muon trial sites ➡",
            disabled=False,
            layout=ipw.Layout(width="350px"),
            button_style="info",
            tooltip="Number of muon trial sites (i.e. different supercells);\nwarning: for large systems, this may take some time.",
        )
        self.estimate_number_of_supercells.on_click(self._estimate_supercells)
        self.number_of_supercells = ipw.HTML(value="")
        ipw.dlink(
            (self._model, "number_of_supercells"),
            (self.number_of_supercells, "value"),
        )
        
        self.mu_spacing_structure = SettingsInfoBoxWidget(
            info=""" """,
            description="Visualize candidate muon sites"
        )
        ipw.dlink(
            (self._model, "number_of_supercells"),
            (self.mu_spacing_structure, "layout"),
            lambda x: {"display": "none"} if x in ["", "0"] else {"display": "block"},
        )
        self.mu_spacing_structure.about_toggle.observe(self._on_mu_spacing_structure_toggle, "value")
        
        self._model.compute_mesh_grid()
            
        general_settings = [
            self.settings_help,
            self.warning_banner, # TODO: use the one from the app.
            self.compute_options_box,
        ]
        self.findmuon_settings = [
            ipw.HBox(
                [
                ipw.HTML("<h4><b> - Find muon sites settings - </b></h4>"),],
                layout=ipw.Layout(justify_content="center"),
            ),
            self.override_defaults_box,
            self.charge_box,
            self.supercell_selector,
            self.kpoints_box,
            self.hubbard,
            self.spin_polarized,
            self.mu_spacing_box,
            ipw.HBox([
                self.estimate_number_of_supercells,
                self.number_of_supercells,
                self.mu_spacing_structure,
                ],
            ),
            self.mu_spacing_structure.infobox,
            # self.moments, # TODO: add moments widget
        ]
        # we display the findmuon settings only if the compute_findmuon is selected
        # we link the display of each
        self.polarization_field_choice = ExternalMagneticFieldUndiWidget()
        
        self.polarization_field_choice_additional = ExternalMagneticFieldUndiWidget(title="Second grid of fields (mT)")
        self.polarization_field_choice.observe(self._update_fields_list_grid_2, "field_list")
        self.polarization_field_choice_additional.observe(self._update_fields_list_grid_2, "field_list")
        self._model.undi_fields = self.polarization_field_choice.field_list
        
        self.additional_grid_checkbox = ipw.Checkbox(
            description="Additional grid",
            indent=False,
            value=False,
            tooltip="Compute the polarization for an additional grid.",
        )
        ipw.dlink(
            (self.additional_grid_checkbox, "value"),
            (self.polarization_field_choice_additional, "layout"),
            lambda x: {"display": "block"} if x else {"display": "none"},
        )
        self.additional_grid_checkbox.observe(self._update_fields_list_grid_2, "value")
        
        self.polarization_settings_title = ipw.HTML(
            "<h4 style='text-align: center;'><b> - Polarization from &mu; - Nuclear interactions - </b></h4>"
        )
        self.polarization_settings_help = SettingsInfoBoxWidget(
            info="""&#8613; Relaxation function of the muon<br>The polarization is computed for the muon site(s) found in the previous 
                    step or in the muon sites already present in the structure (as last H atom). A calculation of the Kubo-Toyabe relaxation function is 
                    also performed.
                    <br>
                    Please note that, in this second case, the simulation will not involve and DFT simulation (only the UNDI package will be used). <br>
                    We compute the polarization for different values of external magnetic field, and different orientation of the sample. <br>
                    The third lattice vector of the structure should be aligned with the z cartesian direction.
                    
                    <br>
                    You can define your own magnetic field interval by specifying the minimum, the maximum and the setp values for the magnetic fields.
                    It is also possible to add a second grid, in case you want to compute the polarization for a different set of magnetic fields.
                """,
        )
        self.polarization_settings_box = ipw.HBox([
            self.polarization_settings_title,
            self.polarization_settings_help,
        ],
            layout=ipw.Layout(justify_content="center"),
        )
        
        self.polarization_field_list = ipw.HTML(value="")
        ipw.dlink(
            (self._model, "undi_fields"),
            (self.polarization_field_list, "value"),
            lambda x: f"<ul><li>Number of calculation per site: {len(x)} </li><li>Field list (mT):   ["+",  ".join([f"{field:.0f}" for field in x])+"]</li></ul>",
        )
        
        self.polarization_settings = ipw.VBox(
            [
                self.polarization_settings_box,
                self.polarization_settings_help.infobox,
                self.polarization_field_choice,
                self.additional_grid_checkbox,
                self.polarization_field_choice_additional,
                self.polarization_field_list,
            ],
            layout=ipw.Layout(width="100%")
            # TODO: add more polarization settings,
        )
        ipw.dlink(
            (self._model, "compute_polarization_undi"),
            (self.polarization_settings, "layout"),
            lambda x: {"display": "block"} if x else {"display": "none"},
        )
        self.polarization_settings.layout.display = "none" if not self._model.compute_polarization_undi else "block"
        
        self.children = [InAppGuide(identifier="muon-settings")] + \
            general_settings + self.findmuon_settings + [self.polarization_settings]
        
        self.layout = ipw.Layout(width="100%")

        self.rendered = True
    
    def _on_input_structure_change(self, _):
        self.refresh(specific="structure")
        self._model.on_input_structure_change()
        self._model.compute_suggested_supercell()
        self._model.check_polarization_allowed()
        if hasattr(self, "why_no_pol_text"):
            self.why_no_pol_text.layout.display = "none" if self._model.polarization_allowed else "block"
            
    def _on_mu_spacing_structure_toggle(self, _):
        if self.mu_spacing_structure.about_toggle.value:
            structurewidget = self._model._get_structure_view_container()
            self.mu_spacing_structure.infobox.children = [structurewidget]
            self.mu_spacing_structure.infobox.layout.display = "block"
        else:
            self.mu_spacing_structure.infobox.layout.display = "none"
            self.mu_spacing_structure.infobox.children = []
    
    def _on_compute_findmuon_change(self, _):
        with self.hold_trait_notifications():
            for widget in self.findmuon_settings:
                widget.layout.display = "none" if not self._model.compute_findmuon else "flex"
            
    def _on_supercell_change(self, _):
        self._model.compute_mesh_grid()
        
    def _suggest_supercell(self, _=None):
        """
        minimal supercell size for muons, imposing a minimum lattice parameter of 9 A.
        """
        self._model.suggest_supercell()
        
    def _reset_supercell(self, _=None):
        self._model.supercell_hint_reset()
        
    def _on_kpoints_distance_change(self, _):
        self._model.compute_mesh_grid()
        
    def _on_mu_spacing_change(self, _):
        self._model.reset_number_of_supercells()
        self.mu_spacing_structure.about_toggle.value = False
    
    def _reset_mu_spacing(self, _=None):
        self._model.mu_spacing_reset()
        
    def _estimate_supercells(self, _=None):
        self._model.estimate_number_of_supercells()
        
    def _reset_kpoints_distance(self, _=None):
        self._model.reset_kpoints_distance()
    
    def _update_fields_list_grid_2(self, _=None):
        if not self.additional_grid_checkbox.value:
            # should be already linked, but apparently does not work.
            self._model.undi_fields = self.polarization_field_choice.field_list
        else: # should be already linked, but apparently does not work.
            self._model.undi_fields = list(set(self.polarization_field_choice.field_list + self.polarization_field_choice_additional.field_list))
