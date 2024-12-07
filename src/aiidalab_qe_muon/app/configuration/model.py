"""Panel for muon spectroscopy settings.

Authors:

    * Miki Bonacci <miki.bonacci@psi.ch>
"""
from aiida import orm
import traitlets as tl
import numpy as np
from aiida_quantumespresso.calculations.functions.create_kpoints_from_distance import (
    create_kpoints_from_distance,
)
from aiidalab_qe.common.mixins import HasInputStructure
from aiidalab_qe.common.panel import ConfigurationSettingsModel
from ase.build import make_supercell
from aiida_muon.workflows.find_muon import gensup, niche_add_impurities

class MuonConfigurationSettingsModel(ConfigurationSettingsModel, HasInputStructure):
    dependencies = [
        "input_structure",
    ]
    
    charge_options = [ # does not need to be a trait
            ("Muon (+1)", True),
            ("Muonium (neutral)", False)
        ]
    charge_state = tl.Bool(True)
    mu_spacing = tl.Float(1.0)
    
    compute_supercell = tl.Bool(False)
    hubbard = tl.Bool(True)
    spin_polarized = tl.Bool(True)
    kpoints_distance = tl.Float(0.3)
    mesh_grid = tl.Unicode("")
    specific_pseudofamily = tl.Unicode("")
    warning_banner = tl.List(
        trait=tl.Unicode(""),
        default_value=["", ""]
    )
    
    # Traits for number of supercell estimator, relatred to muon spacing
    number_of_supercells = tl.Unicode("")
    
    # Traits for the supercell size hint (related to ImpuritySupercellConvWorkChain)
    supercell_hint_estimator = tl.Unicode(
        "Click the button to estimate the supercell size."
    )
    supercell_x = tl.Int(1)
    supercell_y = tl.Int(1)
    supercell_z = tl.Int(1)

    disable_x = tl.Bool(False)
    disable_y = tl.Bool(False)
    disable_z = tl.Bool(False)
    
    supercell = tl.List(
        trait=tl.Int(),
        default_value=[1,1,1],
    )

    def get_model_state(self):
        return {k: v for k, v in self.traits().items()}
    
    def set_model_state(self, parameters: dict):
        for key, value in parameters.items():
            if key in self.traits():
                self.set_trait(key, value)
    
    
    def _get_default(self, trait):
        return self.traits()[trait].default_value

    def _set_default(self, trait):
        self.set_trait(trait, self._get_default(trait))
        
    def reset(self, exclude=['input_structure', 'supercell', 'warning_banner']):
        with self.hold_trait_notifications():
            for trait in self.traits():
                if trait not in exclude:
                    self._set_default(trait)
    
    
    def _validate_pseudo_family(self, change):
        """try to load the pseudo family and raise warning/exception"""
        self.warning_banner[1] = ''
        if len(change["new"]) > 0:
            try:
                family = orm.load_group(change["new"])
                if self.input_structure:
                    pseudos = family.get_pseudos(structure=self.input_structure)
                    self.warning_banner[1] = ''
            except:
                self.warning_banner[1] = f"Could not load pseudopotential family '{change['new']}'"        
    
    def suggest_supercell(self, _=None):
        if self.input_structure:
            with self.hold_trait_notifications():
                self.supercell_hint_reset()
                s = self.input_structure.get_ase()
                s = make_supercell(
                    s,
                    [
                        [self.supercell[0], 0, 0],
                        [0, self.supercell[1], 0],
                        [0, 0, self.supercell[2]],
                    ],
                )
                suggested_3D = np.round(s.cell.cellpar()[:3], 3)
                alfa_beta_gamma = np.round(s.cell.cellpar()[3:], 1)
                # Update only dimensions that are not disabled
                if not self.disable_x:
                    self.supercell_x = int(suggested_3D[0])
                if not self.disable_y:
                    self.supercell_y = int(suggested_3D[1])
                if not self.disable_z:
                    self.supercell_z = int(suggested_3D[2])

                # Sync the updated values to the supercell list
                self.supercell = [self.supercell_x, self.supercell_y, self.supercell_z]
                
                '''sc_html += f"a=" + str(abc[0]) + "Å, "
                sc_html += f"b=" + str(abc[1]) + "Å, "
                sc_html += f"c=" + str(abc[2]) + "Å; "

                sc_html += f"α=" + str(alfa_beta_gamma[0]) + "Å, "
                sc_html += f"β=" + str(alfa_beta_gamma[1]) + "Å, "
                sc_html += f"γ=" + str(alfa_beta_gamma[2]) + "Å; "

                sc_html += f"V={round(s.get_volume(),3)}Å<sup>3</sup>"
                '''
            
    def supercell_hint_reset(self, _=None):
        if not self.disable_x:
            self.supercell_x = self._get_default("supercell_x")
        if not self.disable_y:
            self.supercell_y = self._get_default("supercell_x")
        if not self.disable_z:
            self.supercell_z = self._get_default("supercell_x")
        self.supercell = [self.supercell_x, self.supercell_y, self.supercell_z]
    
    def estimate_number_of_supercells(self, _=None):
        """estimate the number of supercells, given sc_matrix and mu_spacing.
        this is copied from the FindMuonWorkChain, it is code duplication.
        should be not.
        """
        if self.input_structure is None:
            return
        else:
            mu_lst = niche_add_impurities(
                self.input_structure,
                orm.Str("H"),
                orm.Float(self.mu_spacing),
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
            self.number_of_supercells = str(len(supercell_list))
            
    def compute_mesh_grid(self, _=None):
        if self.input_structure:
            if self.kpoints_distance > 0:
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
                    orm.Float(self.kpoints_distance),
                    orm.Bool(False),
                    metadata={"store_provenance": False},
                )
                self.mesh_grid = "Mesh grid: " + str(mesh.get_kpoints_mesh()[0])
            else:
                self.mesh_grid = "Please select a number higher than 0.0"
    
    def reset_kpoints_distance(self, _=None):
        self.kpoints_distance = self._get_default("kpoints_distance")
    
    def reset_mesh_grid(self, _=None):
        self.mesh_grid = ""
    
    def reset_number_of_supercells(self, _=None):
        self.number_of_supercells = self._get_default("number_of_supercells")
    
    def mu_spacing_reset(self, _=None):
        self.mu_spacing = self._get_default("mu_spacing")
    
    
    def on_input_structure_change(self, _=None):
        if not self.input_structure:
            self.reset()
        else:
            self.disable_x, self.disable_y, self.disable_z = True, True, True
            pbc = self.input_structure.pbc

            if pbc == (False, False, False):
                # No periodicity; fully disable and reset supercell
                self.supercell_x = self.supercell_y = self.supercell_z = 1
                self.warning_banner[0] = "No periodicity detected. Super cell is disabled."
            elif pbc == (True, False, False):
                self.supercell_y = self.supercell_z = 1
                self.disable_x = False
                self.warning_banner[0] = "1D periodicity detected. Super cell is disabled in y and z."
            elif pbc == (True, True, False):
                self.supercell_z = 1
                self.warning_banner[0] = "2D periodicity detected. Super cell is disabled in z."
            elif pbc == (True, True, True):
                self.disable_x = self.disable_y = self.disable_z = False

            self.supercell = [self.supercell_x, self.supercell_y, self.supercell_z]
            
            self.compute_mesh_grid()
            #self.reset()