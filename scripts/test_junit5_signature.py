import json,unittest
from pathlib import Path
from parse_failure import parse,is_method,surefire
ROOT=Path(__file__).resolve().parents[1]
class JUnitSignatures(unittest.TestCase):
    def test_actual_parameterized_ignite_report(self):
        if not (ROOT/"data/extracted/cb6dc83c3ff4432b9631a5f6.xml").exists():self.skipTest("Real diagnostic fixtures must be supplied separately")
        data=(ROOT/'data/extracted/cb6dc83c3ff4432b9631a5f6.xml').read_bytes()
        result=parse(data,'report.xml','org.apache.ignite.internal.storage.rocksdb.RocksDbMvPartitionStorageTest#testScanOverEmpty')
        self.assertEqual(result['matched_cases'],2);self.assertEqual(len(result['failures']),2)
        self.assertEqual(result['failures'][0]['exception_type'],'org.junit.jupiter.api.extension.ParameterResolutionException')
    def test_reject_prefix_and_ambiguous_overloads_synthetic_fixture(self):
        self.assertFalse(is_method('testExtra(Type)[1]','test'))
        self.assertFalse(is_method('human display name','test'))
        data=b'<testsuite><testcase classname="Example" name="test(A)[1]"/><testcase classname="Example" name="test(B)[1]"/></testsuite>'
        with self.assertRaisesRegex(ValueError,'Ambiguous'):surefire(data,'Example#test')
if __name__=='__main__':unittest.main()
