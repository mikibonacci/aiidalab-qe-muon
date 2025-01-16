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
from aiidalab_qe_muon.app.configuration.model import MuonConfigurationSettingsModel

from aiida.plugins import DataFactory

HubbardStructureData = DataFactory("quantumespresso.hubbard_structure")


class MuonConfigurationSettingPanel(
    ConfigurationSettingsPanel[MuonConfigurationSettingsModel],
):
    title = "Muon Settings"
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
            <h4><b>Muon spectroscopy settings</b></h4>
            Please select desired inputs to compute muon stopping sites and related properties. The muon is considered infinite-dilute
            in the crystal, so we should select a supercell in which the muon will stay and do not interact with its replica.
            If you do not provide a size for the supercell size and select "Compute supercell", a pre-processing set of simulation will be submitted
            to estimate it.<br>
            You can select the three main steps of the workflow: <b>Compute supercell</b>, <b>Search for muon sites</b>, and <b>Compute polarization</b>.
            Computing only the polarization requires the muon (H atom) already placed in the structure as last site.
            </div>"""
        )
        
        self.warning_banner = ipw.HTML('Please select at list on among the three main steps of the workflow.')
        self.warning_banner.layout.display = "none"
        
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
            description="Compute polarization ",
            indent=False,
            value=self._model.compute_polarization_undi,
            tooltip="Compute the compute polarization for muon resting site(s).",
            layout=ipw.Layout(width="250px"),
        )
        ipw.link(
            (self.compute_polarization_undi, "value"),
            (self._model, "compute_polarization_undi"),
        )
        
        
        # Charge state view and control (the control is the link, and observe() if any)
        self.charge_help = ipw.HTML(
            """<div style="line-height: 140%; padding-top: 5px; padding-bottom: 5px">
            <h5><b>Muon charge state</b></h5>
            If you select a neutral muon, this will resemble the "muonium" state. It represents the analogous of the hydrogen
            atom (it can be thought as one of its lightest isotopes), which is the
            most simplest defects in a semiconductor. The electronic structure of H
            and muonium are then expected to be identical;
            at variance, vibrational properties are not, as their mass is different.
            </div>"""
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
        
        supercell_hint_estimator = ipw.HTML(
            """<div style="line-height: 140%; padding-top: 5px; padding-bottom: 5px">
            <h5><b>Muon supercell</b></h5>
            Click the button to estimate the supercell size or defined it. 
            If `compute_supercell` is not selected, this is be the supercell 
            size used in the search of muon resting sites.
            </div>"""
        )
        self.supercell_x = ipw.BoundedIntText(
            min=1,
            layout={"width": "40px"},
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
        self.supercell_y = ipw.BoundedIntText(
            min=1,
            layout={"width": "40px"},
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
        self.supercell_z = ipw.BoundedIntText(
            min=1,
            layout={"width": "40px"},
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

        self.supercell_selector = ipw.VBox(
            children=[
                supercell_hint_estimator,
                ipw.HBox([
                    self.supercell_x,
                    self.supercell_y,
                    self.supercell_z,
                ],),
            ],
        )
        
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
        
        # Kpoints view and control
        self.kpoints_description = ipw.HTML(
            """<div style="line-height: 140%; padding-top: 5px; padding-bottom: 5px">
            <h5><b>K-points mesh density</b></h5>
            The k-points mesh density for the relaxation of the muon supecells.
            The value below represents the maximum distance between the k-points in each direction of
            reciprocal space.</div>"""
        )

        self.kpoints_distance = ipw.BoundedFloatText(
            min=0.0,
            step=0.05,
            value=0.3,
            description="K-points distance (1/Å):",
            disabled=False,
            style={"description_width": "initial"},
        )
        ipw.link(
            (self.kpoints_distance, "value"),
            (self._model, "kpoints_distance"),
        )
        self.kpoints_distance.observe(self._on_kpoints_distance_change, "value")
        
        self.reset_kpoints_distance = ipw.Button(
            description="Reset k-points",
            disabled=False,
            button_style="warning",
        )
        self.reset_kpoints_distance.on_click(self._reset_kpoints_distance)
        
        self.mesh_grid = ipw.HTML(value=self._model.mesh_grid)
        ipw.link(
            (self._model, "mesh_grid"),
            (self.mesh_grid, "value"),
        )
        
        self.hubbard = ipw.Checkbox(
            description="Disable Hubbard correction (if any): ",
            indent=False,
            value=False,
        )
        ipw.dlink(
            (self.hubbard, "value"),
            (self._model, "hubbard"),
        )
        
        self.spin_polarized = ipw.Checkbox(
            description="Enable spin polarised DFT (if magnetic sample): ",
            indent=False,
            value=True,
            layout=ipw.Layout(justify_content="flex-start"),
        )
        ipw.dlink(
            (self.spin_polarized, "value"),
            (self._model, "spin_polarized"),
        )
        
        # Muon spacing view and control, included the estimator for the number of supercells
        self.mu_spacing_help = ipw.HTML(
            """<div style="line-height: 140%; padding-top: 5px; padding-bottom: 5px">
            <h5><b>Muons site distance</b></h5>
            Muons distance in Å for different candidate positions in the choosen supercell. Default is 1 Å.</div>"""
        ) 
        self.mu_spacing = ipw.BoundedFloatText(
            min=0.05,
            step=0.05,
            value=1.0,
            description="μ-spacing (Å):",
            disabled=False,
            style={"description_width": "initial"},
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
        
        self.estimate_number_of_supercells = ipw.Button(
            description="Click to stimate number of muon trial sites ➡",
            disabled=False,
            layout=ipw.Layout(width="350px"),
            button_style="info",
            tooltip="Number of muon trial sites (i.e. different supercells);\nwarning: for large systems, this may take some time.",
        )
        self.estimate_number_of_supercells.on_click(self._estimate_supercells)
        self.number_of_supercells = ipw.HTML(value="")
        ipw.link(
            (self._model, "number_of_supercells"),
            (self.number_of_supercells, "value"),
        )
            
        general_settings = [
            self.settings_help,
            self.warning_banner, # TODO: use the one from the app.
            self.compute_supercell,
            self.compute_findmuon,
            self.compute_polarization_undi,
        ]
        self.findmuon_settings = [
            self.charge_help,
            self.charge_options,
            self.supercell_selector,
            ipw.HBox([
                self.supercell_hint,
                self.supercell_reset_button,
                ],
            ),
            self.kpoints_description,
            ipw.HBox([
                self.kpoints_distance,
                self.reset_kpoints_distance,
                self.mesh_grid,
                ],
            ),
            self.hubbard,
            self.spin_polarized,
            self.mu_spacing_help,
            ipw.HBox([
                self.mu_spacing,
                self.mu_spacing_reset_button,
                ],
            ),
            ipw.HBox([
                self.estimate_number_of_supercells,
                self.number_of_supercells,
                ],
            ),
            # self.moments, # TODO: add moments widget
        ]
        # we display the findmuon settings only if the compute_findmuon is selected
        # we link the display of each

        self.polarization_settings = [] # TODO: add polarization settings
        
        self.children = general_settings + self.findmuon_settings + self.polarization_settings
        self.rendered = True
    
    def _on_input_structure_change(self, _):
        self.refresh(specific="structure")
        self._model.on_input_structure_change()
    
    def _on_compute_findmuon_change(self, _):
        with self.hold_trait_notifications():
            for widget in self.findmuon_settings:
                widget.layout.display = "none" if not self._model.compute_findmuon else "flex"
            
    
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
    
    def _reset_mu_spacing(self, _=None):
        self._model.mu_spacing_reset()
        
    def _estimate_supercells(self, _=None):
        self._model.estimate_number_of_supercells()
        
    def _reset_kpoints_distance(self, _=None):
        self._model.reset_kpoints_distance()
        
    
    