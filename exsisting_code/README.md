# XSDカバレッジ分析ツール

階層構造を考慮した、XSDスキーマに対するXMLファイルのカバレッジを計測するツールです。

## 概要

このツールは、XSDスキーマで定義されたすべての要素と属性のパスを抽出し、複数のXMLファイルがそれらをどの程度カバーしているかを計測します。

### 主な特徴

1. **階層構造を考慮**
   - 同じ要素名でも、異なる階層に現れる場合は別の要素として扱います
   - 例：`/RootDocument/Header/Name` と `/RootDocument/Body/Item/Name` は別の要素パスとして認識

2. **属性も階層を考慮**
   - 属性も、親要素の階層に応じて別々にカウントされます
   - 例：`/RootDocument/Body/Item@Status` と `/RootDocument/Body/Category@Status` は別の属性パスとして認識

3. **再帰的構造のサポート**
   - `SubItem`のような再帰的な要素も、深さごとに別のパスとして認識します
   - 例：
     - `/RootDocument/Body/Item/SubItem`
     - `/RootDocument/Body/Item/SubItem/SubItem`
     - `/RootDocument/Body/Item/SubItem/SubItem/SubItem`

## ファイル構成

```
├── extended_schema.xsd    # 拡張されたサンプルXSDファイル
├── sample1.xml            # サンプルXML（低カバレッジ）
├── sample2.xml            # サンプルXML（中カバレッジ）
├── sample3.xml            # サンプルXML（高カバレッジ、ネスト構造含む）
├── xsd_coverage.py        # カバレッジ計測プログラム
├── coverage_report.txt    # 生成されるレポートファイル
└── README.md              # このファイル
```

## 使用方法

### 基本的な使い方

```bash
python xsd_coverage.py <XSDファイル> <XMLファイル1> [XMLファイル2] ...
```

### 例1: 単一のXMLファイルを解析

```bash
python xsd_coverage.py extended_schema.xsd sample1.xml
```

### 例2: 複数のXMLファイルを解析

```bash
python xsd_coverage.py extended_schema.xsd sample1.xml sample2.xml sample3.xml
```

### 例3: ワイルドカードを使用

```bash
python xsd_coverage.py extended_schema.xsd sample*.xml
```

## レポートの見方

実行すると、以下の情報を含むレポートが生成されます：

### 1. 要素カバレッジ（改善版）

```
【要素カバレッジ】
  XSDで定義された要素パス数: 56
  ├─ XMLで使用されている数: 20
  └─ XMLで未使用の数: 36
  
  XMLに存在する要素パス総数: 20
  ├─ XSDで定義済み: 20
  └─ XSDで未定義: 0
  
  カバレッジ率: 35.71%
  （定義された56個のうち20個が使用されている）
```

**重要な指標**:
- **カバレッジ率**: 定義されたパスのうち、テストでカバーされている割合
- **XSDで未定義**: これが0でない場合、XMLがXSDに準拠していない可能性あり

### 2. 属性カバレッジ

要素と同様の形式で属性のカバレッジを表示します。

### 3. 総合カバレッジ

要素と属性を合わせた全体のカバレッジを表示します。

### 4. 未使用のパス一覧

XSDで定義されているが、XMLファイル群で使用されていない要素・属性パスのリスト。
これらを含むテストケースを追加することでカバレッジを向上できます。

### 5. 警告: 未定義のパス

**重要**: XMLに存在するが、XSDで定義されていないパスが表示されます。
これが表示される場合、以下のいずれかの問題があります：
- XMLがXSDに準拠していない
- XSDの解析に問題がある
- 名前空間の不一致

### 6. 使用されているパス一覧

XMLファイル群で実際に使用されている要素・属性パスのリスト。
- ✓マークは定義されているパス
- ✗マークは定義されていないパス（問題あり）

**詳細な解説は [COVERAGE_GUIDE.md](COVERAGE_GUIDE.md) を参照してください。**

## 拡張されたXSDの特徴

`extended_schema.xsd`は、階層構造の課題を表現するために以下の特徴を持っています：

1. **同じ要素名が異なる階層に登場**
   - `Name`要素：Header、Metadata、Item、Categoryなど複数の場所に登場
   - `Description`要素：複数の異なる階層に登場
   - `Item`要素：BodyとCategoryの下に登場

2. **同じ属性名が異なる要素に付与**
   - `Status`属性：RootDocument、Header、Body、Item、Categoryなど
   - `Version`属性：RootDocument、Metadata、Footerなど

3. **再帰的なネスト構造**
   - `Item`型は`SubItem`要素を持ち、`SubItem`も`Item`型なので無限にネストできる
   - プログラムは最大深度5までのネストをサポート

4. **複雑な階層構造**
   - RootDocument → Header/Body/Footer
   - Body → Item/Category
   - Item → Name/Description/Details/SubItem
   - Details → Note/Tag

## カバレッジの計測例

### サンプル1 (sample1.xml) - 低カバレッジ
最小限の要素のみを使用した例

### サンプル2 (sample2.xml) - 中カバレッジ
より多くの要素と属性を使用し、MetadataやDetailsなども含む例

### サンプル3 (sample3.xml) - 高カバレッジ
ネスト構造（SubItem）を含む、より包括的な例

### 3つのサンプルを組み合わせた結果
```
要素カバレッジ: 35.71% (20/56パス)
属性カバレッジ: 40.00% (20/50パス)
総合カバレッジ: 37.74% (40/106パス)
```

## プログラムの設計

### SchemaAnalyzerクラス
- XSDスキーマを解析
- すべての要素と属性のパスを抽出
- 再帰的な構造にも対応（無限ループ防止機能付き）

### XMLCoverageAnalyzerクラス
- XMLファイル群を解析
- 実際に使用されている要素と属性のパスを抽出

### CoverageReporterクラス
- カバレッジを計算
- 詳細なレポートを生成

## 要件

- Python 3.6以上
- lxml ライブラリ

### lxmlのインストール

```bash
pip install lxml --break-system-packages
```

## 制限事項

1. 再帰的な構造は最大深度5までサポート
2. 名前空間は自動的に処理されますが、複雑な名前空間の組み合わせでは予期しない動作をする可能性があります
3. choice、all、group などの複雑なXSD構造は基本的にサポートしていますが、一部制限があります

## カスタマイズ

### 最大再帰深度の変更

プログラム内の`max_recursion_depth`パラメータを変更することで、再帰的な構造の解析深度を調整できます：

```python
schema_analyzer.analyze(max_recursion_depth=10)  # デフォルトは5
```

## トラブルシューティング

### エラー: "Invalid input tag"
- XMLファイルの構造がXSDと一致していない可能性があります
- XMLファイルの構文エラーを確認してください

### カバレッジが0%になる
- XSDとXMLの名前空間が一致していることを確認してください
- パスの抽出が正しく行われているか、デバッグ出力を確認してください

## ライセンス

このツールは教育・研究目的で自由に使用できます。

## 作成者

Claude (Anthropic)
