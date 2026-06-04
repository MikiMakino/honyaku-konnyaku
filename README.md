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

### Argosモデルを自動ダウンロードして導入 (PowerShell)

ブラウザで `.argosmodel` を手動取得しなくても、公式インデックスから自動導入できます。

```powershell
python -c "import argostranslate.package as p; p.update_package_index(); pkg=next(x for x in p.get_available_packages() if x.from_code=='ja' and x.to_code=='en'); path=p.download_package(pkg); p.install_from_path(path); print('installed:', path)"
```

導入確認:

```powershell
python -c "import argostranslate.translate as t; langs=t.get_installed_languages(); print([l.code for l in langs]); fr=next(l for l in langs if l.code=='ja'); to=next(l for l in langs if l.code=='en'); tr=fr.get_translation(to); print(tr.translate('テストです'))"
```

## Usage

### 0) 起動前の自動診断 (推奨)

```bash
python scripts/preflight_check.py --source ja --target en --vosk-model models/vosk-model-small-ja-0.22
```

`.argosmodel` ファイルの存在も同時に確認したい場合:

```bash
python scripts/preflight_check.py --source ja --target en --argos-model-file models/translate-ja_en.argosmodel --vosk-model models/vosk-model-small-ja-0.22
```

`Overall: OK` なら起動準備完了です。

### 1) 翻訳モデルをインストールしつつ起動 (初回)

```bash
python meeting_interpreter.py --source ja --target en --mode manual --argos-model-file models/translate-ja_en.argosmodel
```

`Argos model not found` が出る場合は、指定した `.argosmodel` のパスが誤っています。

- 先に配置確認: `dir .\\models`
- 絶対パスで再実行:

```bash
python meeting_interpreter.py --source ja --target en --mode manual --argos-model-file C:\\path\\to\\translate-ja_en.argosmodel
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
- `--source` と `--target` に同じ言語を指定すると、起動時にエラー終了します。
- `--output` で指定した保存先ディレクトリが存在しない場合は自動作成されます。
- micモードを Ctrl+C で停止したとき、最後の未確定発話も可能な限り回収して保存します。

## Troubleshooting: モデル未導入

`Initialization error` でモデル未導入のメッセージが表示されたら、次の手順で解決できます。

1. 対象言語ペアの `.argosmodel` を社内配布または持ち込みファイルで用意
2. 初回のみ `--argos-model-file` を付けて実行
3. 2回目以降は `--argos-model-file` なしで実行

起動前に一括確認する場合:

```bash
python scripts/preflight_check.py --source ja --target en --argos-model-file <path-to-model.argosmodel> --vosk-model <path-to-vosk-model-dir>
```

確認コマンド:

```bash
python -c "import argostranslate.translate as t; print([l.code for l in t.get_installed_languages()])"
```
