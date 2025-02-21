"""Implementation of the VibroWorkchain for managing the aiida-vibroscopy workchains."""

from aiida.common import AttributeDict
from aiida.engine import WorkChain
from aiida import orm
from aiida.plugins import WorkflowFactory
from aiida.engine import if_

from aiida_workgraph import WorkGraph
from aiida_workgraph.engine.workgraph import WorkGraphEngine
from aiidalab_qe_muon.undi_interface.workflows.workgraphs import (
    MultiSites,
)


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
            "structure", valid_type=orm.StructureData
        )  # Maybe not needed as input... just in the protocols. but in this way it is not easy to automate it in the app, after the relaxation. So let's keep it for now.
        spec.input(
            "undi_code", 
            valid_type=orm.Code, 
            required=False,
            help="The code to run the UNDI calculations.",
        )
        spec.input(
            "undi_metadata",
            valid_type= dict, 
            non_db=True,
            required=False,
            help=" Preferred metadata and scheduler options for undi",
        )
        spec.input(
            "undi_fields",
            valid_type= orm.List,
            required=False,
            help="The list of magnetic fields to compute the polarization.",
        )
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
        spec.input(
            "implant_muon",
            valid_type=bool,
            default=True,
            non_db=True,
            help="Whether to implant the muon or not.",
        )
        spec.input(
            "compute_polarization",
            valid_type=bool,
            default=True,
            non_db=True,
            help="Whether to compute the polarization or not.",
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
                cls.output_implant_results,
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
                "help": "Outputs of the `FindMuonWorkChain`.",
            },
        )
        
        
        spec.output('polarization', required=False, help="The polarization results.")
        
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
        undi_code=None,
        undi_metadata=None,
        undi_fields=None,
        protocol=None,
        enforce_defaults: bool = True,
        compute_findmuon: bool = True,
        compute_polarization_undi: bool = True,
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
            enforce_defaults = enforce_defaults,
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
        
        builder.implant_muon = compute_findmuon
        builder.compute_polarization = compute_polarization_undi
        
        if undi_code:
            builder.undi_code = undi_code
            if undi_metadata:
                builder.undi_metadata = undi_metadata
                
        if undi_fields and compute_polarization_undi:
            builder.undi_fields = orm.List(undi_fields)

        return builder

    def setup(self):
        # key, class, outputs namespace.
        self.ctx.implant_muon = self.inputs.implant_muon
        self.ctx.compute_polarization = self.inputs.compute_polarization
        self.ctx.workchain_class = FindMuonWorkChain

    def need_implant(self):
        """Return True if the muon is not implanted,
        i.e. we need to run the full WorkChain."""
        # is False if only undi run. PP
        # a smart check is to see if the structure contain as last element the muon, and if it contains
        # the extra: muon_implanted == True, fixed in the settings (so we can trigger only the undi run).
        # in the settings we need also a check that H is the only H....
        return self.ctx.implant_muon

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
        
    def output_implant_results(self):
        """Output the results of the FindMuonWorkChain."""
        workchain = self.ctx.get("findmuon", None)

        if workchain:
            if not workchain.is_finished_ok:
                self.report(f"the child WorkChain with <PK={workchain.pk}> failed")
                return self.exit_codes.ERROR_WORKCHAIN_FAILED

            if self.ctx.implant_muon:
                self.out_many(
                    self.exposed_outputs(
                        workchain,
                        self.ctx.workchain_class,
                        namespace="findmuon",
                    )
                )

    def need_polarization(self):
        return self.ctx.compute_polarization

    def prepare_polarization(self):
        if self.ctx.implant_muon:
            self.ctx.structure_group = self.get_structures_group_from_findmuon(self.ctx.findmuon)
        else:  # we want only polarization, so use the input structure.
            self.ctx.structure_group = {'0':self.inputs.structure}

    def compute_polarization(self):
        # here we will submit the workgraph for the polarization estimation. Via Undi and KT.
        # need to parse all the output structures, and loop on them.

        metadata = self.inputs.get("undi_metadata", None)
        workgraph = MultiSites(
            structure_group=self.ctx.structure_group,
            code = getattr(self.inputs, "undi_code", None),
            B_mods = self.inputs.get("undi_fields", None),
            metadata = metadata,
            )
        inputs = {
            "wg": workgraph.to_dict(),
            "metadata": {"call_link_label": "MultiSiteUndiPolarizationAndKT"},
            
        }
        process = self.submit(WorkGraphEngine, **inputs)
        self.report(
            f"submitting `Workgraph` for polarization calculation: <PK={process.pk}>"
        )
        self.to_context(workgraph=process)

    def results(self):
        """Inspect pol sub-processes."""
        polarization = self.ctx.get("workgraph", None)

        # should we output the wgraph results here?
        # Yes, we should collect them in order to easily recover the site index.
        if polarization:
            if not polarization.is_finished_ok:
                self.report(f"the child WorkGraph with <PK={polarization.pk}> failed")
                return self.exit_codes.ERROR_POLARIZATION_FAILED
            else:
                self.out(
                        "polarization",
                        polarization.outputs.execution_count,
                    )
                self.report(f"Undi calculation was successful.")
                

    @staticmethod
    def get_structures_group_from_findmuon(findmuon: FindMuonWorkChain):
        """Return the structures group from the FindMuonWorkChain."""
        structure_group = {}
        for idx, uuid in findmuon.outputs.all_index_uuid.get_dict().items():
            if idx in findmuon.outputs.unique_sites.get_dict().keys():
                relaxwc = orm.load_node(uuid)
                structure_group[idx] = relaxwc.outputs.output_structure
                relaxwc.outputs.output_structure.base.extras.set("muon_index", str(idx))
        return structure_group
