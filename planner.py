"""Grid A*, footprint inflation, no diagonal corner cutting."""
import heapq
import math
import numpy as np

BOUNDS = (-3.8, 3.8, -2.8, 2.8)
RESOLUTION = .10
ROBOT_RADIUS = .32  # conservative bound covering chassis, wheels and caster

def blocked(x, y, obstacles, zones):
    if not (-3.65+ROBOT_RADIUS <= x <= 3.65-ROBOT_RADIUS and
            -2.65+ROBOT_RADIUS <= y <= 2.65-ROBOT_RADIUS): return True
    for ox, oy, hx, hy in obstacles:
        if abs(x-ox) <= hx+ROBOT_RADIUS+.24 and abs(y-oy) <= hy+ROBOT_RADIUS+.24:
            return True
    return any(math.hypot(x-cx,y-cy) <= radius+ROBOT_RADIUS+.06 for cx,cy,radius in zones)

def astar(start, goal, obstacles, zones):
    xmin,xmax,ymin,ymax = BOUNDS
    nx,ny = int(round((xmax-xmin)/RESOLUTION))+1,int(round((ymax-ymin)/RESOLUTION))+1
    def node(p): return (int(round((p[0]-xmin)/RESOLUTION)),int(round((p[1]-ymin)/RESOLUTION)))
    def world(n): return (xmin+n[0]*RESOLUTION,ymin+n[1]*RESOLUTION)
    occupied = np.ones((nx,ny),dtype=bool)
    for i in range(nx):
        for j in range(ny): occupied[i,j] = blocked(*world((i,j)),obstacles,zones)
    source, target = node(start),node(goal)
    if occupied[target] or occupied[source]:
        raise RuntimeError(f'Planning start/goal occupied: {start} -> {goal}')
    q=[(0.,source)]; cost={source:0.}; parent={}
    while q:
        _, current=heapq.heappop(q)
        if current==target: break
        for di,dj in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
            a,b=current; ni,nj=a+di,b+dj
            if not (0<=ni<nx and 0<=nj<ny) or occupied[ni,nj]: continue
            if di and dj and (occupied[a+di,b] or occupied[a,b+dj]): continue
            nxt=(ni,nj); value=cost[current]+math.hypot(di,dj)
            if value<cost.get(nxt,math.inf):
                cost[nxt]=value; parent[nxt]=current
                heapq.heappush(q,(value+math.hypot(target[0]-ni,target[1]-nj),nxt))
    if target not in cost: raise RuntimeError('No collision-free path')
    path=[target]
    while path[-1]!=source: path.append(parent[path[-1]])
    return [world(n) for n in reversed(path)]

def wrap(angle): return (angle+math.pi)%(2*math.pi)-math.pi

def follow(position,yaw,path,index):
    while index<len(path)-1 and math.dist(position,path[index])<.20: index+=1
    distance=math.dist(position,path[-1])
    if distance<.13: return 0.,0.,index,True
    target=path[index]
    error=wrap(math.atan2(target[1]-position[1],target[0]-position[0])-yaw)
    angular=float(np.clip(2.8*error,-1.8,1.8))
    speed=min(.52,.16+distance*.8)*max(0.,math.cos(error))
    if abs(error)>.60: speed=0.
    return speed,angular,index,False

def safety_filter(speed,angular,front_distance):
    """Independent LiDAR stop/slow layer. No learned label can relax it."""
    if not all(math.isfinite(x) for x in [speed,angular,front_distance]):
        return 0.,0.,'INVALID_STOP'
    speed=float(np.clip(speed,0.,.52)); angular=float(np.clip(angular,-1.8,1.8))
    if speed>.02 and front_distance<.48: return 0.,0.,'LIDAR_STOP'
    if speed>.02 and front_distance<.78:
        speed=min(speed,.18)
        return speed,angular,'LIDAR_SLOW'
    return speed,angular,'CLEAR'
