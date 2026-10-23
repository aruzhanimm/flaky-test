import json, unittest
from pathlib import Path
from representations import clean,mask
ROOT=Path(__file__).resolve().parents[1]

class Masking(unittest.TestCase):
    def test_real_diagnostics_keep_exceptions_remove_target_class(self):
        if not (ROOT/"data/processed/corpus.jsonl").exists():self.skipTest("Research corpus must be supplied separately")
        records=[json.loads(line) for line in (ROOT/'data/processed/corpus.jsonl').read_text(encoding='utf-8').splitlines()]
        metadata={r['container']:r for r in json.loads((ROOT/'data/audit/metadata_inventory.json').read_text())}
        checked=0
        for r in records:
            original=r['original_text']; transformed=mask(original,metadata[r['container']],r['canonical_repository'],r['exception_type'])
            self.assertEqual(transformed,r['masked_text'])
            exception=r['exception_type']
            if exception:self.assertIn(exception,transformed)
            klass=r['configured_test'].split('#')[0]
            if klass in original and klass not in (exception or ''):
                self.assertNotIn(klass,transformed)
            self.assertEqual(transformed,mask(original,metadata[r['container']],r['canonical_repository'],exception));checked+=1
        self.assertGreater(checked,10)
    def test_synthetic_edge_fixture_not_research_data(self):
        meta={'project':'https://github.com/example/sample-core','configured_test':'com.sample.SampleTest#run'}
        text='com.sample.CustomException: /work/sample-core/file.txt\n at com.sample.SampleTest.run(SampleTest.java:12)\n at java.lang.Thread.run(Thread.java:3)'
        transformed=mask(text,meta)
        self.assertIn('com.sample.CustomException',transformed)
        self.assertIn('PROJECT_PATH',transformed)
        self.assertIn('TEST_CLASS.TEST_METHOD',transformed)
        self.assertIn('java.lang.Thread.run',transformed)
        self.assertIn(':12',transformed)
    def test_common_cleanup_is_not_condition_specific(self):
        text='java.lang.AssertionError\r\n\tat edu.illinois.nondex.shuffling.ControlNondeterminism.foo(X.java:1)\r\n\tat org.example.Test.test(X.java:5)'
        value=clean(text)
        self.assertNotIn('nondex',value);self.assertIn('org.example.Test.test',value)
    def test_actual_quickcheck_preserves_shared_junit_framework(self):
        if not (ROOT/"data/processed/corpus.jsonl").exists():self.skipTest("Research corpus must be supplied separately")
        rows=[json.loads(x) for x in (ROOT/'data/processed/corpus.jsonl').read_text(encoding='utf-8').splitlines()]
        r=next(r for r in rows if r['container']=='quickcheckc1c1')
        meta={'project':r['canonical_repository'],'configured_test':r['configured_test']}
        value=mask(r['original_text'],meta,r['canonical_repository'],r['exception_type'])
        self.assertIn('org.junit.Assert.fail',value)
        self.assertIn('org.junit.runners.ParentRunner',value)
        self.assertIn('TEST_CLASS.TEST_METHOD',value)

if __name__=='__main__':unittest.main()
