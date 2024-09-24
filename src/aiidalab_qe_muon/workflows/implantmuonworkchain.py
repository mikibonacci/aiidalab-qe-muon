"""Implementation of the VibroWorkchain for managing the aiida-vibroscopy workchains."""
from aiida.common import AttributeDict
from aiida.engine import ToContext, WorkChain, calcfunction
from aiida.orm import AbstractCode, Int, Float, Dict, Code, StructureData, load_code
from aiida.plugins import WorkflowFactory
from aiida_quantumespresso.utils.mapping import prepare_process_inputs
from aiida_quantumespresso.common.types import ElectronicType, SpinType
from aiida.engine import WorkChain, calcfunction, if_


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
            exclude=("clean_workdir"),  # AAA check this... maybe not needed.
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

        ###
        spec.outline(
            cls.setup,
            cls.implant_muon,
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
        from aiida_quantumespresso.workflows.protocols.utils import recursive_merge

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
            setattr(builder.findmuon, k, v)

        # If I don't pop here, when we set this builder as QeAppWorkChain builder attribute,
        # it will be validated and it will fail because it tries anyway to detect IMPURITY inputs...
        if sc_matrix:
            builder.findmuon.pop('impuritysupercellconv')
        #    builder.findmuon.impuritysupercellconv.pwscf.pw.parameters = Dict({})
            
        if pp_metadata:
            builder.findmuon.pp_metadata = pp_metadata

        builder.structure = structure

        return builder

    def setup(self):
        # key, class, outputs namespace.
        self.ctx.workchain = FindMuonWorkChain

    def implant_muon(self):
        """Run a WorkChain for vibrational properties."""
        # maybe we can unify this, thanks to a wise setup.
        inputs = AttributeDict(
            self.exposed_inputs(self.ctx.workchain, namespace=self.ctx.key)
        )
        inputs.metadata.call_link_label = self.ctx.key

        future = self.submit(self.ctx.workchain, **inputs)
        self.report(f"submitting `WorkChain` <PK={future.pk}>")
        self.to_context(**{self.ctx.key: future})

    def results(self):
        """Inspect all sub-processes."""
        workchain = self.ctx[self.ctx.key]

        if not workchain.is_finished_ok:
            self.report(f"the child WorkChain with <PK={workchain.pk}> failed")
            return self.exit_codes.ERROR_WORKCHAIN_FAILED

        self.out_many(
            self.exposed_outputs(
                self.ctx[self.ctx.key], self.ctx.workchain, namespace=self.ctx.key
            )
        )
