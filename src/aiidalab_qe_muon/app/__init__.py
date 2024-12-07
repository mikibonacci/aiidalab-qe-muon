from aiidalab_qe.common.panel import PluginOutline

from aiidalab_qe_muon.app.configuration.model import MuonConfigurationSettingsModel
from aiidalab_qe_muon.app.configuration.view import MuonConfigurationSettingPanel
#from aiidalab_qe_muon.app.code import (
#    MuonResourceSettingsModel,
#    MuonResourcesSettingsPanel,
#)
#from aiidalab_qe_muon.app.result.result import MuonResultsPanel
#from aiidalab_qe_muon.app.result.model import MuonResultsModel
from aiidalab_qe_muon.app.workchain import workchain_and_builder

from aiidalab_qe_muon.app.workchain import workchain_and_builder


class MuonPluginOutline(PluginOutline):
    title = "Muon Spectroscopy (MUON)"


property = {
    "outline": MuonPluginOutline,
    "configuration": {
        "panel": MuonConfigurationSettingPanel,
        "model": MuonConfigurationSettingsModel,
    },
    #"code": {
    #    "panel": MuonResourcesSettingsPanel,
    #    "model": MuonResourceSettingsModel,
    #},
    #"result": {
    #    "panel": MuonResultsPanel,
    #    "model": MuonResultsModel,
    #},
    #"workchain": workchain_and_builder,
}
