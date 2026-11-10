"""Credential-free deadline controls; called only after CampaignCodex's probe guard."""
import asyncio
import os


async def run(adapter, instruction, environment, context, launch):
    scenario = adapter.deadline_fixture
    os.environ['AEB_PILOT_SCENARIO'] = 'native-empty' if scenario == 'empty' else 'native-deadline'
    if scenario == 'secondary':
        environment._deadline_copy_fault = True  # A real failed stopped-container copy.
    handle = asyncio.get_running_loop().call_later(45, asyncio.current_task().cancel) if scenario == 'cancelled' else None
    try:
        return await launch(instruction, environment, context)
    finally:
        if handle: handle.cancel()


def commands(output, payload):
    return [f"printf %s {payload} | base64 -d > {output}; "
            "printf 'native-deadline-evidence\\n'; "
            "printf 'native-deadline-stderr OPENAI_API_KEY=fixture-redaction-sentinel\\n' >> /logs/agent/codex-stderr.txt; "
            "(sleep 100; touch /workspace/output/deadline-descendant-survived) &"]
