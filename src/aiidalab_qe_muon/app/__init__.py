from aiidalab_qe_muon.app.settings import Setting
from aiidalab_qe_muon.app.structure import ImportMagnetism
from aiidalab_qe_muon.app.workchain import workchain_and_builder
from aiidalab_qe_muon.app.result import Result

from aiidalab_qe.common.panel import OutlinePanel

from aiidalab_qe.common.widgets import (
    QEAppComputationalResourcesWidget,
    PwCodeResourceSetupWidget,
)

MuonWorkChainPwCode = PwCodeResourceSetupWidget(
    description="pw.x for muons",  # code for the PhononWorkChain workflow",
    default_calc_job_plugin="quantumespresso.pw",
)

PpCalculationCode = QEAppComputationalResourcesWidget(
    description="pp.x",
    default_calc_job_plugin="quantumespresso.pp",
)

class Outline(OutlinePanel):
    title = "Muon spectroscopy"

property ={
"outline": Outline,
"importer":ImportMagnetism,
"setting": Setting,
"workchain": workchain_and_builder,
"result": Result,
"code": {
    "pw_muons": MuonWorkChainPwCode,
    "pp_code": PpCalculationCode,
    },
}