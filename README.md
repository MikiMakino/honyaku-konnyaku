# Online Meeting Translator (Script Display)

オンライン会議向けの、シンプルな翻訳・通訳スクリプトです。
発話テキストをリアルタイムに翻訳し、字幕のように表示します。

## Features

- 手入力モード (安定)
- マイク入力モード (SpeechRecognition + Google Speech API)
- 画面にスクリプト表示
- スクリプトを `meeting_script.txt` に保存

## Setup

### Miniconda (recommended)

```bash
conda env create -f environment.yml
conda activate meeting-interpreter
```

If your company policy prefers existing envs:

```bash
conda create -n meeting-interpreter python=3.11 -y
conda activate meeting-interpreter
pip install -r requirements.txt
```

### venv (optional)

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

`pyaudio` のインストールに失敗する場合は、手入力モードだけでも利用できます。

## Usage

Run commands after activating your conda environment.

### 1) 手入力モード

```bash
python meeting_interpreter.py --source ja --target en --mode manual
```

- 1行ごとに発話を入力
- `/exit` で終了

### 2) マイク入力モード

```bash
python meeting_interpreter.py --source ja --target en --mode mic --phrase-seconds 7
```

## Main Options

- `--source`: 入力言語コード (例: `ja`, `en`)
- `--target`: 翻訳先言語コード
- `--mode`: `manual` / `mic`
- `--output`: 保存先ファイル (default: `meeting_script.txt`)
- `--display-limit`: 画面に表示する最新件数
- `--phrase-seconds`: マイク入力時の切り出し秒数

## Notes

- 翻訳はインターネット接続が必要です。
- 認識精度はマイク環境に依存します。
- Google API 側の制限で失敗する場合があります。
