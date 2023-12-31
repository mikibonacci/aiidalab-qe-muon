from aiidalab_qe_muon.app.settings import Setting
from aiidalab_qe_muon.app.structure import ImportMagnetism
from aiidalab_qe_muon.app.workchain import workchain_and_builder
from aiidalab_qe_muon.app.result import Result
from aiidalab_qe_muon.app.codes import pp_code

from aiidalab_qe.common.panel import OutlinePanel


class Outline(OutlinePanel):
    title = "Muon spectroscopy"

property ={
"outline": Outline,
"importer":ImportMagnetism,
"setting": Setting,
"workchain": workchain_and_builder,
"result": Result,
"code": {"pp_code": pp_code},
}