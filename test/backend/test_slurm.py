import unittest
from saliweb.backend.cluster import _SLURMTasks


class SLURMTest(unittest.TestCase):
    """Check SLURM utility classes"""

    def test_slurm_tasks_none(self):
        """Check the _SLURMTasks class with no subtasks"""
        for s in ('', '-o foo -p bar'):
            t = _SLURMTasks(s)
            self.assertTrue(not t)

    def test_slurm_tasks_invalid(self):
        """Check the _SLURMTasks class with invalid input"""
        for s in ('-a ', '-a x:y', '-a FOO'):
            self.assertRaises(ValueError, _SLURMTasks, s)

    def test_slurm_tasks_valid(self):
        """Check the _SLURMTasks class with valid input"""
        t = _SLURMTasks('-a 27')
        self.assertEqual((t.first, t.last, t.step), (27, 27, 1))
        t = _SLURMTasks('-a 4-10')
        self.assertEqual((t.first, t.last, t.step), (4, 10, 1))
        t = _SLURMTasks('-a 4-10:2')
        self.assertEqual((t.first, t.last, t.step), (4, 10, 2))

    def test_slurm_tasks_run_get(self):
        """Check the _SLURMTasks.get_run_id() method"""
        t = _SLURMTasks('-a 4-10:2')
        self.assertEqual(t.get_run_id(['foo_4', 'foo_6', 'foo_8', 'foo_10']),
                         'foo_4-10:2')
        t = _SLURMTasks('-a 1-3')
        self.assertEqual(t.get_run_id(['foo_1', 'foo_2', 'foo_3']),
                         'foo_1-3:1')
        t = _SLURMTasks('-a 4-10:2')
        self.assertRaises(ValueError, t.get_run_id,
                          ['foo_1', 'foo_2', 'foo_3'])


if __name__ == '__main__':
    unittest.main()
