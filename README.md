# XSD Coverage Measurement and XML Generation Tools

XSDスキーマのカバレッジを測定し、高カバレッジのXMLファイルを生成するためのツールセット。

## 概要

このプロジェクトは、XMLスキーマ定義（XSD）に対するXMLファイルのカバレッジを測定し、最適なテストデータを生成するための3つの主要ツールを提供します：

1. **XSDカバレッジ測定ツール** - XSDで定義されたパスに対するXMLファイルのカバレッジを分析
2. **貪欲法XML生成ツール** - Set-Cover問題として高カバレッジXMLを生成
3. **SMTソルバーベースXML生成ツール** - Z3ソルバーを用いて理論的に最適なXMLを生成

## 主要機能

### カバレッジ測定の特徴

- **階層構造を考慮したパスカウント**: 同じ要素名でも異なる階層パスを別々にカウント
- **要素パスと属性パスの個別測定**: それぞれ独立してカバレッジを計算
- **再帰構造のサポート**: `max-depth`パラメータで制御可能
- **詳細なレポート出力**: 未使用パスや未定義パスを明確に表示

### XML生成の特徴

| 特徴 | 貪欲法 | SMTソルバー |
|------|--------|-------------|
| カバレッジ | 55-89% | 99-100% |
| 生成速度 | 1-2秒 | 1-5秒 |
| 最適性保証 | なし | あり |
| ファイル数 | 1 | 1 |

## インストール

### 前提条件

- Python 3.8以上
- pip

### 依存パッケージのインストール

```bash
pip install lxml z3-solver
```

## ディレクトリ構造

```
xsdcoverage/
├── exsisting_code/
│   ├── xsd_coverage.py              # カバレッジ測定ツール
│   ├── xml_generator.py             # 貪欲法XML生成ツール
│   ├── xml_generator_smt.py         # SMTソルバーベースXML生成ツール
│   └── COUNTING_METHODOLOGY.md      # カバレッジ計測方法の詳細説明
├── test/
│   ├── sample/
│   │   └── extended_schema.xsd      # サンプルスキーマ（236パス）
│   └── ISO/
│       └── IEC62474_Schema_*.xsd    # ISO標準スキーマ（3491パス）
├── generated/
│   ├── greedy_sample/               # 貪欲法で生成されたXML（Sample）
│   ├── greedy_iso/                  # 貪欲法で生成されたXML（ISO）
│   ├── smt_sample/                  # SMTで生成されたXML（Sample）
│   ├── smt_iso/                     # SMTで生成されたXML（ISO）
│   ├── COMPARISON_REPORT.md         # 貪欲法の比較レポート
│   └── SMT_COMPARISON_REPORT.md     # SMTと貪欲法の比較レポート
├── spec/
│   └── xml_generation.md            # XML生成アルゴリズムの仕様
└── README.md                        # 本ファイル
```

## 使用方法

### 1. XSDカバレッジ測定

XSDスキーマに対するXMLファイルのカバレッジを測定します。

```bash
python3 exsisting_code/xsd_coverage.py <XSDファイル> <XMLファイル>... [オプション]
```

#### オプション

- `--max-depth N`: 再帰構造の最大深度（デフォルト: 10）

#### 実行例

```bash
# 単一XMLファイルのカバレッジを測定
python3 exsisting_code/xsd_coverage.py test/sample/extended_schema.xsd sample.xml

# 複数XMLファイルの合計カバレッジを測定
python3 exsisting_code/xsd_coverage.py test/sample/extended_schema.xsd data/*.xml --max-depth 10
```

#### 出力例

```
================================================================================
XSDカバレッジレポート（階層構造考慮版）
================================================================================

【要素カバレッジ】
  XSDで定義された要素パス数: 116
  ├─ XMLで使用されている数: 116
  └─ XMLで未使用の数: 0
  カバレッジ率: 100.00%

【属性カバレッジ】
  XSDで定義された属性パス数: 120
  ├─ XMLで使用されている数: 120
  └─ XMLで未使用の数: 0
  カバレッジ率: 100.00%

【総合カバレッジ】
  カバレッジ率: 100.00% (236/236)
```

### 2. 貪欲法XML生成

Set-Cover問題として高カバレッジXMLを生成します。

```bash
python3 exsisting_code/xml_generator.py <XSDファイル> -o <出力ディレクトリ> [オプション]
```

#### オプション

- `-o, --output DIR`: 出力ディレクトリ（必須）
- `--max-depth N`: XSD解析の最大深度（デフォルト: 10）
- `--max-gen-depth N`: XML生成の最大深度（デフォルト: 10）
- `--target-coverage RATE`: 目標カバレッジ率（0.0-1.0、デフォルト: 0.90）
- `--max-files N`: 最大生成ファイル数（デフォルト: 10）
- `--namespace PREFIX=URI`: 名前空間の追加

#### 実行例

```bash
# Sample Schemaに対してXMLを生成
python3 exsisting_code/xml_generator.py test/sample/extended_schema.xsd \
    -o generated/greedy_sample \
    --max-depth 10 \
    --max-gen-depth 10 \
    --target-coverage 0.95 \
    --namespace "http://example.com/MySchema"

# ISO Schemaに対してXMLを生成
python3 exsisting_code/xml_generator.py test/ISO/IEC62474_Schema_X8.21-120240831.xsd \
    -o generated/greedy_iso \
    --max-depth 10 \
    --max-gen-depth 10 \
    --target-coverage 0.95
```

#### 性能

- **Sample Schema**: 88.98% カバレッジ、1ファイル、~1秒
- **ISO Schema**: 55.83% カバレッジ、1ファイル、~2秒

### 3. SMTソルバーベースXML生成（推奨）

Z3 SMTソルバーを用いて理論的に最適なXMLを生成します。

```bash
python3 exsisting_code/xml_generator_smt.py <XSDファイル> -o <出力ディレクトリ> [オプション]
```

#### オプション

- `-o, --output DIR`: 出力ディレクトリ（必須）
- `--max-depth N`: XSD解析の最大深度（デフォルト: 10）
- `--target-coverage RATE`: 目標カバレッジ率（0.0-1.0、デフォルト: 0.95）
- `--timeout MS`: Z3ソルバーのタイムアウト（ミリ秒、デフォルト: 60000）
- `--namespace PREFIX=URI`: 名前空間の追加

#### 実行例

```bash
# Sample Schemaに対してXMLを生成
python3 exsisting_code/xml_generator_smt.py test/sample/extended_schema.xsd \
    -o generated/smt_sample \
    --max-depth 10 \
    --target-coverage 0.95 \
    --timeout 60000 \
    --namespace "http://example.com/MySchema"

# ISO Schemaに対してXMLを生成
python3 exsisting_code/xml_generator_smt.py test/ISO/IEC62474_Schema_X8.21-120240831.xsd \
    -o generated/smt_iso \
    --max-depth 10 \
    --target-coverage 0.95 \
    --timeout 120000
```

#### 性能

- **Sample Schema**: 100.00% カバレッジ、1ファイル、~1秒
- **ISO Schema**: 99.80% カバレッジ、1ファイル、~5秒

## 実験結果

### Sample Schema (236パス: 116要素 + 120属性)

| 手法 | ファイル数 | カバレッジ | 生成時間 |
|------|------------|------------|----------|
| 既存XML | 3 | 24.58% | - |
| 貪欲法 | 1 | 88.98% | ~1秒 |
| **SMT** | **1** | **100.00%** | **~1秒** |

### ISO IEC62474 Schema (3491パス: 907要素 + 2584属性)

| 手法 | ファイル数 | カバレッジ | 生成時間 |
|------|------------|------------|----------|
| 既存XML | 22 | 6.19% | - |
| 貪欲法 | 1 | 55.83% | ~2秒 |
| **SMT** | **1** | **99.80%** | **~5秒** |

**結論**: SMTソルバーベースのアプローチが圧倒的に優れています。

## アルゴリズムの詳細

### カバレッジ測定アルゴリズム

1. XSDスキーマを解析し、すべての要素パスと属性パスを列挙
2. 再帰構造は`max-depth`まで展開
3. XMLファイルを解析し、実際に使用されているパスを収集
4. 定義済みパスと使用済みパスを比較してカバレッジを計算

詳細は `exsisting_code/COUNTING_METHODOLOGY.md` を参照してください。

### 貪欲法XML生成アルゴリズム

1. XSDから様々な深度・バリエーションのXMLスニペットを生成
   - 各深度で生成
   - オプション要素を含む/含まないバリエーション
   - choice構造の各選択肢
2. 各スニペットがカバーするパスを計算
3. 貪欲的に、最も多くの未カバーパスをカバーするスニペットを選択
4. 目標カバレッジまたは最大ファイル数に到達するまで繰り返し

### SMTソルバーベースXML生成アルゴリズム

1. **変数定義**: 全パスに対してZ3ブール変数を割り当て
2. **制約構築**: XSDの制約をZ3 SMT制約に変換
   - **階層制約**: `child → parent` (子が存在すれば親も存在)
   - **必須要素制約**: `parent → required_child` (親が存在すれば必須子も存在)
   - **choice制約**: 親が存在すれば選択肢のうち正確に1つが存在
   - **深度制約**: 指定深度を超えないように制限
3. **最適化**: Z3 Optimizeソルバーでカバレッジを最大化
4. **XML構築**: Z3が返すモデル（変数の真偽値割り当て）からXMLツリーを構築

詳細は `generated/SMT_COMPARISON_REPORT.md` を参照してください。

## ユースケース別推奨

### 小〜中規模スキーマ（< 500パス）
**推奨**: SMTソルバー
- 高速かつ完全カバレッジを達成

### 大規模スキーマ（500〜2000パス）
**推奨**: SMTソルバー（タイムアウト設定に注意）
- 代替: 貪欲法（速度優先の場合）

### 超大規模スキーマ（> 2000パス）
**推奨**: SMTソルバー
- 本実験ではISO（3491パス）でも5秒で99.80%達成

### 時間制約が厳しい場合
**推奨**: 貪欲法
- 1〜2秒で合理的なカバレッジを提供

## トラブルシューティング

### Z3がインストールできない

```bash
# 代替インストール方法
pip3 install --upgrade z3-solver
```

### メモリ不足エラー

- `--max-depth`を減らす（例: 8や6に）
- タイムアウトを短くする

### カバレッジが低い

**貪欲法の場合**:
- `--max-gen-depth`を増やす
- `--max-files`を増やす

**SMTソルバーの場合**:
- タイムアウトを増やす
- `--max-depth`を調整

### 名前空間エラー

XSDで名前空間が定義されている場合、`--namespace`オプションで明示的に指定してください。

```bash
--namespace "http://example.com/MySchema"
```

## 技術スタック

- **Python**: 3.8+
- **lxml**: XSD/XMLパーシング
- **Z3-solver**: SMT制約充足ソルバー

## 関連ドキュメント

- `exsisting_code/COUNTING_METHODOLOGY.md` - カバレッジ計測方法の詳細
- `spec/xml_generation.md` - XML生成アルゴリズムの仕様
- `generated/COMPARISON_REPORT.md` - 貪欲法と既存XMLの比較
- `generated/SMT_COMPARISON_REPORT.md` - SMTソルバーと貪欲法の比較

## ライセンス

本プロジェクトは教育・研究目的で作成されました。

## 作成者

Claude Code (Anthropic) - 2025-10-01

## 謝辞

- Z3 SMTソルバー開発チーム
- lxmlライブラリ開発チーム
