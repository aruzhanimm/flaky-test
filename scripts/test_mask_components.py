"""Synthetic unit fixtures only; not research observations."""
import unittest
from mask_components import transform
from representations import mask

class Components(unittest.TestCase):
    def setUp(self):
        self.meta={'project':'https://github.com/owner/widget-engine','configured_test':'org.widget.WidgetTest#testLongMethod'}
        self.url=self.meta['project']
        self.text='org.widget.WidgetError\nat org.widget.WidgetTest.testLongMethod(WidgetTest.java:31)\n/tmp/widget-engine/data.txt\nwidget-engine'
    def mode(self,m):return transform(self.text,self.meta,self.url,'org.widget.WidgetError',m)
    def test_identity(self):self.assertEqual(self.mode('original'),self.text)
    def test_full_matches_original_implementation(self):self.assertEqual(self.mode('full'),mask(self.text,self.meta,self.url,'org.widget.WidgetError'))
    def test_test_only(self):
        x=self.mode('T');self.assertIn('TEST_CLASS.TEST_METHOD',x);self.assertIn('widget-engine',x)
    def test_repo_only(self):
        x=self.mode('R');self.assertIn('WidgetTest.testLongMethod',x);self.assertNotIn('widget-engine',x);self.assertNotIn('PROJECT_PATH',x)
    def test_path_only(self):
        x=self.mode('P');self.assertIn('PROJECT_PATH',x);self.assertIn('WidgetTest.testLongMethod',x);self.assertTrue(x.endswith('widget-engine'))
    def test_exception_protected(self):
        for m in ('T','R','P','TR','TP','RP','full'):self.assertIn('org.widget.WidgetError',self.mode(m))

if __name__=='__main__':unittest.main()
