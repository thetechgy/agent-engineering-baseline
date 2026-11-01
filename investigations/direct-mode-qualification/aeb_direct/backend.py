from skillevaluator.tier3_environments import EnvironmentBackendSpec
SPEC=EnvironmentBackendSpec(import_path='aeb_direct.environment:Environment',agent_import_paths={'codex':'aeb_direct.agent:Agent'},environment_kwargs=frozenset({'profile'}),supports_docker_compose=True)
