"""Render actual PyBullet frames with Japanese explanatory overlays to MP4."""
from pathlib import Path
import math
import subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import pybullet as p

W,H,FPS=1280,720,10
BG='#0b1725'; PANEL='#12263a'; WHITE='#edf5fb'; MUTED='#a0b4c8'; CYAN='#59e0d0'
LABELS={'NORMAL':'正常','OVERHEAT':'過熱','VIBRATION':'振動異常'}

class Recorder:
    def __init__(self,path,font):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.font_path=str(font);self.fonts={};self.count=0;self.last=None;self.captures=set()
        self.view=p.computeViewMatrix([7.,-9.,11.],[0.,0.,0.],[0,0,1])
        self.projection=p.computeProjectionMatrixFOV(30.,860/480,.1,40.)
        self.matrix=np.array(self.projection).reshape(4,4,order='F')@np.array(self.view).reshape(4,4,order='F')
        self.pipe=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-vcodec','rawvideo',
            '-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264',
            '-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(self.path)],stdin=subprocess.PIPE)
        intro=self.card('AIで「見つける」から「避ける」へ',[
            'SENTINEL ROVER  |  自律巡回・設備点検ロボット',
            '温度・振動 → 学習済みAI → 危険区域の追加 → 経路の再計画',
            '人の横断にはLiDARで停止。3台を点検し、出発地点へ戻ります。',
            'PyBullet物理シミュレーション / 合成センサー / 実機ではありません',
            '移動シーンは等速（シミュレーション時刻基準） / 解説カードは別尺'])
        for _ in range(8*FPS):self.write(intro)

    def font(self,size):
        if size not in self.fonts:self.fonts[size]=ImageFont.truetype(self.font_path,size)
        return self.fonts[size]

    def txt(self,draw,xy,text,size=22,fill=WHITE):draw.text(xy,text,font=self.font(size),fill=fill)

    def card(self,title,lines):
        im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
        d.rectangle((56,68,1224,74),fill=CYAN)
        self.txt(d,(60,100),'PHYSICAL AI  /  FINAL PROJECT',20,CYAN)
        self.txt(d,(60,158),title,38)
        for i,line in enumerate(lines):self.txt(d,(64,270+i*66),line,23,MUTED if i>=3 else WHITE)
        self.txt(d,(60,656),'SENTINEL ROVER  |  reproducible simulation + trained machine learning',18,MUTED)
        return im

    def project(self,x,y,z=.02):
        q=self.matrix@np.array([x,y,z,1.]);q=q[:3]/q[3]
        return ((q[0]+1)*430,(1-q[1])*240)

    def write(self,im):
        self.pipe.stdin.write(im.convert('RGB').tobytes());self.count+=1

    def frame(self,s):
        im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
        self.txt(d,(24,18),'SENTINEL ROVER',34)
        self.txt(d,(25,64),'設備の状態を学習し、安全な巡回経路をつくる',21,MUTED)
        self.txt(d,(940,24),f"SIM  {s['t']:05.1f} s",27,CYAN)
        self.txt(d,(940,63),'等速 / PyBullet / 10 fps',18,MUTED)
        render=p.getCameraImage(860,480,self.view,self.projection,
            renderer=p.ER_TINY_RENDERER,lightDirection=[-3,-2,7],shadow=0)
        scene=Image.fromarray(np.array(render[2],dtype=np.uint8).reshape(480,860,4)[:,:,:3]).convert('RGBA')
        overlay=Image.new('RGBA',scene.size,(0,0,0,0));o=ImageDraw.Draw(overlay)
        for cx,cy,r in s['zones']:
            points=[self.project(cx+r*math.cos(a),cy+r*math.sin(a)) for a in np.linspace(0,2*math.pi,80)]
            o.polygon(points,fill=(237,67,54,55));o.line(points+[points[0]],fill=(225,48,42,210),width=3)
            points2=[self.project(cx+(r+.32)*math.cos(a),cy+(r+.32)*math.sin(a)) for a in np.linspace(0,2*math.pi,80)]
            o.line(points2,fill=(235,118,85,140),width=2)
        if len(s['trail'])>1:o.line([self.project(*point) for point in s['trail']],fill=(10,113,137,210),width=4)
        if len(s['path'])>1:o.line([self.project(*point,.04) for point in s['path']],fill=(17,174,139,220),width=3)
        for k,(x,y) in zip('ABC',[(-2.75,1.8),(0,1.8),(2.7,1.8)]):
            px,py=self.project(x,y,1.15)
            o.rounded_rectangle((px-18,py-18,px+18,py+15),radius=6,fill=(11,23,37,240))
            o.text((px-9,py-16),k,font=self.font(23),fill='white')
        scene=Image.alpha_composite(scene,overlay)
        im.paste(scene.convert('RGB'),(24,120))
        d.rounded_rectangle((904,120,1256,600),radius=14,fill=PANEL)
        status={'NAVIGATE':'巡回中','INSPECT':'センサー取得中','YIELD':'横断を待機','COMPLETE':'巡回完了'}[s['state']]
        color='#f4b860' if s['state']=='YIELD' else CYAN
        self.txt(d,(925,139),status,27,color)
        self.txt(d,(925,184),f"前方距離  {s['front']:.2f} m",20,MUTED)
        self.txt(d,(925,218),f"走行距離  {s['length']:.1f} m",20,MUTED)
        self.txt(d,(925,269),'AIの判定結果',21)
        for i,k in enumerate('ABC'):
            result=next((a for a in s['inspections'] if a['equipment']==k),None)
            yy=308+i*75
            if result:
                label=result['prediction'];conf=result['confidence'];c={'NORMAL':'#59e0d0','OVERHEAT':'#ff8175','VIBRATION':'#f4b860'}[label]
                self.txt(d,(925,yy),f"{k}  {LABELS[label]}",23,c)
                self.txt(d,(1149,yy+2),f'{conf:.0%}',20,c)
                d.rounded_rectangle((925,yy+37,1227,yy+43),radius=3,fill='#31465d')
                d.rounded_rectangle((925,yy+37,925+302*conf,yy+43),radius=3,fill=c)
            else:self.txt(d,(925,yy),f'{k}  未点検',23,MUTED)
        self.txt(d,(925,548),'数値 = モデルの推定確率',17,MUTED)
        self.txt(d,(925,574),'実世界の正しさは保証しません',16,MUTED)
        if s['state']=='COMPLETE':
            caption='3台の点検と帰還が完了。判定・経路・停止履歴をログへ保存。'
        elif s['state']=='YIELD':
            caption='人が横断。AI判定と独立したLiDARの安全層が停止を指示。'
        elif s['state']=='INSPECT':
            caption='点検位置で停止し、温度と振動の合成センサーデータを取得。'
        elif s['goal_index']==2:
            caption='Bの過熱を検知。赤い危険区域を避けてCへ経路を再計画。'
        elif s['goal_index']==3:
            caption='Cの振動異常を記録。危険区域を避けた経路で帰還。'
        elif s['goal_index']==1:
            caption='Aは正常と判定。次の設備Bへ向かいます。'
        else:caption='車輪モーターで移動。121本のLiDARレイで前方障害物を監視。'
        self.txt(d,(26,623),caption,23)
        self.txt(d,(26,669),'青 = 走行履歴    緑 = 計画経路    赤 = 過熱の危険区域（外周は車体分の余裕）',18,MUTED)
        self.write(im);self.last=im
        label=None
        if s['state']=='YIELD':label='yield'
        elif s['goal_index']==2 and s['position'][0]>-.4:label='replan'
        elif s['state']=='COMPLETE':label='complete'
        if label and label not in self.captures:
            im.save(self.path.parent/f'scene_{label}.png');self.captures.add(label)

    def finish(self,metrics):
        extra=max(0,65*FPS-self.count)
        end=self.card('AIの判断を、ロボットの行動につなぐ',[
            f"3台の点検と帰還: {'完了' if metrics['completed'] else metrics['terminal']}   |   帰還 {metrics['completion_time_s']} 秒",
            f"障害物接触（240 Hz観測） {metrics['collision_physics_step_count']}   |   危険区域侵入 {metrics['hazard_violation_episodes']} 回",
            'AI: Random Forest  /  移動: A* + 差動二輪モーター制御',
            '検証範囲: 合成センサー・既知地図・既知自己位置のシミュレーション',
            '実環境への応用には、実測データ・自己位置推定・安全検証が必要'])
        for _ in range(max(10*FPS,extra)):self.write(end)
        end.save(self.path.parent/'scene_summary.png')

    def close(self):
        if self.pipe is not None:
            self.pipe.stdin.close();code=self.pipe.wait();self.pipe=None
            if code:raise RuntimeError(f'FFmpeg failed: {code}')
