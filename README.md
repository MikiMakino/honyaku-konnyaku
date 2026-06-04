# Online Meeting Translator (Offline / Script Display)

オンライン会議向けの、API不使用の翻訳・通訳スクリプトです。
発話をローカルで翻訳し、字幕のようにターミナル表示します。

## Features

- API不使用 (外部翻訳APIなし)
- 手入力モード (安定)
- マイク入力モード (Vosk オフライン音声認識)
- 画面にスクリプト表示
- スクリプトを `meeting_script.txt` に保存

## Setup (Miniconda)

```bash
conda env create -f environment.yml
conda activate meeting-interpreter
```

## Model Preparation (Offline)

このアプリはローカルモデルを使います。

- 翻訳モデル: Argos Translate の `.argosmodel`
- 音声認識モデル: Vosk のモデルフォルダ

例として、以下のように配置します。

- `models/translate-ja_en.argosmodel`
- `models/vosk-model-small-ja-0.22/`

## Usage

### 1) 翻訳モデルをインストールしつつ起動 (初回)

```bash
python meeting_interpreter.py --source ja --target en --mode manual --argos-model-file models/translate-ja_en.argosmodel
```

### 2) 2回目以降の手入力モード

```bash
python meeting_interpreter.py --source ja --target en --mode manual
```

- 1行ごとに発話を入力
- `/exit` で終了

### 3) マイク入力モード (完全オフライン)

```bash
python meeting_interpreter.py --source ja --target en --mode mic --vosk-model models/vosk-model-small-ja-0.22
```

## Main Options

- `--source`: 入力言語コード (例: `ja`, `en`)
- `--target`: 翻訳先言語コード
- `--mode`: `manual` / `mic`
- `--output`: 保存先ファイル (default: `meeting_script.txt`)
- `--display-limit`: 画面に表示する最新件数
- `--argos-model-file`: 初回インストール用 `.argosmodel` パス
- `--vosk-model`: micモード用 Vosk モデルフォルダ
- `--sample-rate`: マイクのサンプリングレート (default: `16000`)

## Notes

- 翻訳APIやクラウド音声APIは使用しません。
- 初回はローカルモデルの準備が必要です。
- 認識精度はマイク環境とモデル品質に依存します。
