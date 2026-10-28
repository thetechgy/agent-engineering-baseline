from skillevaluator.tier3_environments import EnvironmentBackendSpec
SPEC=EnvironmentBackendSpec(import_path='aeb_native_qualification.environment:SecureNativeEnvironment',environment_kwargs=frozenset({'profile'}),required_environment_kwargs=('profile',),agent_import_paths={'codex':'aeb_native_qualification.agent:NativeCodex'},supports_docker_compose=True)
