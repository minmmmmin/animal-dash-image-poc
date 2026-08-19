# animal-dash-image-poc

「アニマルダッシュ」企画の画像生成周りを検証するPoCリポジトリ。

紙に描いた動物イラストの写真から、ゲームで使う透過キャラクター画像とステータスJSONを
生成するまでのパイプラインを検証する。

```
撮影画像
  -> 台紙の枠（描画エリアの罫線）検出
  -> 台形補正
  -> 明るさ・影補正
  -> 白背景を判定してalpha=0（透過）
  -> 絵の範囲でcrop
  -> 正方形キャンバスにpadding
  -> (Gemini API) 特徴・ステータス判定 -> JSON
```

余白処理・背景透過は OpenCV でローカル処理し、AIには単純な余白除去をさせない方針。
AI（Gemini）には透過済みの画像を見せて、動物の特徴やゲーム用ステータス
（speed / jump / power、称号など）を判定させる。

## セットアップ

### mise を使う場合（推奨）

[mise](https://mise.jdx.dev/) でPython 3.13 / uv のバージョンを固定し、タスクランナーとしても使う。

```bash
mise trust        # mise.toml を信頼する（初回のみ）
mise install      # python, uv を導入
mise run setup    # uv pip install -e . （.venv に依存関係をインストール）
```

### mise を使わない場合

miseはPythonバージョン固定と`mise run ...`タスクの薄いラッパーなので、無くても標準の
venv + pip だけでセットアップできる（Python 3.13以上を想定。[python.org](https://www.python.org/downloads/)からインストール）。

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Windows（PowerShell）**

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

PowerShellでスクリプト実行がブロックされる場合は、一度だけ以下を実行してから
Activate.ps1を叩く（実行ポリシーの変更）。

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Windows（コマンドプロンプト）**

```bat
py -3.13 -m venv .venv
.venv\Scripts\activate.bat
pip install -e .
```

以降の `mise run preprocess` / `mise run run` は、venvをactivateした状態で
以下のコマンドに読み替えればよい（各タスクの中身は `mise.toml` を参照）。
このコマンド自体はOS共通（Windowsでもそのまま同じコマンドでよい）。

```bash
python -m animal_dash_image_poc.cli preprocess samples/dragon.png -o output/dragon.png --debug output/debug_dragon
python -m animal_dash_image_poc.cli run samples/dragon.png -o output/dragon
```

### Gemini APIキー

`.env.example` を `.env` にコピーして `GEMINI_API_KEY` を設定する
（無料枠での検証を想定 / [Google AI Studio](https://aistudio.google.com/)で発行）。

```bash
cp .env.example .env       # macOS / Linux
```

```powershell
copy .env.example .env     # Windows（PowerShell/コマンドプロンプトどちらも可）
```


## テストのやり方

新しく触る人向けの、動作確認の一連の流れ。

### 0. 準備

[セットアップ](#セットアップ)を済ませ、`.env`に`GEMINI_API_KEY`を入れておく
（Gemini判定を試さず前処理だけ確認したい場合はキー不要）。

### 1. サンプル画像を用意する

`samples/` に、実際の台紙の写真 or モックアップ画像を好きなファイル名で置く
（jpg/png どちらも可）。台紙のデザイン自体を確認したいだけなら、絵が描かれていない
テンプレート画像でもOK（背景透過が空になるだけ）。

### 2. まずOpenCV前処理だけ試す（Geminiのキーが無くてもOK・タダで何度でも試せる）

```bash
python -m animal_dash_image_poc.cli preprocess samples/<ファイル名> \
  -o output/<名前>.png \
  --debug output/debug_<名前>
```

確認するもの：

- `output/<名前>.png` … 最終的な透過PNG。輪郭内側の色が消えていないか、
  余計な背景が残っていないか、右向き・全身になっているかを目視確認する
- `output/debug_<名前>/` … 各ステップの中間画像。うまくいかない時はここを見て
  どの段階で崩れているか切り分ける
  - `01_warped.png` … 枠検出＆台形補正の結果（ここが歪んでいたら`find_frame_corners`の問題）
  - `02_illum_corrected.png` … 影・明るさ補正後
  - `03_mask.png` … 背景/インクの二値マスク（白＝インクとして残す部分）
  - `04_rgba.png` … マスクを適用した透過画像（crop前）
  - `05_cropped.png` / `06_padded.png` … crop後 / 正方形padding後（最終出力と同じ）

透過PNGはVSCodeのプレビューや`Read`ツールだと背景が黒っぽく/白っぽく表示されることが
あるが、これは表示側の都合。alphaが本当に0になっているかはコードで確認できる
（不安なら聞いてください）。

### 3. Gemini判定も含めて一気通貫で試す

```bash
python -m animal_dash_image_poc.cli run samples/<ファイル名> -o output/<名前>
```

- `output/<名前>.png` … 透過PNG（手順2と同じ）
- `output/<名前>.json` … `animal_type` / `features` / `personality` / `title` / `stats`
  （speed・jump・powerの合計が30になっているか、内容が不自然でないかを確認）

**注意：`status`サブコマンド単体だとファイルに保存されず標準出力に表示されるだけ。**
JSONを残したい場合は必ず`run`サブコマンドを使う。

Gemini呼び出しは1件あたり10〜20秒程度かかる（サーバー混雑時はもっとかかったり
`503 UNAVAILABLE`で失敗することもある。その場合は少し待って再実行すればよい）。

### 4. 結果がおかしい時にいじる場所

| 症状 | 見る/直すファイル |
|---|---|
| 台形補正が変な形になる・枠が検出できない | `preprocessing.py` の `find_frame_corners`（しきい値`dark_thresh`, `min_area_ratio`） |
| 輪郭の内側の色が透過で消える | `preprocessing.py` の `build_ink_mask`（`gap_close_ratio`を上げると輪郭の隙間をより強く塞げる） |
| 枠線の縁が透過画像に残る | `preprocessing.py` の `strip_frame_border`（`inset_ratio`） |
| Geminiの判定内容・文面を変えたい | `prompts/character_status.md` を直接編集するだけでOK（コード変更不要） |
| ステータスの合計値やレンジを変えたい | `gemini_status.py` の `STAT_TOTAL` とスキーマ |

## 検証したいこと / 既知の制約

- [ ] 実際の台紙（枠付き）を撮影し、`find_frame_corners` / `build_ink_mask` の
      しきい値を実写真に合わせて調整する
- [ ] 台紙の枠線の太さに対して `strip_frame_border` の inset 比率が適切か
- [ ] 黄色など明度の高い色のインクが背景判定されてしまわないか
- [ ] Gemini APIの無料枠のレート制限（4人同時処理を想定した負荷）
- [ ] 生成時間・成功率・失敗パターンの記録方法
- [ ] キャラクター画像生成モデル（ゲームキャラ化）は別途比較検討中、本リポジトリ未対応

## 構成

```
src/animal_dash_image_poc/
  preprocessing.py   # OpenCV: 紙検出・台形補正・影補正・背景透過・crop・padding
  gemini_status.py   # Gemini API: 特徴・ステータスJSON生成
  pipeline.py         # 上記をつなぐオーケストレーション
  cli.py              # CLIエントリポイント
samples/                # 入力画像置き場（.gitignore対象、.gitkeepのみ管理）
output/                 # 出力画像・JSON置き場（.gitignore対象、.gitkeepのみ管理）
```
