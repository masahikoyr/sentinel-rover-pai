"""Train, simulate, compare and optionally record the complete final project."""
from pathlib import Path
import argparse
import json
import platform
import importlib.metadata
import joblib
from sensors import train
from simulation import simulate

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parent/'results')
    parser.add_argument('--video',action='store_true',help='Record the seed-100 adaptive run with FFmpeg')
    parser.add_argument('--evaluate',action='store_true',help='Run BOTH policies on predeclared seeds 100..104')
    args=parser.parse_args()
    model,ml=train(args.out)
    seeds=range(100,105) if args.evaluate else [100]
    results=[]
    for seed in seeds:
        for policy in ['adaptive','fixed']:
            video=args.out/'SentinelRover_demo.mp4' if args.video and seed==100 and policy=='adaptive' else None
            metrics=simulate(model,args.out,policy,seed,video)
            results.append(metrics)
            print(f"{policy} seed={seed}: {metrics['terminal']}, hazard={metrics['hazard_violation_time_s']} s",flush=True)
    env={'python':platform.python_version(),'platform':platform.platform(),
         'packages':{k:importlib.metadata.version(k) for k in ['numpy','scikit-learn','pybullet','Pillow','reportlab','matplotlib','joblib']}}
    (args.out/'environment.json').write_text(json.dumps(env,indent=2),encoding='utf-8')
    (args.out/'evaluation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print('Outputs:',args.out)

if __name__=='__main__':main()
