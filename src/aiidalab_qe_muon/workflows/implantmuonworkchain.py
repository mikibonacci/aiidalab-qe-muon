"""Implementation of the VibroWorkchain for managing the aiida-vibroscopy workchains."""

from aiida.common import AttributeDict
from aiida.engine import WorkChain
from aiida.orm import StructureData
from aiida.plugins import WorkflowFactory
from aiida.engine import if_


MusconvWorkChain = WorkflowFactory("impuritysupercellconv")
FindMuonWorkChain = WorkflowFactory("muon.find_muon")
PwRelaxWorkChain = WorkflowFactory("quantumespresso.pw.relax")
original_PwRelaxWorkChain = WorkflowFactory("quantumespresso.pw.relax")


def FindMuonWorkChain_override_validator(inputs, ctx=None):
    """validate inputs for musconv.relax; actually, it is
    just a way to avoid defining it if we do not want it.
    otherwise the default check is done and it will excepts.
    """
    return None


FindMuonWorkChain.spec().inputs.validator = FindMuonWorkChain_override_validator


def implant_input_validator(inputs, ctx=None):
    return None


class ImplantMuonWorkChain(WorkChain):
    "WorkChain to compute muon stopping sites in a crystal."

    label = "muon"

    @classmethod
    def define(cls, spec):
        """Specify inputs and outputs."""
        super().define(spec)

        spec.input(
            "structure", valid_type=StructureData
        )  # Maybe not needed as input... just in the protocols. but in this way it is not easy to automate it in the app, after the relaxation. So let's keep it for now.

        spec.expose_inputs(
            FindMuonWorkChain,
            namespace="findmuon",
            exclude=(
                "clean_workdir",
                "structure",
            ),  # AAA check this... maybe not needed.
            namespace_options={
                "required": False,
                "populate_defaults": False,
                "help": (
                    "Inputs for the `FindMuonWorkChain` that will be"
                    "used to calculate the muon stopping sites."
                ),
            },
            # exclude=('symmetry')
        )

        # I think the following is not needed, as we may want to just provide the structure and the fields, max_hdims
        # and then initialise the workgraph with the structure and the fields and max_hdims.
        # TOBE understood how to provide a given code (probably the computer... but I need the code)
        # spec.input_namespace('undi_workgraph', dynamic=True)

        ###
        spec.outline(
            cls.setup,
            if_(cls.need_implant)(
                cls.prepare_implant,
                cls.implant_muon,
            ),
            if_(cls.need_polarization)(
                cls.prepare_polarization,
                cls.compute_polarization,
            ),
            cls.results,
        )
        ###
        spec.expose_outputs(
            FindMuonWorkChain,
            namespace="findmuon",
            namespace_options={
                "required": False,
                "help": "Outputs of the `PhononWorkChain`.",
            },
        )
        ###
        spec.exit_code(400, "ERROR_WORKCHAIN_FAILED", message="The workchain failed.")
        spec.exit_code(
            401,
            "ERROR_POLARIZATION_FAILED",
            message="The polarization calculation failed.",
        )
        ###
        spec.inputs.validator = implant_input_validator

    @classmethod
    def get_builder_from_protocol(
        cls,
        pw_muons_code,
        structure,
        pseudo_family: str = "SSSP/1.2/PBE/efficiency",
        pp_code=None,
        protocol=None,
        overrides: dict = {},
        trigger=None,
        relax_musconv: bool = False,  # in the end you relax in the first step of the QeAppWorkchain.
        magmom: list = None,
        options=None,
        sc_matrix: list = None,
        mu_spacing: float = 1.0,
        kpoints_distance: float = 0.301,
        charge_supercell: bool = True,
        pp_metadata: dict = None,
        **kwargs,
    ):
        """Return a builder prepopulated with inputs selected according to the chosen protocol.

        :param pw_muons_code: the ``Code`` instance configured for the ``quantumespresso.pw`` plugin.
        :param structure: the ``StructureData`` instance to use.
        :param protocol: protocol to use, if not specified, the default will be used.
        :param overrides: optional dictionary of inputs to override the defaults of the protocol.
        :param options: A dictionary of options that will be recursively set for the ``metadata.options`` input of all
            the ``CalcJobs`` that are nested in this work chain.
        :param kwargs: additional keyword arguments that will be passed to the ``get_builder_from_protocol`` of all the
            sub processes that are called by this workchain.
        :return: a process builder instance with all inputs defined ready for launch.
        """

        if magmom and not pp_code:
            raise ValueError(
                "pp code not provided but required, as the system is magnetic."
            )

        builder = cls.get_builder()

        builder_findmuon = FindMuonWorkChain.get_builder_from_protocol(
            pw_code=pw_muons_code,
            pp_code=pp_code,
            structure=structure,
            protocol=protocol,
            overrides=overrides,
            relax_musconv=relax_musconv,  # relaxation of unit cell already done if needed.
            magmom=magmom,
            sc_matrix=sc_matrix,
            mu_spacing=mu_spacing,
            kpoints_distance=kpoints_distance,
            charge_supercell=charge_supercell,
            pseudo_family=pseudo_family,
            **kwargs,
        )
        # builder.findmuon = builder_findmuon
        for k, v in builder_findmuon.items():
            if k != "structure":
                setattr(builder.findmuon, k, v)

        # If I don't pop here, when we set this builder as QeAppWorkChain builder attribute,
        # it will be validated and it will fail because it tries anyway to detect IMPURITY inputs...
        if sc_matrix:
            builder.findmuon.pop("impuritysupercellconv")
        #    builder.findmuon.impuritysupercellconv.pwscf.pw.parameters = Dict({})

        if pp_metadata:
            builder.findmuon.pp_metadata = pp_metadata

        builder.structure = structure

        return builder

    def setup(self):
        # key, class, outputs namespace.
        self.ctx.muon_not_implanted = True
        self.ctx.compute_polarization = False
        self.ctx.workchain_class = FindMuonWorkChain

    def need_implant(self):
        """Return True if the muon is not implanted,
        i.e. we need to run the full WorkChain."""
        # is False if only undi run. PP
        # a smart check is to see if the structure contain as last element the muon, and if it contains
        # the extra: muon_implanted == True, fixed in the settings (so we can trigger only the undi run).
        # in the settings we need also a check that H is the only H....
        return self.ctx.muon_not_implanted

    def prepare_implant(self):
        return

    def implant_muon(self):
        """Run a WorkChain for to find muon rest site candidates."""
        # maybe we can unify this, thanks to a wise setup.
        inputs = AttributeDict(
            self.exposed_inputs(self.ctx.workchain_class, namespace="findmuon")
        )
        inputs.metadata.call_link_label = "findmuon"

        inputs.structure = self.inputs.structure

        future = self.submit(self.ctx.workchain_class, **inputs)
        self.report(f"submitting `WorkChain` <PK={future.pk}>")
        self.to_context(**{"findmuon": future})

    def need_polarization(self):
        return self.ctx.compute_polarization

    def prepare_polarization(self):
        if self.ctx.muon_not_implanted:
            pass
        else:  # we want only polarization, so use the input structure.
            self.ctx.structure_group = [self.inputs.structure]

    def compute_polarization(self):
        # this is a placeholder for the future.
        # here we will submit the workgraph for the polarization estimation. Via Undi and KT.
        # need to parse all the output structures, and loop on them.
        from aiida_workgraph import WorkGraph
        from aiida_workgraph.engine.workgraph import WorkGraphEngine
        from aiidalab_qe_muon.undi_interface.workflows.workgraphs import (
            UndiAndKuboToyabe,
        )

        # which code to use?
        workgraph = WorkGraph(name="polarization")
        for i,structure in enumerate(self.ctx.structure_group):
            workgraph.add_task(
                UndiAndKuboToyabe,
                structure=structure,
                Bmods=[0, 2e-3, 4e-3],  # for now, hardcoded.
                max_hdims=[10**p for p in range(1, 4, 2)],  # for now, hardcoded.
                convergence_check=i==0,  # maybe the convergence can be done for only one site...
                algorithm='fast',
                sample_size_average=10,
                name=f"polarization_structure_{structure.pk}",
            )

        inputs = {
            "wg": workgraph.to_dict(),
            "metadata": {"call_link_label": "UndiPolarizationAndKT"},
        }
        process = self.submit(WorkGraphEngine, **inputs)
        self.report(
            f"submitting `Workgraph` for polarization calculation: <PK={process.pk}>"
        )
        self.to_context(workgraph=process)

    def results(self):
        """Inspect all sub-processes."""
        workchain = self.ctx.get("findmuon", None)
        polarization = self.ctx.get("workgraph", None)

        if workchain:
            if not workchain.is_finished_ok:
                self.report(f"the child WorkChain with <PK={workchain.pk}> failed")
                return self.exit_codes.ERROR_WORKCHAIN_FAILED

            if self.ctx.muon_not_implanted:
                self.out_many(
                    self.exposed_outputs(
                        self.ctx["findmuon"],
                        self.ctx.workchain_class,
                        namespace="findmuon",
                    )
                )

        # should we output the wgraph results here?
        # Yes, we should collect them in order to easily recover the site index.
        if polarization:
            if not polarization.is_finished_ok:
                self.report(f"the child WorkGraph with <PK={polarization.pk}> failed")
                return self.exit_codes.ERROR_POLARIZATION_FAILED
            #self.out_many(polarization.outputs)
