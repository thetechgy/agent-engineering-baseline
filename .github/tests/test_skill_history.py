"""History admission, comparison equivalence, expiry, and renderer regressions."""
import copy
import json
from datetime import datetime, timedelta, timezone
import unittest

import test_skill_analysis as fixtures
import skill_analysis as analysis
import skill_history as history
import skill_report as report
from test_skill_pages import prov

AT='2026-10-27T12:00:00Z'


class HistoryTests(unittest.TestCase):
    def item(self, n=1, at=AT, slot='standard--alpha', record=None):
        record=record or fixtures.synthetic(run='run-'+str(n))
        return history.observation(record,slot,prov('a'*40,n,kind='benchmark' if slot!='quality' else 'validate'),at,{'started_at':at,'completed_at':at})

    def test_zero_one_multiple_render_and_no_external_assets(self):
        value=history.empty(AT)
        self.assertIn('No historical observations',report.historical_view(value))
        history.add(value,self.item())
        html=report.historical_view(history.validate(json.loads(json.dumps(value, sort_keys=True))))
        self.assertIn('trend is not yet established',html)
        self.assertIn('<svg role="img"',html)
        self.assertIn('<table',html)
        self.assertNotIn('<script',html)
        self.assertNotIn('cdn.',html)

    def test_comparison_matches_analyzer_and_decrease_is_descriptive(self):
        left=self.item(at='2026-10-26T12:00:00Z')
        r=fixtures.synthetic(run='run-2'); r['metrics'][0]['value']=0.1
        right=self.item(2,record=r)
        status, reasons, delta=history.compare(left,right)
        self.assertEqual(status,'directly_comparable')
        self.assertEqual(delta['Skill Lift']['display'],'-0.1000')
        self.assertEqual((status,reasons),analysis.classify_facts(history.facts(left),history.facts(right)))
        value=history.empty(AT); value['observations']=[right,left]
        html=report.historical_view(value)
        self.assertIn('ordinary variation remains possible',html)
        self.assertLess(html.index('Run 1 /'),html.index('Run 2 /'))

    def test_unknown_policy_runtime_and_dates_never_gain_deltas(self):
        left=self.item(at='2026-10-26T12:00:00Z')
        for mode in ('unknown','runtime','undated','diagnostic','tied'):
            right=self.item(2)
            if mode=='unknown': right['record']['policy']['fields']['model']=None
            if mode=='runtime': right['record']['policy']['fields']['codex']='different'
            if mode=='undated': right['execution']['completed_at']=None
            if mode=='diagnostic': right['class']='diagnostic'
            if mode=='tied': right['execution']=left['execution']
            self.assertEqual(history.compare(left,right)[2],{},mode)

    def test_duplicate_and_conflicting_measurements(self):
        value=history.empty(AT); item=self.item()
        history.add(value,item); replay=copy.deepcopy(item); replay['provenance']['attempt']=2
        history.add(value,replay); self.assertEqual(len(value['observations']),1)
        replay['record_digest']='sha256:'+'f'*64
        with self.assertRaises(ValueError): history.add(value,replay)

    def test_retention_boundaries_independent_classes_and_protection(self):
        value=history.empty(AT)
        now=history.timestamp(AT)
        for n in range(35):
            at=(now-timedelta(days=n)).strftime('%Y-%m-%dT%H:%M:%SZ')
            history.add(value,self.item(n+1,at))
        expired=self.item(99,'2026-01-01T12:00:00Z'); history.add(value,expired)
        diagnostic=self.item(100,slot='confirmation--alpha'); history.add(value,diagnostic)
        history.retain(value,AT,{(99,1)})
        self.assertEqual(len(value['observations']),32)
        self.assertIn(expired['id'],value['protected'])
        first=copy.deepcopy(value); history.retain(value,AT,{(99,1)}); self.assertEqual(value,first)
        exact=self.item(200,(now-timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%SZ'))
        v=history.empty(AT); v['observations']=[exact]
        history.retain(v,AT); self.assertEqual(len(v['observations']),1)
        history.retain(v,'2026-10-27T12:00:01Z'); self.assertFalse(v['observations'])

    def test_missing_metrics_incomplete_and_schema_v2(self):
        left=self.item(at='2026-10-26T12:00:00Z'); right=self.item(2)
        right['numeric_complete']=False
        self.assertEqual(history.compare(left,right)[0],'exploratory')
        right['record']['schema_version']=2
        self.assertEqual(history.compare(left,right)[0],'custom_comparison_deferred')

    def test_retained_oracle_schema_v2_is_operational_only(self):
        from pathlib import Path
        import skill_evidence as evidence
        record=evidence.read_json(Path(__file__).parent / 'fixtures/skill_pages/oracle-public.json')
        value=history.empty(AT)
        item=history.observation(record, 'oracle--powershell-pester-6', prov('a'*40), AT)
        history.add(value,item)
        history.validate(json.loads(json.dumps(value,sort_keys=True)))
        self.assertEqual(item['class'],'diagnostic')
        self.assertFalse(item['numeric_complete'])
        self.assertNotIn('<svg',report.historical_view(value))

    def test_tampered_identity_and_nonfinite_metrics_rejected(self):
        for key in ('id','metric'):
            value=history.empty(AT); item=self.item(); value['observations']=[item]
            if key=='id': item['id']='sha256:'+'f'*64
            else: item['record']['metrics'][0]['value']=float('nan')
            with self.assertRaises(ValueError): history.validate(value)
