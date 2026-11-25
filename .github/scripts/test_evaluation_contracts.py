"""Run the evaluator contract tests in their owning environments."""
import argparse
from pathlib import Path
import sys
import unittest

TESTS = Path(__file__).resolve().parents[1] / 'tests'
REVIEW_MODULES = ('test_skill_review', 'test_skill_report_reviews', 'test_historical_review_replay')
PRESENTATION_MODULES = (
    'test_skill_analysis', 'test_skill_report', 'test_skill_pages', 'test_public_reports',
    'test_evaluator_scoring_compatibility',
)


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


def contract_suite(loader):
    # Keep the established discovery rule for suites outside the released owners.
    discovered = loader.discover(str(TESTS))
    return unittest.TestSuite(
        case for case in cases(discovered)
        if case.id().partition('.')[0] not in (*REVIEW_MODULES, *PRESENTATION_MODULES)
    )


def review_suite(loader):
    import private_review_runtime

    private_review_runtime.validate_install()
    sys.path.insert(0, str(TESTS))
    return loader.loadTestsFromNames(REVIEW_MODULES)


def presentation_suite(loader):
    import static_evaluator

    static_evaluator.validate_install()
    sys.path.insert(0, str(TESTS))
    return loader.loadTestsFromNames(PRESENTATION_MODULES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    suites = {'contracts': contract_suite, 'private-review': review_suite, 'presentation': presentation_suite}
    parser.add_argument('owner', choices=suites)
    owner = parser.parse_args().owner
    loader = unittest.TestLoader()
    suite = suites[owner](loader)
    if not suite.countTestCases():
        raise ValueError('No evaluation tests selected')
    return not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()


if __name__ == '__main__':
    raise SystemExit(main())
