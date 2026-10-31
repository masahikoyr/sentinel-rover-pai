# GitHub Public公開手順

## 公開するもの

このZIPはSENTINEL ROVERのソース・設定・検証データ用です。
PDF、MP4、学習済みjoblibは省いています。コードから再生成できます。
ロボットの形状、フォント、フォントのライセンス、評価JSON/CSV、説明用PNGも含みます。

ZIPを展開し、SentinelRoverフォルダの**中のファイルとフォルダ**をアップロードします。
README.mdとmain.pyがリポジトリの最上位に表示される構成にしてください。
ZIPそのもののアップロードでは、個々のソースが閲覧できる状態になりません。

## 1. リポジトリを作成する

https://github.com/new を開き、ログインします。

| 項目 | 設定 |
| --- | --- |
| Owner | 自分の個人アカウント |
| Repository name | sentinel-rover-pai |
| Description | 任意。空欄でも可 |
| Visibility | Public |
| READMEなど初期ファイルの自動作成 | 選択しない。ソース一式に含まれています |

Create repositoryを押します。本作品は新規作成なので、別のリポジトリをforkする必要はありません。

## 2. ソースをアップロードする

1. 空のリポジトリの「uploading an existing file」を押します。
   ファイル一覧がすでにある場合は「Add file」→「Upload files」を選びます。
2. 展開したSentinelRoverフォルダを開きます。
3. その中のファイルとassets・results・buildなどのフォルダを、まとめてドラッグ＆ドロップします。
   フォルダ名の階層を保ち、フォントとライセンスも含めます。
4. 画面の一覧でmain.py、README.md、assets/rover.urdfなどのパスを確認します。
5. Commit messageに `Add Physical AI final project` と入力します。
6. 初回アップロードをmainへ保存します。画面の「Commit changes」を押します。
   新しいブランチへの変更として「Propose changes」が表示される場合は、その後Pull Requestを作り、
   自分のリポジトリのmainへMergeしてください。

## 3. 公開状態と提出URLを確認する

- リポジトリ名の横がPublicであることを確認します。
- README.mdがトップページに表示されることを確認します。
- main.py、sensors.py、simulation.py、assets/rover.urdfが開けることを確認します。
- シークレットウィンドウなど、ログインしていない状態でも閲覧できることを確認します。
- 提出するURLはリポジトリのトップページです。

例: `https://github.com/YOUR_USERNAME/sentinel-rover-pai`

URLのYOUR_USERNAMEは実際のGitHubユーザー名へ置き換えてください。
GitHubのソース公開、YouTubeの動画公開、omnicampusの提出はそれぞれ別の操作です。

## ソースの役割

| ファイル | 内容 |
| --- | --- |
| main.py | 学習・評価・録画の起動 |
| sensors.py | 合成データ生成、6特徴量、Random Forestの学習・推論 |
| planner.py | A*、車体サイズを考慮した回避、経路追従、停止制御 |
| simulation.py | PyBulletの物理世界、モーター、LiDAR、点検シーケンス |
| assets/rover.urdf | 差動二輪ロボットの形状・車輪・関節 |
| video.py | 実行画面と日本語解説のMP4記録 |
| report.py | 評価ログから図とPDFを生成 |
| tests.py | 停止優先、区域回避、軌跡などのテスト |
| requirements.txt | Pythonライブラリの検証時バージョン |
| run_colab.ipynb | Colab実行の手順。Colab UI上では未検証 |
| results/ | 実行済みの評価JSON、軌跡CSV、画面PNG |
| assets/fonts/ | 日本語フォントと再配布に必要なライセンス |

## ソースから再生成する場合

Python 3.11または3.12、FFmpegを用意し、READMEの環境構築手順を実施します。
READMEと同じフォルダで以下を実行します。

```bash
python -m pip install -r requirements.txt
python main.py --evaluate --video
python tests.py
python report.py
```

AIを使用する部分は合成温度・振動データの状態分類です。
A*やLiDAR停止は非学習の制御で、シミュレーションの地図・自己位置は既知です。
生成AIを制作支援として使用した旨はREADMEとレポートに記載しています。

## 公式資料

- https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository
- https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
