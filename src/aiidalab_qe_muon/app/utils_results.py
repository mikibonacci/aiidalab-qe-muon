from aiida import orm

import numpy as np
import pandas as pd

from pymatgen.core import Structure

# spinner for waiting time (supercell estimations)
spinner_html = """
<style>
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.spinner {
  display: inline-block;
  width: 15px;
  height: 15px;
}

.spinner div {
  width: 100%;
  height: 100%;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3498db;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
</style>
<div class="spinner">
  <div></div>
</div>
"""

dictionary_of_names_for_html = {
    # "tot_energy":"total energy (eV)",
    "muon_position_cc": "muon position (crystal coordinates)",
    "delta_E": "ΔE<sub>total</sub> (eV)",
    "structure": "structure pk",
    "B_T": "B<sub>total</sub> (T)",
    "Bdip": "B<sub>dipolar</sub> (T)",
    "hyperfine": "B<sub>hyperfine</sub> (T)",
    "B_T_norm": "|B<sub>total</sub>| (T)",
    "Bdip_norm": "|B<sub>dip</sub>| (T)",
    "hyperfine_norm": "|B<sub>hyperfine</sub>| (T)",
}
