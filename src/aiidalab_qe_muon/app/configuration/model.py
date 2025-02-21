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

from aiida_muon.utils.sites_supercells import niche_add_impurities, gensup, compute_suggest_supercell_size, generate_supercell_with_impurities

from undi.undi_analysis import check_enough_isotopes

class MuonConfigurationSettingsModel(ConfigurationSettingsModel, HasInputStructure):
    
    title = "Muon Settings"
    
    dependencies = [
        "input_structure",
    ]
    
    # the following three define the three possible workflow steps.
    compute_supercell = tl.Bool(False)
    compute_findmuon = tl.Bool(True)
    compute_polarization_undi = tl.Bool(True)
    
    charge_options = [ # does not need to be a trait
            ("Muon (+1)", True),
            ("Muonium (neutral)", False)
        ]
    charge_state = tl.Bool(True)
    mu_spacing = tl.Float(1.0)
    
    hubbard = tl.Bool(True)
    spin_polarized = tl.Bool(True)
    kpoints_distance = tl.Float(0.3)
    mesh_grid = tl.Unicode("")
    
    override_defaults = tl.Bool(False) # default are the one of the muons, not the one of QE or the QEapp. overriding means using the defaults (protocols) of the QEapp.
    
    # TODO: implement these two in MVC
    specific_pseudofamily = tl.Unicode("")
    warning_banner = tl.List(
        trait=tl.Unicode(""),
        default_value=["", ""]
    )
    
    # Traits for number of supercell estimator, relatred to muon spacing
    number_of_supercells = tl.Unicode("")
    
    # Traits for the supercell size hint (related to ImpuritySupercellConvWorkChain)
    supercell_x = tl.Int(1)
    supercell_y = tl.Int(1)
    supercell_z = tl.Int(1)

    disable_x = tl.Bool(False)
    disable_y = tl.Bool(False)
    disable_z = tl.Bool(False)
    
    supercell = tl.List(
        default_value=[1,1,1],
    )
    
    polarization_allowed = tl.Bool(True)
    polarization_fields = tl.List(tl.Int())
    polarization_fields_additional = tl.List(tl.Int())

    def get_model_state(self):
        return {
            k: getattr(self, k) for k, v in self.traits().items() if
            k != "input_structure"
        }
    
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
    
    def compute_suggested_supercell(self, _=None):
        if self.input_structure:
            with self.hold_trait_notifications():
                self.supercell_hint_reset()
                suggested_3D = compute_suggest_supercell_size(self.input_structure.get_ase())

                self.suggested_supercell_x = 1
                self.suggested_supercell_y = 1
                self.suggested_supercell_z = 1
                
                # Update only dimensions that are not disabled
                if not self.disable_x:
                    self.suggested_supercell_x = int(suggested_3D[0])
                if not self.disable_y:
                    self.suggested_supercell_y = int(suggested_3D[1])
                if not self.disable_z:
                    self.suggested_supercell_z = int(suggested_3D[2])

                # Sync the updated values to the supercell list
                self.suggested_supercell = [self.suggested_supercell_x, self.suggested_supercell_y, self.suggested_supercell_z]
                self.input_structure.base.extras.set('suggested_supercell', self.suggested_supercell)
    
    def suggest_supercell(self, _=None):
        if self.input_structure:
            if not hasattr(self, "suggested_supercell"):
                self.compute_suggested_supercell()
            
            with self.hold_trait_notifications():
                self.supercell_x = self.suggested_supercell_x
                self.supercell_y = self.suggested_supercell_y
                self.supercell_z = self.suggested_supercell_z
                self.supercell = [self.supercell_x, self.supercell_y, self.supercell_z]
                
                #self.compute_mesh_grid()
                
    def supercell_hint_reset(self, _=None):
        if not self.disable_x:
            self.supercell_x = self._get_default("supercell_x")
        if not self.disable_y:
            self.supercell_y = self._get_default("supercell_x")
        if not self.disable_z:
            self.supercell_z = self._get_default("supercell_x")
        self.supercell = [self.supercell_x, self.supercell_y, self.supercell_z]
        
        self.compute_mesh_grid()
    
    def estimate_number_of_supercells(self, _=None):
        """estimate the number of supercells, given sc_matrix and mu_spacing.
        this is copied from the FindMuonWorkChain, it is code duplication.
        should be not.
        """
        if self.input_structure is None:
            return
        else:
            self.mu_lst = niche_add_impurities(
                self.input_structure.get_pymatgen_structure(),
                niche_atom = "H",
                niche_spacing = orm.Float(self.mu_spacing),
                niche_distance = 1, # distance from hosting atoms,
            )
            self.number_of_supercells = str(len(self.mu_lst))
            
    def compute_mesh_grid(self, _=None):
        if self.input_structure:
            if self.kpoints_distance > 0:
                # make supercell now supports only diagonal transformation matrices.
                supercell_ = self.input_structure.get_ase()
                
                # just to make sure they synchronize:
                self.supercell = [self.supercell_x, self.supercell_y, self.supercell_z]
                
                # then:
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
    
    def check_polarization_allowed(self, _=None):
        # This is needed to check that we can run a undi calculation:
        # if no isotopes are found, the calculation will fail, so don't allow to run it.
        if self.input_structure:
            info, isotope_list = check_enough_isotopes(self.input_structure.get_ase())
            if len(isotope_list) == 0:
                self.polarization_allowed = False
            else:
                self.polarization_allowed =  True
        else:
            self.polarization_allowed =  True
        
        if not self.polarization_allowed:
            self.compute_polarization_undi = False
    
    def on_input_structure_change(self, _=None):
        if not self.input_structure:
            self.reset()
        else:
            self.check_polarization_allowed()
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
    
    def _generate_supercell_with_impurities(self):
        if self.input_structure:

            self.supercell_with_impurities = generate_supercell_with_impurities(
                structure=self.input_structure.get_pymatgen_structure(), 
                # sc_matrix = [
                #     [self.supercell_x, 0, 0],
                #     [0, self.supercell_y, 0],
                #     [0, 0, self.supercell_z],
                # ],
                mu_spacing=self.mu_spacing, 
                mu_list=self.mu_lst if hasattr(self, "mu_lst") else None,
            )

      
    def _get_structure_view_container(self):
        """Get the structure view container for the given structure.
        
        """
        import ipywidgets as ipw
        from aiidalab_widgets_base.viewers import StructureDataViewer

        self._generate_supercell_with_impurities()
            
        structure_view_container = ipw.VBox(
                children=[
                    StructureDataViewer(orm.StructureData(pymatgen=self.supercell_with_impurities)),
                ],
                layout=ipw.Layout(
                    flex="1",
                ),
            )
        
        return structure_view_container