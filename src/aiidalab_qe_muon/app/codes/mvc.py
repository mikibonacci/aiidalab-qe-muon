from aiidalab_qe.common.code.model import CodeModel, PwCodeModel
from aiidalab_qe.common.panel import ResourceSettingsModel, ResourceSettingsPanel


class MuonResourceSettingsModel(ResourceSettingsModel):
    """Resource settings for the muon calculations."""

    codes = {
        "pw_muons": PwCodeModel(
            description="pw.x for muon search",
            default_calc_job_plugin="quantumespresso.pw",
        ),
        "pp_muons": CodeModel(
            name="pp.x",
            description="pp.x for post processing",
            default_calc_job_plugin="quantumespresso.pp",
        ),
    }


class MuonResourcesSettingsPanel(ResourceSettingsPanel[MuonResourceSettingsModel]):
    """Panel for the resource settings for the muon calculations."""

    title = "Muonic"
    identifier = "muonic"
