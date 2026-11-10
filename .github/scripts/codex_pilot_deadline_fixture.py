"""Credential-free controls only; never selected by production agent configuration."""
import os
from evaluation_codex import CampaignCodex


class DeadlineCodex(CampaignCodex):
    def __init__(self, *args, deadline_fixture, **kwargs):
        assert os.environ.get('AEB_PILOT_PROBE') == '1' and not kwargs.get('live')
        assert deadline_fixture in ('emitted', 'empty', 'secondary', 'cancelled')
        self.deadline_fixture = deadline_fixture
        super().__init__(*args, **kwargs)

    async def run(self, instruction, environment, context):
        os.environ['AEB_PILOT_SCENARIO'] = 'native-empty' if self.deadline_fixture == 'empty' else 'native-deadline'
        if self.deadline_fixture == 'secondary':
            # A real failed stopped-container copy, not an exception substituted for execution.
            environment._deadline_copy_fault = True
        return await super().run(instruction, environment, context)

    def fixture_commands(self, payload):
        return [f"printf %s {payload} | base64 -d > {self.output}; "
                "printf 'native-deadline-evidence\\n'; "
                "printf 'native-deadline-stderr OPENAI_API_KEY=fixture-redaction-sentinel\\n' >> /logs/agent/codex-stderr.txt; "
                "(sleep 100; touch /workspace/output/deadline-descendant-survived) &"]
