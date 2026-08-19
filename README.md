# animal-dash-image-poc

「アニマルダッシュ」企画の画像生成周りを検証するPoCリポジトリ。

紙に描いた動物イラストの写真から、ゲームで使う透過キャラクター画像とステータスJSONを
生成するまでのパイプラインを検証する。

```
撮影画像
  -> 紙の領域検出（四隅検出）
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
venv + pip だけでセットアップできる（Python 3.13以上を想定）。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

以降の `mise run sample` / `mise run preprocess` / `mise run run` は、venvを
activateした状態で以下のコマンドに読み替えればよい（各タスクの中身は `mise.toml` を参照）。

```bash
python scripts/make_sample.py
python -m animal_dash_image_poc.cli preprocess samples/sample_01.jpg -o output/sample_01.png --debug output/debug_sample_01
python -m animal_dash_image_poc.cli run samples/sample_01.jpg -o output/sample_01
```

### Gemini APIキー

`.env.example` を `.env` にコピーして `GEMINI_API_KEY` を設定する
（無料枠での検証を想定 / [Google AI Studio](https://aistudio.google.com/)で発行）。

```bash
cp .env.example .env
```

## 使い方

### 1. 検証用サンプル画像を生成する

実機で撮影した写真がまだ無くても、机の上にA4用紙を斜めに置いて撮影したような
合成画像を生成してパイプラインを試せる。

```bash
mise run sample
# -> samples/sample_01.jpg
```

### 2. OpenCV前処理のみ実行（Gemini不要）

```bash
mise run preprocess
# -> output/sample_01.png （透過PNG）
# -> output/debug_sample_01/ （各ステップの中間画像）
```

`--debug` で指定したディレクトリに、台形補正後・影補正後・マスク・透過後・crop後・
padding後の各画像が出力されるので、しきい値調整の確認に使う。

### 3. 前処理 + Gemini判定を一気通貫で実行

```bash
mise run run
# -> output/sample_01.png
# -> output/sample_01.json （animal_type / features / personality / title / stats）
```

個別のコマンドは以下からも実行できる。

```bash
python -m animal_dash_image_poc.cli preprocess <input.jpg> -o <output.png> [--debug <dir>]
python -m animal_dash_image_poc.cli status <preprocessed.png> [--api-key ...]
python -m animal_dash_image_poc.cli run <input.jpg> -o <output_prefix> [--debug <dir>]
```

## 検証したいこと / 既知の制約

- [ ] 実際に紙とペンで描いた絵を撮影し、`find_paper_corners` / `build_ink_mask` の
      しきい値を実写真に合わせて調整する
- [ ] 台紙の四隅にマーカーを入れるかどうか（現状はエッジ検出ベースの汎用実装）
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
scripts/make_sample.py # 検証用の合成サンプル画像を生成
samples/                # 入力画像置き場（.gitignore対象、.gitkeepのみ管理）
output/                 # 出力画像・JSON置き場（.gitignore対象、.gitkeepのみ管理）
```
