"""Run the evaluator contract tests in their owning environments."""
import argparse
from pathlib import Path
import sys
import unittest

TESTS = Path(__file__).resolve().parents[1] / 'tests'
REVIEW_MODULES = ('test_skill_review', 'test_skill_report_reviews')
LEGACY_VALIDATOR_TESTS = frozenset(
    'test_skill_report_reviews.AttachmentTests.' + name
    for name in (
        'test_frozen_current_profile_rejects_changed_checkout_and_retains_legacy_host_dispatch',
        'test_new_profile_rejects_previous_dependency_environment',
        'test_missing_legacy_runtime_rejects_without_changing_profile',
        'test_wrong_runtime_cannot_validate_legacy_modules',
    )
)


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


def contract_suite(loader):
    # Keep the established discovery rule and the legacy dispatch tests while
    # older validator entry points are still supported during the migration.
    discovered = loader.discover(str(TESTS))
    return unittest.TestSuite(
        case for case in cases(discovered)
        if case.id().partition('.')[0] not in REVIEW_MODULES or case.id() in LEGACY_VALIDATOR_TESTS
    )


def review_suite(loader):
    import private_review_runtime

    private_review_runtime.validate_install()
    sys.path.insert(0, str(TESTS))
    return loader.loadTestsFromNames(REVIEW_MODULES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('owner', choices=('contracts', 'private-review'))
    owner = parser.parse_args().owner
    loader = unittest.TestLoader()
    suite = contract_suite(loader) if owner == 'contracts' else review_suite(loader)
    if not suite.countTestCases():
        raise ValueError('No evaluation tests selected')
    return not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()


if __name__ == '__main__':
    raise SystemExit(main())
