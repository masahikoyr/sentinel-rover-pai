"""Build a four-page Japanese report from saved, measured execution results."""
from pathlib import Path
import csv,json,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Circle,Rectangle
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor,white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/'results'; BUILD=ROOT/'build';BUILD.mkdir(exist_ok=True)
FONT=ROOT/'assets/fonts/ipaexg.ttf'
JP=FontProperties(fname=str(FONT),size=9)
plt.rcParams.update({'font.family':JP.get_name(),'axes.unicode_minus':False,
                    'axes.spines.top':False,'axes.spines.right':False})
# Explicitly register the local font, so plots do not depend on a font cache.
from matplotlib import font_manager
font_manager.fontManager.addfont(str(FONT))
pdfmetrics.registerFont(TTFont('IPAexG',str(FONT)))
NAVY=HexColor('#112a40');TEAL=HexColor('#078b80');GRAY=HexColor('#506274');PALE=HexColor('#edf3f6')
PAGE_W,PAGE_H=595.276,841.89

def load(name):return json.loads((RESULTS/name).read_text(encoding='utf-8'))

def make_charts(ml,runs):
    fig,axes=plt.subplots(1,2,figsize=(8.8,2.7),layout='constrained')
    for ax,key,title in zip(axes,['test','stress'],['通常の合成テスト','ノイズ・温度偏りを加えたテスト']):
        cm=np.array(ml[key]['confusion_matrix'])
        ax.imshow(cm,cmap='Blues',vmin=0,vmax=200)
        ax.set_xticks([0,1,2],['正常','過熱','振動異常'],fontproperties=JP)
        ax.set_yticks([0,1,2],['正常','過熱','振動異常'],fontproperties=JP)
        ax.set_xlabel('AIの予測',fontproperties=JP);ax.set_ylabel('生成時の正解',fontproperties=JP)
        ax.set_title(f"{title}\n正解率 {ml[key]['accuracy']:.1%}",fontproperties=JP)
        for i in range(3):
            for j in range(3):ax.text(j,i,str(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>100 else '#17354e',fontsize=10)
    fig.savefig(BUILD/'classification.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.8,3.6),layout='constrained')
    for x,y,hx,hy in [(-2.75,1.8,.38,.38),(0,1.8,.38,.38),(2.7,1.8,.38,.38),(-.8,-1.3,.45,.45),(1.5,-1.5,.45,.45)]:
        ax.add_patch(Rectangle((x-hx,y-hy),2*hx,2*hy,facecolor='#667b8a',alpha=.85))
    ax.add_patch(Circle((0,1.8),1.72,facecolor='#ffe0d9',edgecolor='#e89982',linestyle=':',label='危険区域＋車体半径'))
    ax.add_patch(Circle((0,1.8),1.4,facecolor='#f5b7ac',alpha=.45,edgecolor='#c34d38'))
    for policy,color,line,label in [('fixed','#dd7a22','--','比較：区域を経路へ反映しない'),('adaptive','#078b80','-','提案：AIで区域を反映')]:
        with (RESULTS/f'{policy}_100_trajectory.csv').open() as stream:rows=list(csv.DictReader(stream))
        ax.plot([float(r['x_m']) for r in rows],[float(r['y_m']) for r in rows],line,color=color,lw=2,label=label)
    for k,(x,y) in zip('ABC',[(-2.75,1.8),(0,1.8),(2.7,1.8)]):ax.text(x,y,k,ha='center',va='center',color='white',weight='bold')
    ax.scatter([-3.05],[-2.15],color='#112a40',s=60,marker='*',label='出発・帰還点',zorder=5)
    ax.set(xlim=(-3.8,3.8),ylim=(-2.8,2.8),xlabel='x [m]',ylabel='y [m]');ax.set_aspect('equal')
    ax.grid(alpha=.16);ax.legend(loc='lower right',prop=JP,framealpha=.95)
    fig.savefig(BUILD/'trajectory.png',dpi=180);plt.close(fig)

class Report:
    def __init__(self):
        self.c=canvas.Canvas(str(ROOT/'report_SentinelRover.pdf'),pagesize=(PAGE_W,PAGE_H))
        self.c.setTitle('SENTINEL ROVER - Physical AI Final Project')
        self.c.setAuthor('');self.c.setSubject('Synthetic sensor AI and mobile robot simulation')
        self.markdown=[]

    def txt(self,x,y,text,size=10,color=NAVY):
        self.c.setFillColor(color);self.c.setFont('IPAexG',size);self.c.drawString(x,y,text)

    def para(self,text,y,size=10,width=511):
        style=ParagraphStyle('body',fontName='IPAexG',fontSize=size,leading=size*1.65,
            textColor=NAVY,wordWrap='CJK',spaceAfter=0)
        p=Paragraph(text,style);w,h=p.wrap(width,700);p.drawOn(self.c,42,y-h)
        self.markdown.append(text.replace('<br/>','\n').replace('<b>','').replace('</b>',''))
        return y-h

    def section(self,n,title,y):
        self.c.setFillColor(TEAL);self.c.roundRect(42,y-21,25,24,4,fill=1,stroke=0)
        self.txt(49,y-13,str(n),12,white);self.txt(79,y-14,title,14)
        self.markdown.append(f'\n## {n}. {title}\n')
        return y-37

    def table(self,rows,y,widths,font=9):
        style=ParagraphStyle('cell',fontName='IPAexG',fontSize=font,leading=font*1.45,wordWrap='CJK',textColor=NAVY)
        data=[[Paragraph(str(x),style) for x in row] for row in rows]
        t=Table(data,colWidths=widths,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#d8e9ed')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[HexColor('#f1f5f7'),white]),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),
            ('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),
            ('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.6,HexColor('#9ab6c1'))]))
        w,h=t.wrap(511,700);t.drawOn(self.c,42,y-h)
        lines=['| '+' | '.join(str(x).replace('<br/>',' / ') for x in row)+' |' for row in rows]
        lines.insert(1,'| '+' | '.join('---' for _ in rows[0])+' |')
        self.markdown.append('\n'.join(lines))
        return y-h

    def page(self,number,heading):
        self.c.setFillColor(NAVY);self.c.rect(0,PAGE_H-64,PAGE_W,64,fill=1,stroke=0)
        self.txt(42,PAGE_H-28,'PHYSICAL AI 応用1  /  FINAL PROJECT',10,HexColor('#83d5cf'))
        self.txt(42,PAGE_H-49,heading,15,white)
        self.c.setStrokeColor(HexColor('#d3e0e6'));self.c.line(42,39,553,39)
        self.txt(42,24,'SENTINEL ROVER  |  Simulation & synthetic data',8,GRAY)
        self.txt(522,24,f'{number} / 4',8,GRAY)

    def endpage(self):self.c.showPage()

    def build(self,ml,runs):
        demo=next(r for r in runs if r['policy']=='adaptive' and r['seed']==100)
        fixed=next(r for r in runs if r['policy']=='fixed' and r['seed']==100)
        self.page(1,'AIの判定を、安全な巡回行動につなぐ')
        self.txt(42,738,'SENTINEL ROVER',31)
        y=self.para('AIで設備の異常を判別し、危険を避けて巡回する点検ロボット',707,14)
        y=self.para('学習済みAI × 差動二輪ロボット × 危険区域を反映する経路計画',y-12,10)
        self.c.drawImage(str(RESULTS/'scene_replan.png'),42,353,width=511,height=287.4)
        self.markdown.append('![実行画面](results/scene_replan.png)')
        self.txt(42,337,'図1  実行画面：Bの過熱を検知し、危険区域の外を通ってCへ向かう。',8.7,GRAY)
        y=self.section(1,'目的と実現したタスク',310)
        y=self.para('工場・倉庫の点検を題材に、単に異常を表示するだけでなく、AIの判定で移動の方針を変更するロボットを設計した。3台の設備を順番に点検し、過熱設備を避けて出発地点へ戻る。横断者が前方に近づくと、独立した安全層で停止する。',y,10)
        y=self.table([['観点','本作品での工夫'],
            ['創造性','設備の異常分類を、巡回ロボットの通行制約へ変換する。'],
            ['実装','自作URDF・車輪モーター制御・LiDAR・A*・学習済み分類器を統合。'],
            ['検証','区域反映を無効にした比較条件と、実行ログで行動の違いを評価。']],y-14,[76,435],9)
        self.para('検証範囲：PyBulletの物理シミュレーション。設備信号は合成、地図と自己位置は既知。実機実験は実施していない。',y-13,9)
        self.endpage()

        self.page(2,'AIの中身と、判断を行動へ変える仕組み')
        y=self.section(2,'AIとロボット制御の接続',750)
        y=self.table([['段階','処理内容'],
            ['観測','点検位置で停止し、設備の合成振動256点／1秒と温度16点を取得。'],
            ['特徴量・学習','温度の平均・標準偏差、振動RMS・尖度、低域・高域パワー比の6特徴。Random Forest 120本、最大深さ8。'],
            ['意思決定','正常：巡回継続／過熱：危険区域を追加／振動異常：要保全として記録。最大推定確率0.70未満は停止し、再点検要求。'],
            ['移動・停止','A*→経路追従→左右車輪の速度指令。LiDAR停止層が速度を制限。A*と停止制御は非学習。']],y,[76,435],9.2)
        y=self.section(3,'合成データによる分類評価',y-23)
        y=self.para('学習1,800件（各600件、seed=42）。通常テスト600件（seed=2026）とノイズ・温度偏りを加えたストレス600件（seed=2027）を独立に生成した。学習と同じ信号の再利用は行わず、評価値で閾値の調整も行っていない。',y,9.5)
        # Place measured confusion matrices directly below the text.
        figure_top=y-30
        self.c.drawImage(str(BUILD/'classification.png'),42,figure_top-160,width=511,height=157)
        self.markdown.append('![分類評価](build/classification.png)')
        self.txt(42,figure_top-174,'図2  混同行列。行が正解、列がAIの予測。各クラス200件。',8.4,GRAY)
        y=figure_top-192
        y=self.table([['指標','通常の合成テスト','ストレス条件'],
            ['正解率 / Macro F1',f"{ml['test']['accuracy']:.1%} / {ml['test']['macro_f1']:.3f}",f"{ml['stress']['accuracy']:.1%} / {ml['stress']['macro_f1']:.3f}"],
            ['推定確率0.70以上の割合',f"{ml['test']['accepted_fraction']:.1%}",f"{ml['stress']['accepted_fraction']:.1%}"],
            ['上記に限った正解率',f"{ml['test']['accuracy_when_accepted']:.1%}",f"{ml['stress']['accuracy_when_accepted']:.1%}"]],y,[205,153,153],8.8)
        self.para('考察：ストレス条件では正解率が低下し、58.0%が判定保留になる。確率閾値は誤判定を減らす一方、運用停止を増やす。高信頼に見える誤判定も残るため、実データでの校正と独立した過熱保護が必要である。',y-13,9.4)
        self.endpage()

        self.page(3,'物理シミュレーションによる検証結果')
        y=self.section(4,'同じ条件で経路計画を比較',750)
        y=self.para('提案方式は過熱判定後に危険区域をA*へ反映し、比較方式はこの反映だけを無効にする。両方式のAI・地図・横断者・LiDAR停止層は同じ。危険区域は設備B中心から半径1.4 mで、車体半径0.32 mと計画余裕0.06 mを考慮する。',y,9.5)
        self.c.drawImage(str(BUILD/'trajectory.png'),42,420,width=511,height=209)
        self.markdown.append('![軌跡比較](build/trajectory.png)')
        self.txt(42,405,'図3  seed=100の実際の軌跡。比較方式はBの周囲へ進入する。',8.5,GRAY)
        y=self.table([['seed=100の実行結果','提案方式','比較方式'],
            ['3台点検・帰還','完了','完了'],
            ['完了時間',f"{demo['completion_time_s']:.1f} 秒",f"{fixed['completion_time_s']:.1f} 秒"],
            ['走行距離',f"{demo['path_length_m']:.3f} m",f"{fixed['path_length_m']:.3f} m"],
            ['危険区域への侵入',f"{demo['hazard_violation_episodes']} 回 / {demo['hazard_violation_time_s']:.1f} 秒",f"{fixed['hazard_violation_episodes']} 回 / {fixed['hazard_violation_time_s']:.1f} 秒"],
            ['障害物接触の物理ステップ数',str(demo['collision_physics_step_count']),str(fixed['collision_physics_step_count'])],
            ['最小離隔 / LiDAR停止時間',f"{demo['min_obstacle_clearance_m']:.3f} m / {demo['lidar_stop_time_s']:.1f} 秒",f"{fixed['min_obstacle_clearance_m']:.3f} m / {fixed['lidar_stop_time_s']:.1f} 秒"]],387,[205,153,153],9)
        y=self.para('追加検証：事前に定めたセンサーseed=100〜104で計10走行を実行。両方式とも5/5完了し、提案は5/5で侵入0回、比較は5/5で侵入2回だった。地図と横断者は固定であり、環境変化への頑健性を示す結果ではない。',y-17,9.5)
        self.para('計測条件：物理240 Hz、制御・侵入・離隔20 Hz、LiDAR 121本。接触は床を除く障害物との法線力0.05 N超を全物理ステップで確認。侵入は区域追加後の距離＜1.4＋0.32 mで集計した。',y-12,8.7)
        self.endpage()

        self.page(4,'実装の再現性、限界、今後の研究')
        y=self.section(5,'実装と再現方法',750)
        y=self.para('Python 3.12 / PyBullet 3.2.7 / scikit-learn 1.8.0。GPUや外部AI APIは使わない。URDFは基本形状で構成し、車輪半径0.10 m・左右間隔0.40 mの差動二輪を速度モーターで駆動する。本体の姿勢は物理計算結果を使用する。地図・自己位置はシミュレータの既知情報であり、SLAMではない。',y,9.6)
        y=self.para('再現コマンド：<br/>python -m pip install -r requirements.txt<br/>python main.py --evaluate --video<br/>python tests.py<br/>python report.py',y-13,9.5)
        y=self.para('results/に軌跡CSV・イベントJSON・評価JSONと動画を保存する。添付動画は65秒、日本語解説付き・無音。移動シーンはシミュレーション時刻基準の等速で、冒頭・末尾は説明カードである。5件のテストで停止優先、未知出力の停止、区域回避、軌跡の連続性などを確認した。',y-12,9.4)
        y=self.section(6,'工学的な考察：セキュリティ×AI',y-23)
        y=self.para('AIには設備の状態分類を担当させ、速度上限や停止条件は別の制御層に置いた。この分離により、判定結果から無制限な移動指令を出さない構造にした。ただし、センサー偽装や通信攻撃への有効性を試験したものではない。',y,9.6)
        y=self.para('研究仮説として「分類精度だけでなく、不確実性に応じた停止方針と独立した安全制約が、誤移動リスクと稼働率の両立に寄与する」を設定できる。今後は実測信号、センサー欠損・偽装、自己位置誤差、未学習設備を加え、侵入率・過熱見逃し率・停止時間の関係を比較したい。モデル確率は安全性の証明ではなく、閾値0.70やLiDAR停止距離0.48 mも実機基準ではない。',y-11,9.6)
        y=self.section(7,'出典・制作支援',y-23)
        y=self.para('［1］配布資料「最終課題（10_19 改訂版）」：課題・提出要件。<br/>［2］PyBullet公式リポジトリ・Quickstart Guide：物理、URDF、車輪モーター、描画。<br/>github.com/bulletphysics/bullet3<br/>［3］scikit-learn公式：Random Forestおよび分類評価。<br/>scikit-learn.org/stable/modules/ensemble.html<br/>scikit-learn.org/stable/modules/model_evaluation.html<br/>［4］IPAexゴシック：同梱のIPAフォントライセンスに基づき使用。',y,8.8)
        self.para('制作支援として生成AIを設計・実装・説明文の作成に使用した。数値は本コードを実行して得たログに基づく。実機実験は実施していない。',y-12,8.8)
        self.endpage();self.c.save()
        (ROOT/'report_SentinelRover.md').write_text('# SENTINEL ROVER\n\n'+'\n\n'.join(self.markdown),encoding='utf-8')

def main():
    ml=load('ml_metrics.json');runs=load('evaluation.json')
    make_charts(ml,runs);Report().build(ml,runs)
    print(ROOT/'report_SentinelRover.pdf')

if __name__=='__main__':main()
