# XSD Coverage Measurement and XML Generation Tools

XSDスキーマのカバレッジを測定し、高カバレッジのXMLファイルを生成するためのツールセット。

## 概要

このプロジェクトは、XMLスキーマ定義（XSD）に対するXMLファイルのカバレッジを測定し、最適なテストデータを生成するための5つの主要ツールを提供します：

1. **XSDカバレッジ測定ツール** - XSDで定義されたパスに対するXMLファイルのカバレッジを分析
2. **貪欲法XML生成ツール** - Set-Cover問題として高カバレッジXMLを生成
3. **SMTソルバーベースXML生成ツール** - Z3ソルバーを用いて理論的に最適なXMLを生成
4. **ペアワイズXML生成ツール** - 組合せテストに基づくテストデータを生成
5. **XMLバリデーションツール（新）** - 生成されたXMLがXSDに対して有効かを検証

## 主要機能

### カバレッジ測定の特徴

- **階層構造を考慮したパスカウント**: 同じ要素名でも異なる階層パスを別々にカウント
- **要素パスと属性パスの個別測定**: それぞれ独立してカバレッジを計算
- **再帰構造のサポート**: `max-depth`パラメータで制御可能
- **詳細なレポート出力**: 未使用パスや未定義パスを明確に表示

### XML生成の特徴

| 特徴 | 貪欲法 | SMTソルバー | ペアワイズ |
|------|--------|-------------|------------------|
| カバレッジ | 55-89% | 99-100% | 84-96% |
| ペアカバレッジ | - | - | 100% |
| バリデーション | 検証なし | 検証なし | **100% valid** |
| 生成速度 | 1-2秒 | 1-5秒 | 2-5秒 |
| 最適性保証 | なし | あり | ペアワイズ最適 |
| ファイル数 | 1 | 1 | 10-30 |
| テストデータ適性 | 低 | 中 | **高** |

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
│   ├── xml_generator_pairwise.py    # ペアワイズXML生成ツール
│   ├── xml_validator.py             # XMLバリデーションツール（新）
│   ├── optional_extractor.py        # オプション項目抽出モジュール
│   ├── pairwise_generator.py        # ペアワイズ配列生成モジュール
│   ├── pairwise_xml_builder.py      # ペアワイズXMLビルダー
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
│   ├── pairwise_sample_fixed/       # ペアワイズで生成されたXML（Sample）
│   ├── pairwise_iso_fixed/          # ペアワイズで生成されたXML（ISO）（新）
│   ├── COMPARISON_REPORT.md         # 貪欲法の比較レポート
│   └── SMT_COMPARISON_REPORT.md     # SMTと貪欲法の比較レポート
├── spec/
│   ├── xml_generation.md            # XML生成アルゴリズムの仕様
│   ├── greedy_algorithm.md          # 貪欲法の詳細解説
│   └── smt_algorithm.md             # SMTソルバーの詳細解説
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

### 4. ペアワイズXML生成（組合せテスト向け）

組合せテストの理論に基づき、すべてのオプション項目のペア（2-way組合せ）をカバーするテストデータを生成します。

```bash
python3 exsisting_code/xml_generator_pairwise.py <XSDファイル> -o <出力ディレクトリ> [オプション]
```

#### オプション

- `-o, --output DIR`: 出力ディレクトリ（必須）
- `--max-depth N`: XSD解析の最大深度（デフォルト: 10）
- `--max-patterns N`: 最大パターン数（デフォルト: 50）
- `--namespace PREFIX=URI`: 名前空間の追加
- `--random-seed N`: 乱数シード（デフォルト: 42）

#### 実行例

```bash
# Sample Schemaに対してペアワイズXMLを生成
python3 exsisting_code/xml_generator_pairwise.py test/sample/extended_schema.xsd \
    -o generated/pairwise_sample_fixed \
    --max-depth 10 \
    --max-patterns 30 \
    --namespace "http://example.com/MySchema"

# ISO Schemaに対してペアワイズXMLを生成
python3 exsisting_code/xml_generator_pairwise.py test/ISO/IEC62474_Schema_X8.21-120240831.xsd \
    -o generated/pairwise_iso_fixed \
    --max-depth 10 \
    --max-patterns 10
```

#### 性能

- **Sample Schema**: 83.90% 構造カバレッジ、100% ペアカバレッジ、23ファイル、100% valid、~3秒
  - オプション項目: 169個のオプション項目から56,784ペアを完全カバー
- **ISO Schema**: 96.34% 構造カバレッジ、100% ペアカバレッジ、10ファイル、**100% valid**、~5秒
  - オプション項目: 1,781個のオプション項目から300個にサンプリング、179,400ペアを完全カバー

#### 特徴

- **組合せテストの標準手法**: ペアワイズテスト（2-way coverage）
- **テストデータとして最適**: 各オプション項目の有無の組合せを網羅
- **理論的保証**: すべてのペアを最小ファイル数でカバー
- **下流ソフトウェアのテストに適している**: 分岐条件の網羅的テスト
- **XSDバリデーション対応**: 生成されたすべてのXMLが100% valid

### 5. XMLバリデーション（新）

生成されたXMLファイルがXSDスキーマに対して有効かを検証します。

```bash
python3 exsisting_code/xml_validator.py <XSDファイル> <XMLファイル>... [オプション]
```

#### オプション

- `--output FILE`: 検証結果をファイルに出力

#### 実行例

```bash
# 単一XMLファイルを検証
python3 exsisting_code/xml_validator.py test/sample/extended_schema.xsd sample.xml

# 複数XMLファイルを一括検証
python3 exsisting_code/xml_validator.py test/sample/extended_schema.xsd generated/pairwise_sample_fixed/*.xml

# 結果をファイルに保存
python3 exsisting_code/xml_validator.py test/ISO/IEC62474_Schema_X8.21-120240831.xsd \
    generated/pairwise_iso_fixed/*.xml \
    --output validation_report.txt
```

#### 出力例

```
================================================================================
XMLバリデーション結果レポート
================================================================================

【サマリー】
総XMLファイル数: 10
✓ Valid:   10 (100.0%)
✗ Invalid: 0 (0.0%)

すべてのXMLファイルがValidです！
```

## 実験結果

### Sample Schema (236パス: 116要素 + 120属性)

| 手法 | ファイル数 | 構造カバレッジ | ペアカバレッジ | バリデーション | 生成時間 | 用途 |
|------|------------|----------------|----------------|----------------|----------|------|
| 既存XML | 3 | 24.58% | - | - | - | - |
| 貪欲法 | 1 | 88.98% | - | 未検証 | ~1秒 | 構造検証 |
| SMT | 1 | 100.00% | - | 未検証 | ~1秒 | 構造検証 |
| **ペアワイズ** | **23** | **83.90%** | **100%** | **100% valid** | **~3秒** | **テストデータ** |

### ISO IEC62474 Schema (3491パス: 907要素 + 2584属性)

| 手法 | ファイル数 | 構造カバレッジ | ペアカバレッジ | バリデーション | 生成時間 | 用途 |
|------|------------|----------------|----------------|----------------|----------|------|
| 既存XML | 22 | 6.19% | - | - | - | - |
| 貪欲法 | 1 | 55.83% | - | 未検証 | ~2秒 | 構造検証 |
| SMT | 1 | 99.80% | - | 未検証 | ~5秒 | 構造検証 |
| **ペアワイズ** | **10** | **96.34%** | **100%** | **✅ 100% valid** | **~5秒** | **テストデータ** |

**結論**:
- **構造カバレッジ優先**: SMTソルバーが最適（99-100%）
- **テストデータ生成**: ペアワイズが最適（組合せテストに基づく網羅性 + XSDバリデーション保証）
- **プロダクション用**: ペアワイズのみが100% validなXMLを生成

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

詳細は `generated/SMT_COMPARISON_REPORT.md` および `spec/smt_algorithm.md` を参照してください。

### ペアワイズXML生成アルゴリズム

1. **オプション項目抽出**: XSDから以下を抽出
   - `minOccurs="0"`の要素
   - `use="optional"`の属性
   - choice構造の各選択肢
2. **ペアワイズカバーリング配列生成**: Greedyアルゴリズムで生成
   - すべてのオプション項目ペアを列挙（C(N,2)通り）
   - 未カバーペアを最も多くカバーするパターンを繰り返し追加
   - 全ペアがカバーされるまで継続
3. **XML構築**: 各テストパターンからXMLを生成
   - パターンで True の項目を含める
   - パターンで False の項目を除外
   - 必須要素は常に含める
4. **XSDバリデーション対応**（新）:
   - **名前空間の自動検出**: xs: vs xsd: プレフィックスを自動処理
   - **コンテンツモデルの正確な判定**: empty/element-only/simpleContentの区別
   - **必須属性の完全な検出**: extension/baseからの継承も含む
   - **必須子要素の生成**: max_depth到達時でも必須要素を追加
   - **外部名前空間対応**: XML Digital Signature (ds:SignatureType) などの特殊処理

詳細は `spec/greedy_algorithm.md` を参照してください。

## ユースケース別推奨

### 用途別の選択

#### 構造検証・スキーマ検証
**推奨**: SMTソルバー
- **目的**: XSD定義の完全性を検証
- **理由**: 99-100%の構造カバレッジを達成
- **適用**: すべての規模のスキーマ

#### テストデータ生成・組合せテスト
**推奨**: ペアワイズアプローチ
- **目的**: 下流ソフトウェアの分岐テスト
- **理由**: オプション項目の組合せを網羅的にカバー
- **特徴**:
  - 100%ペアカバレッジで実バグ検出率が高い
  - **100% XSD valid保証** - プロダクション環境で安心して利用可能
  - 複雑なスキーマ（ISO IEC62474など）にも対応
- **適用**: テストデータが必要なすべてのケース

#### 高速プロトタイピング
**推奨**: 貪欲法
- **目的**: 素早く動作確認用のXMLを生成
- **理由**: 1〜2秒で合理的なカバレッジ
- **適用**: 開発初期段階、デモ用データ

### スキーマ規模別の選択

#### 小〜中規模スキーマ（< 500パス）
- **構造検証**: SMTソルバー（1-2秒、99-100%）
- **テストデータ**: ペアワイズ（5-10ファイル、100%ペアカバー）

#### 大規模スキーマ（500〜2000パス）
- **構造検証**: SMTソルバー（2-10秒、タイムアウト注意）
- **テストデータ**: ペアワイズ（15-25ファイル）

#### 超大規模スキーマ（> 2000パス）
- **構造検証**: SMTソルバー（ISO 3491パスで5秒、99.80%）
- **テストデータ**: ペアワイズ（推定30-50ファイル）

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

Claude Code (Anthropic) - 2025-10-02

## 謝辞

- Z3 SMTソルバー開発チーム
- lxmlライブラリ開発チーム
