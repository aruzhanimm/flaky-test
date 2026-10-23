"""Regression checks for checkpoint serialization; no research observations."""
import json,unittest
import numpy as np
from run_extension_v4 import python_scalar
class Checkpoints(unittest.TestCase):
    def test_numpy_values(self):
        value={'count':np.int64(56),'score':np.float64(.5),'verified':np.bool_(True)}
        self.assertEqual(json.loads(json.dumps(value,default=python_scalar)),{'count':56,'score':.5,'verified':True})
    def test_unsupported_value_fails(self):
        with self.assertRaises(TypeError):json.dumps({'invalid':object()},default=python_scalar)
if __name__=='__main__':unittest.main()
