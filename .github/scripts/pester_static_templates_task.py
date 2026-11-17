"""Frozen BatchSummary fixtures with the successor title admission policy."""
from evaluation_campaign_core import require
from evaluation_tasks import BatchSummary, BooleanContract
from pester_admission import POLICY
from pester_static_templates import TEMPLATE_POLICY, template_execution_profile_bytes, template_runner_bytes
import skill_evidence as evidence


class StaticTemplateBatchSummary(BatchSummary):
    def __init__(self, definition, member):
        require(definition.get('admission_policy') == TEMPLATE_POLICY, 'Unregistered template admission')
        super().__init__(definition, member)

    def source_inputs(self, workspace):
        source = super().source_inputs(workspace)
        for module in ('pester_static_templates', 'pester_static_templates_task'):
            path = '.github/scripts/' + module + '.py'
            source.append({'member': 'task/' + path, 'digest': evidence.digest_bytes((workspace / path).read_bytes())})
        return source

    def controls(self):
        # Retain the original five-control population and the exact mutant
        # expectations. The strong fixture exercises the new title admission.
        controls = BooleanContract.controls(self)
        controls['good']['file'] = (
            '.github/evals/pester-return-contract/transfer/controls/static-template.Tests.ps1'
        )
        return controls

    def expected_members(self, case, arm):
        # Dispatch the old member builder against its own unchanged policy.
        base = BatchSummary(dict(self.definition, admission_policy=POLICY), self.member)
        members = base.expected_members(case, arm)
        members['tests/Runner.ps1'] = template_runner_bytes()
        members['environment/input/EXECUTION-PROFILE.md'] = template_execution_profile_bytes()
        return members
