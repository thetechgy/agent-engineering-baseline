from skillevaluator.tier3_environments import EnvironmentBackendSpec
SPEC=EnvironmentBackendSpec(import_path='harbor_gate:TrustedEnvironment',agent_import_paths={'codex':'harbor_gate:ProbeAgent'},supports_docker_compose=True)
