from aiidalab_qe.common.code.model import CodeModel, PwCodeModel
from aiidalab_qe.common.panel import (
    PluginResourceSettingsModel,
    PluginResourceSettingsPanel,
)

class MuonResourceSettingsModel(PluginResourceSettingsModel):
    """Resource settings for the muon calculations."""
    
    title = "Muon Resources"
    identifier = "muonic"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.add_models({
                "pw_muons": PwCodeModel(
                    description="pw.x for muon search",
                    default_calc_job_plugin="quantumespresso.pw",
                ),
                "pp_muons": CodeModel(
                    name="pp.x",
                    description="pp.x for post processing",
                    default_calc_job_plugin="quantumespresso.pp",
                ),
                "undi_code": CodeModel(
                    name="python",
                    description="Python code for polarization calculation",
                    default_calc_job_plugin="pythonjob.pythonjob",
                ),
            },
        )


class MuonResourcesSettingsPanel(PluginResourceSettingsPanel[MuonResourceSettingsModel]):
    """Panel for the resource settings for the muon calculations."""

    title = "MUON"
