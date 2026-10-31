# SENTINEL ROVER

**AIで設備の異常を判別し、危険を避けて巡回する点検ロボット**  
Physical AI応用1講座 最終課題 / 独自シナリオ・自作URDF / CPUで実行

## 何をする作品か

差動二輪ロボットが設備A・B・Cを点検し、出発地点へ帰還します。
学習済みRandom Forestが温度・振動の合成データを「正常・過熱・振動異常」に分類します。
過熱と判定した設備の周囲には危険区域を追加し、A*の経路を計画し直します。
人が横断する場面では、AIの判定と独立したLiDARの停止層が移動を止めます。

3D画面はPyBulletで実際に物理計算した姿勢を描画しています。
ロボット本体を座標リセットして動かすアニメーションではありません。
座標リセットは横断者のシナリオ再生とワールドの初期化にのみ使用しています。
学習・推論は実行済みで、固定した正解ラベルをAIの予測として表示する実装ではありません。

## 実行環境

- Python 3.11または3.12を推奨。検証環境はPython 3.12 / Linux x86_64。
- GPU、ROS、Gazebo、APIキーは不要です。
- 動画生成にはFFmpegが必要です。録画はCPUソフトウェアレンダリングで行います。
- 依存関係の検証時バージョンをrequirements.txtに固定しています。
- Windows/macOSで環境構築が難しい場合は、同梱のColabノートブックを使えます。
  Colabそのものでは未検証です。検証済みなのは同じPythonコードのLinux実行です。

## ローカルでの再現

このREADMEと同じフォルダで実行します。

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShellでは .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py --evaluate --video
python tests.py
python report.py
```

FFmpegは別途インストールしてください。Ubuntuでは `sudo apt install ffmpeg`、
macOSのHomebrewでは `brew install ffmpeg` を利用できます。
PyBulletがソースビルドになるLinux環境ではC/C++コンパイラが必要です。
`clang++` が見つからない場合は、インストール前に `export CC=gcc` と `export CXX=g++` を設定します。
Ubuntuでは必要に応じて `sudo apt install build-essential` を実行します。

録画せず評価のみ実行する場合:

```bash
python main.py --evaluate
```

`--evaluate` は事前に定めたセンサー乱数seed 100〜104について、提案方式・比較方式の計10走行を行います。
地図・設備の真の状態・人の軌道は固定で、seedが変えるのはセンサー信号です。
移動環境を変えた網羅的な安全検証ではありません。
`--video` はseed=100の提案方式を録画します。動画は65秒以上・180秒以内を想定し、実際の長さはffprobeで確認します。

## ファイル構成

| ファイル | 内容 |
| --- | --- |
| sensors.py | 合成信号・特徴量抽出・Random Forestの学習と評価 |
| planner.py | 車体分の余裕を考慮したA*・経路追従・独立した停止制御 |
| simulation.py | PyBulletの物理世界・車輪制御・LiDAR・点検シーケンス |
| assets/rover.urdf | プリミティブ形状で作成したロボット |
| video.py | 実行画面と日本語解説をMP4へ記録 |
| report.py | 保存された実行結果から図とPDFを作成 |
| main.py | 学習・評価・録画の起動 |
| tests.py | 停止、危険区域回避、軌跡連続性などの契約テスト |
| prepare_submission.py | アカウントIDを使った提出用ファイル名の準備 |
| run_colab.ipynb | Colabで同じコードを起動する手順 |
| results/ | 評価値・イベントJSON・軌跡CSV・動画 |

## AIと制御の役割

1. 設備の模擬センサーが1秒分の振動256点と温度16点を生成します。
2. 温度平均・温度標準偏差・振動RMS・尖度・低域/高域のパワー比の6特徴を計算します。
3. Random Forest（120本、最大深さ8、末端の最小データ数3）が3クラスを分類します。
4. 推定確率の最大値が0.70未満、または未知出力なら、その場で停止してRECHECKと記録します。
   現実装は自動再測定を行いません。名称RECHECKは再点検が必要な状態を表します。
5. 過熱では半径1.4 mの危険区域を追加し、車体の外接半径0.32 mと余裕0.06 mを加えて経路探索します。
6. A*は既知地図上の非学習の経路計画です。LiDAR停止層もルールです。
   本作品の学習を使う部分は設備の状態分類です。強化学習やLLM制御は使っていません。

LiDARは121本、3 mの範囲で計測します。前方±約23度に障害物があれば距離0.78 m未満で減速、0.48 m未満で停止します。
距離は車体中心から障害物表面までです。速度上限は0.52 m/sです。
これらは本シミュレーションでの設計値で、実機の安全基準値ではありません。
旋回時には前進停止の条件が適用されない場合があり、現実の全周安全を保証する制御ではありません。

## 比較条件と評価の読み方

- adaptive: AIの過熱判定で危険区域を経路へ反映します。
- fixed: AI分類とLiDARの停止層は同じですが、危険区域をA*へ反映しません。
- 固定経路という名称は「AIによる危険区域の反映を無効にした比較条件」を意味します。
  各目的地へのA*計画自体は実行します。
- 指標: 点検・帰還の成否、車体込みの危険区域侵入、障害物接触、走行距離、完了時間。
- 危険区域侵入は区域追加後、車体中心と設備中心の距離が1.4 + 0.32 m未満かを20 Hzで観測します。
- 接触は床・自分自身以外の障害物との法線力0.05 N超を240 Hzで確認します。
  最小離隔と危険区域侵入の数値は20 Hz標本値です。
- `test` は同じ生成分布の独立した合成データ600件、`stress` はノイズ・温度偏りを変えた合成600件です。
  学習1800件、seed=42。通常テストseed=2026、ストレスseed=2027。
- モデルの推定確率は校正済みの安全確率ではありません。合成データの高精度を実機性能として扱わないでください。
- 未検証: 実機、実測信号、未知地図、SLAM、通信断、センサー偽装、動的環境の網羅的検証。

## 提出前の準備

```bash
python prepare_submission.py --account-id YOUR_OMNICAMPUS_ID
```

詳細はSUBMISSION_GUIDE.mdを参照してください。
氏名・所属・メールは含めず、講座のアカウントIDを使用してください。
学習済みjoblibファイルはPythonコードを実行し得る形式なので、他者から取得した未確認のモデルは読み込まず、
`main.py` で再学習してください。本コードは通常、ローカルで学習したモデルをその場で使います。

## 出典と制作支援

- 課題要件: 配布「最終課題（10_19 改訂版）.pdf」。要件は受講者が配布資料で最終確認します。
- PyBullet公式: https://github.com/bulletphysics/bullet3
- PyBullet Quickstart Guide: https://github.com/bulletphysics/bullet3/blob/master/docs/pybullet_quickstart_guide/PyBulletQuickstartGuide.md.html
- scikit-learn RandomForestClassifier: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html
- scikit-learnモデル評価: https://scikit-learn.org/stable/modules/model_evaluation.html
- IPAexフォント: https://moji.or.jp/ipafont/ （同梱ライセンス参照）

制作支援として生成AIを設計・実装・説明文の作成に使用しています。
評価値はこのコードの実行結果に基づきます。提出者本人の実施作業や実機実験を示すものではありません。
内容を理解して挙動を再確認し、自身で変更・検証した点はレポートに追記してください。
