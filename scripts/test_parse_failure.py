"""Regression checks using downloaded real fixtures, plus exclusion invariants."""
import json, unittest
from pathlib import Path
from parse_failure import parse
ROOT=Path(__file__).resolve().parents[1]
MANIFEST_PATH=ROOT/'data/log_sample/manifest.json'
MANIFEST=json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else []

class RealFailureParsing(unittest.TestCase):
    def fixture(self,container):
        if not MANIFEST:self.skipTest("Real diagnostic fixtures must be supplied separately")
        item=next(r for r in MANIFEST if r['container']==container and (r['path'].endswith('.xml') or '/test-runs/results/' in r['path']))
        return item,(ROOT/item['local_path']).read_bytes()
    def test_passing_target_is_not_failure(self):
        for container in ('APEXCORE-403','BOOKKEEPER-709'):
            item,data=self.fixture(container); result=parse(data,item['path'],item['configured_test'])
            self.assertEqual(result['passed_cases'],1); self.assertEqual(result['failures'],[])
    def test_exact_target_ignores_other_testcases(self):
        item,data=self.fixture('wikidatatoolkitwdtkutil10f9711')
        result=parse(data,item['path'],item['configured_test'])
        self.assertEqual(result['matched_cases'],1); self.assertEqual(len(result['failures']),1)
        self.assertNotIn('<properties',result['failures'][0]['text'])
        wrong=parse(data,item['path'],item['configured_test']+'Wrong')
        self.assertEqual(wrong['matched_cases'],0)
    def test_assertion_and_infrastructure_distinguished(self):
        item,data=self.fixture('ormlitecore59309e64'); r=parse(data,item['path'],item['configured_test'])['failures'][0]
        self.assertEqual(r['exception_type'],'java.lang.AssertionError'); self.assertEqual(r['review_flags'],[])
        item,data=self.fixture('wildflynaming3a83b7b1'); r=parse(data,item['path'],item['configured_test'])['failures'][0]
        self.assertIn('class_initialization',r['review_flags'])
    def test_nio_repetitions_do_not_invent_exception(self):
        item,data=self.fixture('quickcheck4851'); r=parse(data,item['path'],item['configured_test'])
        self.assertEqual(r['matched_cases'],2); self.assertEqual(len(r['failures']),1)
        self.assertIsNone(r['failures'][0]['exception_type']); self.assertTrue(r['failures'][0]['testcase_name'].endswith(':1'))
    def test_reject_xml_entities(self):
        with self.assertRaises(ValueError): parse(b'<!DOCTYPE test [<!ENTITY a "x">]><testsuite/>','x.xml','a.B#test')
    def test_text_reports_three_real_naming_formats(self):
        if not (ROOT/"data/first_failures").exists():self.skipTest("Real diagnostic fixtures must be supplied separately")
        import hashlib
        for container in ('COLLECTIONS-812','CURATOR-671','OOZIE-3683'):
            key=hashlib.sha256(container.encode()).hexdigest()[:24]
            record=json.loads((ROOT/'data/first_failures'/(key+'.json')).read_text())
            source=record.get('diagnostic_member') or record['attempts'][-1]['member']
            data=(ROOT/source['local_path']).read_bytes()
            result=parse(data,source['path'],record['metadata']['configured_test'])
            self.assertEqual(len(result['failures']),1)
            self.assertIn('AssertionFailedError',result['failures'][0]['text'])
            self.assertNotIn('Tests run:',result['failures'][0]['text'])
            self.assertEqual(parse(data,source['path'],record['metadata']['configured_test']+'Wrong')['failures'],[])

if __name__=='__main__': unittest.main()
