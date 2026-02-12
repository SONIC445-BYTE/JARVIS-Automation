"""
Test Rollback Manager.
"""
import unittest
import shutil
import os
from AgentCore.rollback.rollback_manager import RollbackManager

class TestRollbackManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_snapshots"
        self.mgr = RollbackManager(self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_snapshot_lifecycle(self):
        name = "snap_v1"
        path = self.mgr.create_snapshot(name)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(self.mgr.last_known_good, name)
        
        success = self.mgr.restore_snapshot(name)
        self.assertTrue(success)
        
        success = self.mgr.restore_snapshot("non_existent")
        self.assertFalse(success)

if __name__ == "__main__":
    unittest.main()
