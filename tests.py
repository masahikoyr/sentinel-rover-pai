"""Contract tests for safety invariants and saved physical execution evidence."""
from pathlib import Path
import csv,json,math,unittest
import numpy as np
from sensors import decision
from planner import astar,blocked,safety_filter

ROOT=Path(__file__).resolve().parent

class SafetyContracts(unittest.TestCase):
    def test_uncertainty_and_unknown_outputs_fail_closed(self):
        for label,confidence in [('NORMAL',.699),('OVERHEAT',.3),('UNKNOWN',1.),('NORMAL',float('nan')),('NORMAL',1.1)]:
            self.assertEqual(decision(label,confidence),'RECHECK')

    def test_stop_dominates_requested_velocity(self):
        for requested in [.1,.52,100.]:
            v,w,state=safety_filter(requested,1.,.4)
            self.assertEqual((v,w,state),(0.,0.,'LIDAR_STOP'))
        for command in [(float('nan'),0,2),(0,float('inf'),2),(.3,0,float('nan'))]:
            self.assertEqual(safety_filter(*command),(0.,0.,'INVALID_STOP'))

    def test_planned_segments_respect_inflated_hazard(self):
        zones=[(0,1.8,1.4)]
        path=astar((-1.4,.5),(2.7,.5),[],zones)
        self.assertTrue(any(y<.15 for x,y in path))
        for a,b in zip(path,path[1:]):
            for alpha in np.linspace(0,1,11):
                xy=np.array(a)*(1-alpha)+np.array(b)*alpha
                self.assertFalse(blocked(*xy,[],zones))

class ExecutionEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        file=ROOT/'results/evaluation.json'
        if not file.exists():raise unittest.SkipTest('Run main.py --evaluate before evidence tests')
        cls.runs=json.loads(file.read_text())

    def test_demo_completes_and_comparison_is_matched(self):
        runs={r['policy']:r for r in self.runs if r['seed']==100}
        self.assertTrue(runs['adaptive']['completed'])
        self.assertEqual([r['prediction'] for r in runs['adaptive']['inspections']],['NORMAL','OVERHEAT','VIBRATION'])
        self.assertEqual(runs['adaptive']['hazard_violation_episodes'],0)
        self.assertGreater(runs['fixed']['hazard_violation_episodes'],0)
        self.assertEqual([r['features'] for r in runs['adaptive']['inspections']],
                         [r['features'] for r in runs['fixed']['inspections']])

    def test_physical_trajectory_and_safety_commands(self):
        self.assertEqual(len(self.runs),10)
        for run in self.runs:
            self.assertEqual(run['collision_physics_step_count'],0)
            if run['policy']=='adaptive':self.assertEqual(run['hazard_violation_sample_count'],0)
            path=ROOT/'results'/f"{run['policy']}_{run['seed']}_trajectory.csv"
            with path.open(encoding='utf-8') as stream:
                rows=list(csv.DictReader(stream))
            for row in rows:
                self.assertTrue(all(math.isfinite(float(row[k])) for k in ['x_m','y_m','v_command_m_s','w_command_rad_s']))
                self.assertLessEqual(abs(float(row['v_command_m_s'])),.520001)
                if row['guard']=='LIDAR_STOP':self.assertEqual(float(row['v_command_m_s']),0.)
            for a,b in zip(rows,rows[1:]):
                distance=math.hypot(float(b['x_m'])-float(a['x_m']),float(b['y_m'])-float(a['y_m']))
                self.assertLess(distance,.05,'Unexpected pose discontinuity / teleportation')

if __name__=='__main__':unittest.main(verbosity=2)
