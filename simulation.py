"""Headless PyBullet dynamics, wheel velocity motors, LiDAR and mission FSM.

Robot pose is read from dynamics, never reset along a prerecorded trajectory.
Only the scripted pedestrian actor uses resetBasePositionAndOrientation.
"""
from pathlib import Path
import csv
import json
import math
import time
import numpy as np
import pybullet as p
from sensors import infer
from planner import astar, follow, safety_filter, ROBOT_RADIUS

ROOT = Path(__file__).resolve().parent
EQUIPMENT = [(-2.75,1.8),(0.,1.8),(2.7,1.8)]
GOALS = [(-2.75,.5),(-1.4,.5),(2.7,.5),(-3.05,-2.15)]
OBSTACLES = [(x,y,.38,.38) for x,y in EQUIPMENT]+[(-.8,-1.3,.45,.45),(1.5,-1.5,.45,.45)]

def box(x,y,z,hx,hy,hz,color,collision=True):
    shape=p.createCollisionShape(p.GEOM_BOX,halfExtents=[hx,hy,hz]) if collision else -1
    visual=p.createVisualShape(p.GEOM_BOX,halfExtents=[hx,hy,hz],rgbaColor=color)
    return p.createMultiBody(0,shape,visual,[x,y,z])

def build_world():
    p.resetSimulation(); p.setGravity(0,0,-9.81); p.setTimeStep(1/240)
    p.setPhysicsEngineParameter(numSolverIterations=80,deterministicOverlappingPairs=1)
    box(0,0,-.12,40,40,.02,[.71,.77,.81,1],False)
    floor=box(0,0,-.06,3.9,2.9,.06,[.82,.87,.89,1])
    p.changeDynamics(floor,-1,lateralFriction=1.)
    for x in np.arange(-3.5,3.6,.5): box(float(x),0,.001,.004,2.7,.001,[.69,.77,.80,1],False)
    for y in np.arange(-2.5,2.6,.5): box(0,float(y),.001,3.7,.004,.001,[.69,.77,.80,1],False)
    walls=[box(0,-2.8,.15,3.9,.08,.15,[.18,.25,.32,1]),
           box(0,2.8,.15,3.9,.08,.15,[.18,.25,.32,1]),
           box(-3.8,0,.15,.08,2.8,.15,[.18,.25,.32,1]),
           box(3.8,0,.15,.08,2.8,.15,[.18,.25,.32,1])]
    machines=[]
    for x,y in EQUIPMENT:
        body=box(x,y,.48,.38,.38,.48,[.24,.34,.44,1]); machines.append(body)
        box(x,y-.385,.70,.25,.008,.11,[.10,.18,.23,1],False)
        for dx in [-.18,0,.18]: box(x+dx,y-.398,.46,.012,.006,.14,[.5,.65,.7,1],False)
    clutter=[box(x,y,.28,hx,hy,.28,[.46,.54,.60,1]) for x,y,hx,hy in OBSTACLES[3:]]
    robot=p.loadURDF(str(ROOT/'assets/rover.urdf'),[-3.05,-2.15,.17])
    for j in [0,1]:
        p.changeDynamics(robot,j,lateralFriction=1.3,spinningFriction=.001,rollingFriction=.001)
        p.setJointMotorControl2(robot,j,p.VELOCITY_CONTROL,targetVelocity=0,force=4.)
    for j in [2,3]: p.changeDynamics(robot,j,lateralFriction=.001,spinningFriction=0,rollingFriction=0)
    p.changeDynamics(robot,-1,linearDamping=.03,angularDamping=.03)
    actor_shape=p.createCollisionShape(p.GEOM_CYLINDER,radius=.22,height=.85)
    actor_visual=p.createVisualShape(p.GEOM_CYLINDER,radius=.22,length=.85,rgbaColor=[.94,.58,.18,1])
    actor=p.createMultiBody(0,actor_shape,actor_visual,[-2.75,-.75,.425])
    head=p.createMultiBody(0,-1,p.createVisualShape(p.GEOM_SPHERE,radius=.16,rgbaColor=[.97,.72,.4,1]),[-2.75,-.75,1.])
    for _ in range(120): p.stepSimulation()
    return robot,actor,head,machines,walls+machines+clutter+[actor]

def lidar(robot):
    pos,orn=p.getBasePositionAndOrientation(robot)
    yaw=p.getEulerFromQuaternion(orn)[2]
    angles=yaw+np.linspace(-math.pi,math.pi,121)
    starts=[[pos[0]+.34*math.cos(a),pos[1]+.34*math.sin(a),.25] for a in angles]
    ends=[[pos[0]+3.*math.cos(a),pos[1]+3.*math.sin(a),.25] for a in angles]
    hits=p.rayTestBatch(starts,ends)
    ranges=np.array([.34+h[2]*2.66 for h in hits])
    front=float(ranges[np.abs(np.linspace(-math.pi,math.pi,121))<.40].min())
    points=[[pos[0]+r*math.cos(a),pos[1]+r*math.sin(a)] for r,a in zip(ranges,angles)]
    return front,points

def simulate(model,out,policy='adaptive',seed=100,video=None,max_time=120.):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    client=p.connect(p.DIRECT)
    robot,actor,head,machines,colliders=build_world()
    recorder=None
    if video:
        from video import Recorder
        recorder=Recorder(video,ROOT/'assets/fonts/ipaexg.ttf')
    zones=[]; events=[]; rows=[]; inspections=[]; frames=[]
    goal_index=0; path=[]; path_index=0; dwell=None; last_guard='CLEAR'
    length=0.; previous=None; min_clearance=math.inf; contact_steps=0; physics_contacts=0
    violation_steps=0; hazard_episodes=0; inside_previous=False; stop_steps=0
    completed=False; terminal=None; last_result=None; replans=0
    def event(t,kind,**extra):
        events.append({'time_s':round(t,3),'kind':kind,**extra})
    try:
        for tick in range(int(max_time*20)):
            t=tick/20
            actor_x=min(3.48,-2.75+max(0,t-5.)*.5)
            p.resetBasePositionAndOrientation(actor,[actor_x,-.75,.425],[0,0,0,1])
            p.resetBasePositionAndOrientation(head,[actor_x,-.75,1.],[0,0,0,1])
            pos,orn=p.getBasePositionAndOrientation(robot)
            xy=pos[:2]; yaw=p.getEulerFromQuaternion(orn)[2]
            if previous is not None: length+=math.dist(xy,previous)
            previous=xy
            clearance=min((point[8] for body in colliders for point in
                           p.getClosestPoints(robot,body,10.)),default=10.)
            min_clearance=min(min_clearance,clearance)
            contacts=[c for body in colliders for c in p.getContactPoints(robot,body) if c[9]>.05]
            contact_steps+=bool(contacts)
            inside=any(math.dist(xy,(cx,cy))<radius+ROBOT_RADIUS for cx,cy,radius in zones)
            violation_steps+=inside
            if inside and not inside_previous: hazard_episodes+=1
            inside_previous=inside
            front,lidar_points=lidar(robot)
            state='NAVIGATE'; v=w=0.; guard='CLEAR'
            if completed:
                state='COMPLETE'
            elif dwell is not None:
                state='INSPECT'
                if t-dwell>=2.:
                    observation=infer(model,goal_index,seed+goal_index)
                    observation.update({'equipment':'ABC'[goal_index],'time_s':t})
                    last_result=observation
                    event(t,'AI_INFERENCE',**observation)
                    if observation['action']=='RECHECK':
                        # A failed/uncertain reading terminates this short demo safely.
                        terminal='LOW_CONFIDENCE_STOP'; event(t,terminal); break
                    inspections.append(observation)
                    if observation['action']=='ADD_EXCLUSION':
                        zones.append((*EQUIPMENT[goal_index],1.4))
                        p.changeVisualShape(machines[goal_index],-1,rgbaColor=[.90,.25,.18,1])
                        event(t,'EXCLUSION_ADDED',center=list(EQUIPMENT[goal_index]),radius_m=1.4)
                    elif observation['action']=='FLAG_MAINTENANCE':
                        p.changeVisualShape(machines[goal_index],-1,rgbaColor=[.96,.61,.16,1])
                    else:
                        p.changeVisualShape(machines[goal_index],-1,rgbaColor=[.18,.64,.52,1])
                    goal_index+=1; dwell=None; path=[]
            else:
                if not path:
                    try:
                        path=astar(xy,GOALS[goal_index],OBSTACLES,zones if policy=='adaptive' else [])
                    except RuntimeError as exc:
                        terminal='NO_PATH_STOP';event(t,terminal,detail=str(exc));break
                    path_index=0; replans+=1
                    event(t,'PLAN',goal_index=goal_index,path=path)
                v,w,path_index,arrived=follow(xy,yaw,path,path_index)
                if arrived:
                    if goal_index==3:
                        completed=True;terminal='COMPLETE';completion_time=t;event(t,'RETURNED_TO_DOCK')
                    else:
                        dwell=t;event(t,'INSPECTION_START',equipment='ABC'[goal_index])
                else:
                    v,w,guard=safety_filter(v,w,front)
                    if guard=='LIDAR_STOP': state='YIELD';stop_steps+=1
            if guard!=last_guard:
                event(t,'GUARD',status=guard,front_range_m=round(front,3));last_guard=guard
            row={'time_s':round(t,3),'x_m':pos[0],'y_m':pos[1],'yaw_rad':yaw,
                 'v_command_m_s':v,'w_command_rad_s':w,'front_range_m':front,
                 'clearance_m':clearance,'state':state,'guard':guard,
                 'goal_index':goal_index,'hazard_violation':int(inside),'contact':int(bool(contacts))}
            rows.append(row)
            # Differential drive: wheel radius .10 m, track .40 m.
            # The simulated dynamics, contacts and wheel friction determine base motion.
            left=(v-w*.40/2)/.10;right=(v+w*.40/2)/.10
            p.setJointMotorControl2(robot,0,p.VELOCITY_CONTROL,targetVelocity=left,force=4.)
            p.setJointMotorControl2(robot,1,p.VELOCITY_CONTROL,targetVelocity=right,force=4.)
            if recorder and tick%2==0:  # 10 rendered frames / simulation second
                snapshot={'t':t,'position':xy,'yaw':yaw,'actor':(actor_x,-.75),
                    'path':path[path_index:],'trail':[(r['x_m'],r['y_m']) for r in rows[::4]],
                    'zones':zones,'state':state,'guard':guard,'front':front,
                    'inspections':inspections,'last_result':last_result,'events':events[-4:],
                    'length':length,'lidar':lidar_points,'goal_index':goal_index,
                    'policy':policy}
                recorder.frame(snapshot)
            for _ in range(12):
                p.stepSimulation()
                physics_contacts+=any(c[2] in colliders and c[9]>.05 for c in p.getContactPoints(bodyA=robot))
            if completed and t>=completion_time+3.: break
        if not terminal: terminal='TIMEOUT'
        metrics={'policy':policy,'seed':seed,'completed':completed,'terminal':terminal,
            'completion_time_s':round(completion_time,2) if completed else None,
            'simulated_time_s':round(rows[-1]['time_s'],2) if rows else 0,
            'path_length_m':round(length,3),'min_obstacle_clearance_m':round(min_clearance,4),
            'collision_sample_count':int(contact_steps),'collision_sample_period_s':.05,
            'collision_physics_step_count':int(physics_contacts),'collision_physics_period_s':1/240,
            'hazard_violation_sample_count':int(violation_steps),
            'hazard_violation_time_s':round(violation_steps*.05,3),
            'hazard_violation_episodes':hazard_episodes,'lidar_stop_time_s':round(stop_steps*.05,3),
            'planning_calls':replans,'inspections':inspections,
            'physics_hz':240,'control_hz':20,'lidar_rays':121,
            'localization':'PyBullet ground-truth pose, no SLAM',
            'sensor_scope':'Synthetic remote equipment telemetry within inspection region; not visual recognition.'}
        prefix=f'{policy}_{seed}'
        with (out/f'{prefix}_trajectory.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        (out/f'{prefix}_events.json').write_text(json.dumps(events,indent=2),encoding='utf-8')
        (out/f'{prefix}_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        if recorder: recorder.finish(metrics)
        return metrics
    finally:
        if recorder: recorder.close()
        p.disconnect(client)
