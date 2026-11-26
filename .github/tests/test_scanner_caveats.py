"""Exercise the pinned scanner contract against retained SkillSpector data."""
import os
import unittest


@unittest.skipUnless(os.environ.get('SKILL_EVALUATION_KIND') == 'scanner-contracts', 'Requires scanner contract setup')
class ScannerCaveatTests(unittest.TestCase):
    def test_retained_adapter_compatibility_contracts(self):
        from qualify_scanner_caveats import contracts

        result = contracts()
        self.assertEqual(result['owner'], 'skillevaluator-1.2.1-scanner-contracts')
        self.assertEqual(result['negative_mutations'], 43)
