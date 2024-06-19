from aiidalab_qe.common.widgets import QEAppComputationalResourcesWidget


pp_code = QEAppComputationalResourcesWidget(
    description="pp.x",
    default_calc_job_plugin="quantumespresso.pp",
)