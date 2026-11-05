"""Operator-owned, credential-free gh initialization for one owning runtime."""

VERSION = "1.0.0"
MODE = "aeb-gh-fixture"
MANIFEST_ENV = "AEB_GH_MANIFEST"


def backend_spec():
    from skillevaluator.tier3_environments import EnvironmentBackendSpec
    from skillevaluator.tier3.harbor.runner import DOCKER_AGENT_IMPORT_PATHS
    return EnvironmentBackendSpec(
        import_path="aeb_gh_fixture.backend:TrustedGhEnvironment",
        host_env_vars=frozenset({MANIFEST_ENV}),
        host_path_env_vars=frozenset({MANIFEST_ENV}),
        agent_import_paths=DOCKER_AGENT_IMPORT_PATHS,
        prerequisites="aeb_gh_fixture.manifest:prerequisites",
        install_hint="Install the reviewed aeb-gh-fixture wheel in the candidate owning lock.",
    )
