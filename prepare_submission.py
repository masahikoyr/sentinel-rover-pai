"""Rename the PDF and generate YouTube upload text using a course account ID."""
from pathlib import Path
import argparse,re,shutil

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--account-id',required=True,help='OmniCampus account ID, not legal name or email')
    a=p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',a.account_id):
        p.error('Use the course account ID: ASCII letters, digits, underscore or hyphen only')
    root=Path(__file__).resolve().parent
    output=root/'submission_ready';output.mkdir(exist_ok=True)
    report=root/'report_SentinelRover.pdf'
    if not report.exists():p.error('Generate the report with: python report.py')
    dest=output/f'説明資料_PAI最終課題_{a.account_id}.pdf'
    shutil.copyfile(report,dest)
    text=f'''タイトル: PAI最終課題_{a.account_id}

SENTINEL ROVER: AIで異常を判別し、危険を避けて巡回する点検ロボット。
PyBulletの物理シミュレーション上で、差動二輪ロボットが3台の設備を点検し帰還します。
合成温度・振動データで学習したRandom Forestの判定をA*の経路計画へ反映します。
LiDARの独立した安全層により、横断者が近づくと停止します。

移動シーンは等速（シミュレーション時刻基準）。冒頭・末尾に解説カードを含みます。
実機の撮影ではありません。センサーデータは合成です。
制作支援として生成AIを設計・実装・説明文の作成に使用しています。

GitHub: 公開リポジトリURLをここに記入
'''
    (output/'YouTube_upload_text.txt').write_text(text,encoding='utf-8')
    print(dest)
    print('YouTube title and description:',output/'YouTube_upload_text.txt')
    print('No publication or submission has been performed by this script.')

if __name__=='__main__':main()
