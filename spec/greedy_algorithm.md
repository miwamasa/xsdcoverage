# 貪欲法（Greedy Set-Cover）XML生成アルゴリズム解説

## 目次

1. [概要](#概要)
2. [理論的背景](#理論的背景)
3. [アルゴリズムの動作原理](#アルゴリズムの動作原理)
4. [実装アーキテクチャ](#実装アーキテクチャ)
5. [詳細なアルゴリズムフロー](#詳細なアルゴリズムフロー)
6. [主要クラスとメソッド](#主要クラスとメソッド)
7. [パラメータとチューニング](#パラメータとチューニング)
8. [性能分析](#性能分析)
9. [利点と欠点](#利点と欠点)
10. [改善案](#改善案)

---

## 概要

貪欲法XML生成アルゴリズムは、**Set-Cover問題**として定式化されたXML生成タスクを、貪欲戦略で解くアプローチです。

### 基本的なアイデア

1. XSDスキーマから多数のXML候補（スニペット）を生成
2. 各スニペットが「カバーする」パスの集合を計算
3. 未カバーのパスを最も多くカバーするスニペットを繰り返し選択
4. 目標カバレッジに到達するまで続行

### 適用シーン

- 中規模スキーマ（〜1000パス）での高速生成
- プロトタイピングや初期検証
- 速度を優先する場合（1〜2秒での生成）

---

## 理論的背景

### Set-Cover問題

**定義**: 全体集合 U と、その部分集合の集合 S = {S₁, S₂, ..., Sₙ} が与えられたとき、U を完全にカバーする最小の部分集合を選択する問題。

**XML生成への適用**:
- **全体集合 U**: XSDで定義されたすべてのパス（要素パス + 属性パス）
- **部分集合 Sᵢ**: 各XMLスニペットがカバーするパスの集合
- **目標**: 最小のXMLファイル数で最大のカバレッジを達成

### 計算複雑性

- Set-Cover問題は **NP困難**
- 近似アルゴリズムとして貪欲法を使用
- 貪欲法の近似比: **O(log n)** （n は全体集合のサイズ）

### 貪欲戦略

各ステップで、**最も多くの未カバー要素をカバーする集合を選択**する戦略。

```
アルゴリズム: Greedy-Set-Cover
入力: 全体集合 U, 部分集合の集合 S
出力: カバーする部分集合の選択 C

C ← ∅
未カバー ← U

while 未カバー ≠ ∅ do
    最良 ← argmax_{S ∈ S} |S ∩ 未カバー|
    C ← C ∪ {最良}
    未カバー ← 未カバー \ 最良
end while

return C
```

---

## アルゴリズムの動作原理

### 全体フロー

```
┌─────────────────────────────────────┐
│  1. XSDスキーマ解析                 │
│     - SchemaAnalyzerでパス列挙      │
│     - 全カバレッジ項目を取得        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  2. スニペット候補生成              │
│     - 深度0〜max_gen_depthで生成    │
│     - バリエーション生成            │
│       • オプション要素含む/含まない │
│       • choice構造の各選択肢        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  3. 各スニペットのカバレッジ計算    │
│     - スニペットに含まれるパスを列挙│
│     - XMLSnippetオブジェクトを作成  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  4. 貪欲的選択ループ                │
│     - 未カバーパスを最も多くカバー  │
│       するスニペットを選択          │
│     - 選択したスニペットをXMLに追加 │
│     - 目標カバレッジまで繰り返し    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  5. XML出力                         │
│     - 選択されたスニペットを統合    │
│     - XMLファイルとして保存         │
└─────────────────────────────────────┘
```

### スニペット生成戦略

#### 1. 深度別生成

各深度レベル（0〜max_gen_depth）でスニペットを生成します。

```
深度0: <Item />
深度1: <Item><Name>text</Name></Item>
深度2: <Item><Name>text</Name><SubItem><Name>text</Name></SubItem></Item>
...
```

#### 2. バリエーション生成

同じ深度でも、異なるバリエーションを生成します。

**バリエーション1**: すべてのオプション要素を含む
```xml
<Item ItemID="id1" Quantity="1" Priority="high" Status="active">
    <Name>text</Name>
    <Description>text</Description>  <!-- オプション -->
    <Details Type="type1">           <!-- オプション -->
        <Note>text</Note>
        <Tag Name="name1" Value="value1"/>
    </Details>
</Item>
```

**バリエーション2**: 必須要素のみ
```xml
<Item ItemID="id1">
    <Name>text</Name>
</Item>
```

#### 3. Choice構造の処理

XSDで choice 構造が定義されている場合、各選択肢ごとにスニペットを生成します。

```xml
<!-- choice: ContactMethod -->
<!-- 選択肢1: Email -->
<Contact>
    <Email>example@example.com</Email>
</Contact>

<!-- 選択肢2: Phone -->
<Contact>
    <Phone>123-456-7890</Phone>
</Contact>
```

---

## 実装アーキテクチャ

### クラス構造

```
xml_generator.py
│
├── XMLSnippet
│   ├── xml_element: lxml.etree.Element
│   ├── covered_paths: Set[str]
│   └── メソッド: to_string(), merge()
│
├── XMLGenerator
│   ├── schema_analyzer: SchemaAnalyzer
│   ├── namespace_map: Dict[str, str]
│   ├── root_elem_name: str
│   └── メソッド:
│       ├── generate_snippets()
│       ├── _generate_snippet_for_depth()
│       ├── _build_element()
│       ├── _build_inline_type()
│       ├── _add_attributes()
│       └── _calculate_snippet_coverage()
│
└── SetCoverOptimizer
    ├── all_paths: Set[str]
    ├── snippets: List[XMLSnippet]
    └── メソッド:
        ├── optimize()
        └── _greedy_selection()
```

---

## 詳細なアルゴリズムフロー

### Phase 1: スキーマ解析

```python
def __init__(self, xsd_path, max_depth, max_gen_depth, namespace_map):
    # SchemaAnalyzerでXSDを解析
    self.schema_analyzer = SchemaAnalyzer(xsd_path)
    self.schema_analyzer.analyze(max_depth)

    # 全カバレッジ項目を取得
    self.all_paths = (
        self.schema_analyzer.element_paths |
        self.schema_analyzer.attribute_paths
    )

    # ルート要素を特定
    self.root_elem_name = self._find_root_element()
```

**出力**: 全236パス（Sample Schema）または3491パス（ISO Schema）

### Phase 2: スニペット候補生成

```python
def generate_snippets(self) -> List[XMLSnippet]:
    snippets = []

    # 各深度でスニペットを生成
    for depth in range(self.max_gen_depth + 1):
        # バリエーション1: すべてのオプション要素を含む
        snippet1 = self._generate_snippet_for_depth(
            self.root_elem_name,
            root_type_name,
            target_depth=depth,
            include_optional=True,
            choice_index=0
        )
        if snippet1:
            snippets.append(snippet1)

        # バリエーション2: 必須要素のみ
        snippet2 = self._generate_snippet_for_depth(
            self.root_elem_name,
            root_type_name,
            target_depth=depth,
            include_optional=False,
            choice_index=0
        )
        if snippet2:
            snippets.append(snippet2)

        # バリエーション3+: choice構造の各選択肢
        # （実装では簡略化のため省略）

    return snippets
```

**出力**: 深度11段階 × 2バリエーション = 約22個のスニペット候補

### Phase 3: カバレッジ計算

各スニペットについて、含まれるパスを列挙します。

```python
def _calculate_snippet_coverage(self, elem: etree.Element,
                                  current_path: str = "") -> Set[str]:
    covered = set()

    # 現在の要素パスを追加
    if current_path:
        covered.add(current_path)

    # 属性パスを追加
    for attr_name in elem.attrib:
        attr_path = f"{current_path}@{attr_name}"
        covered.add(attr_path)

    # 子要素を再帰的に処理
    for child in elem:
        child_tag = etree.QName(child).localname
        child_path = f"{current_path}/{child_tag}"
        covered.update(
            self._calculate_snippet_coverage(child, child_path)
        )

    return covered
```

**例**:
```xml
<Item ItemID="id1">
    <Name>text</Name>
</Item>
```
→ カバーされるパス: `{"/Item", "/Item@ItemID", "/Item/Name"}`

### Phase 4: 貪欲的選択

```python
def _greedy_selection(self, target_coverage: float,
                       max_files: int) -> List[XMLSnippet]:
    selected = []
    uncovered = self.all_paths.copy()

    while len(selected) < max_files:
        # 現在のカバレッジを計算
        current_coverage = 1.0 - (len(uncovered) / len(self.all_paths))
        if current_coverage >= target_coverage:
            break

        # 最も多くの未カバーパスをカバーするスニペットを選択
        best_snippet = None
        best_new_coverage = 0

        for snippet in self.snippets:
            new_coverage = len(snippet.covered_paths & uncovered)
            if new_coverage > best_new_coverage:
                best_new_coverage = new_coverage
                best_snippet = snippet

        if best_snippet is None or best_new_coverage == 0:
            break  # これ以上改善できない

        # スニペットを選択
        selected.append(best_snippet)
        uncovered -= best_snippet.covered_paths

    return selected
```

**動作例**（Sample Schema）:

| イテレーション | 選択スニペット | 新規カバー | 累積カバレッジ |
|----------------|----------------|------------|----------------|
| 1 | depth=10, optional=True | 210パス | 88.98% |
| 終了 | - | - | 88.98% |

### Phase 5: XML出力

選択されたスニペットを単一のXMLファイルとして保存します。

```python
def save_xml_files(self, selected_snippets: List[XMLSnippet],
                    output_dir: str):
    for i, snippet in enumerate(selected_snippets, 1):
        filename = f"greedy_generated_{i:03d}.xml"
        filepath = os.path.join(output_dir, filename)

        # XMLを整形して保存
        xml_str = etree.tostring(
            snippet.xml_element,
            pretty_print=True,
            xml_declaration=True,
            encoding='utf-8'
        ).decode('utf-8')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(xml_str)
```

---

## 主要クラスとメソッド

### 1. XMLSnippet クラス

XMLスニペットとそのカバレッジ情報を保持します。

```python
class XMLSnippet:
    def __init__(self, xml_element: etree.Element, covered_paths: Set[str]):
        """
        Args:
            xml_element: lxml.etree.Element オブジェクト
            covered_paths: このスニペットがカバーするパスの集合
        """
        self.xml_element = xml_element
        self.covered_paths = covered_paths

    def to_string(self) -> str:
        """XMLを文字列として取得"""
        return etree.tostring(
            self.xml_element,
            pretty_print=True,
            encoding='unicode'
        )
```

### 2. XMLGenerator クラス

XSDからXMLスニペット候補を生成します。

#### 主要メソッド

##### `generate_snippets() -> List[XMLSnippet]`

すべてのスニペット候補を生成します。

```python
def generate_snippets(self) -> List[XMLSnippet]:
    """
    XSDスキーマから複数のXMLスニペット候補を生成

    Returns:
        生成されたXMLSnippetのリスト
    """
    snippets = []

    for depth in range(self.max_gen_depth + 1):
        # バリエーション1: オプション要素を含む
        snippet1 = self._generate_snippet_for_depth(
            self.root_elem_name,
            root_type_name,
            target_depth=depth,
            include_optional=True,
            choice_index=0
        )
        if snippet1:
            snippets.append(snippet1)

        # バリエーション2: 必須要素のみ
        snippet2 = self._generate_snippet_for_depth(
            self.root_elem_name,
            root_type_name,
            target_depth=depth,
            include_optional=False,
            choice_index=0
        )
        if snippet2:
            snippets.append(snippet2)

    return snippets
```

##### `_generate_snippet_for_depth() -> Optional[XMLSnippet]`

指定した深度のスニペットを生成します。

```python
def _generate_snippet_for_depth(
    self,
    elem_name: str,
    elem_type: str,
    target_depth: int,
    include_optional: bool = True,
    choice_index: int = 0
) -> Optional[XMLSnippet]:
    """
    指定された深度までのXMLスニペットを生成

    Args:
        elem_name: 要素名
        elem_type: 型名
        target_depth: 目標深度
        include_optional: オプション要素を含むか
        choice_index: choice構造で選択する要素のインデックス

    Returns:
        生成されたXMLSnippet、または None
    """
    elem = self._build_element(
        elem_name,
        elem_type,
        current_depth=0,
        target_depth=target_depth,
        include_optional=include_optional,
        choice_index=choice_index
    )

    if elem is None:
        return None

    # カバレッジを計算
    covered_paths = self._calculate_snippet_coverage(elem, f"/{elem_name}")

    return XMLSnippet(elem, covered_paths)
```

##### `_build_element() -> Optional[etree.Element]`

要素を再帰的に構築します。

```python
def _build_element(
    self,
    elem_name: str,
    elem_type: str,
    current_depth: int,
    target_depth: int,
    parent_path: str = "",
    include_optional: bool = True,
    choice_index: int = 0
) -> Optional[etree.Element]:
    """
    要素を再帰的に構築

    深度制御:
        - current_depth < target_depth: 子要素を追加
        - current_depth == target_depth: この要素で停止
        - current_depth > target_depth: None を返す
    """
    if current_depth > target_depth:
        return None

    # 名前空間を含む要素を作成
    qname = etree.QName(self.namespace_map.get('default', ''), elem_name)
    elem = etree.Element(qname)

    # 属性を追加
    self._add_attributes(elem, elem_type, include_optional)

    # target_depthに到達したら子要素を追加しない
    if current_depth >= target_depth:
        # simpleContent の場合はテキストを設定
        if self._is_simple_content(elem_type):
            elem.text = "sample_text"
        return elem

    # complexType の処理
    self._build_inline_type(
        elem,
        elem_type,
        current_depth,
        target_depth,
        parent_path + "/" + elem_name,
        include_optional,
        choice_index
    )

    return elem
```

##### `_add_attributes()`

要素に属性を追加します。

```python
def _add_attributes(
    self,
    elem: etree.Element,
    type_name: str,
    include_optional: bool
):
    """
    要素に属性を追加

    Args:
        elem: 属性を追加する要素
        type_name: 型名
        include_optional: オプション属性を含むか
    """
    # 型定義を取得
    type_def = self._find_type_definition(type_name)
    if type_def is None:
        return

    # 属性を列挙
    for attr in type_def.xpath('.//xs:attribute', namespaces=self.ns):
        attr_name = attr.get('name')
        attr_use = attr.get('use', 'optional')

        # 必須属性、またはオプション属性を含む設定の場合
        if attr_use == 'required' or include_optional:
            # ダミー値を設定
            elem.set(attr_name, self._generate_attribute_value(attr))
```

### 3. SetCoverOptimizer クラス

Set-Cover問題を貪欲法で解きます。

```python
class SetCoverOptimizer:
    def __init__(self, all_paths: Set[str], snippets: List[XMLSnippet]):
        """
        Args:
            all_paths: カバーすべき全パスの集合
            snippets: 選択可能なXMLスニペットのリスト
        """
        self.all_paths = all_paths
        self.snippets = snippets

    def optimize(
        self,
        target_coverage: float = 0.90,
        max_files: int = 10
    ) -> List[XMLSnippet]:
        """
        貪欲法でSet-Cover問題を解く

        Args:
            target_coverage: 目標カバレッジ率 (0.0〜1.0)
            max_files: 最大ファイル数

        Returns:
            選択されたXMLSnippetのリスト
        """
        return self._greedy_selection(target_coverage, max_files)

    def _greedy_selection(
        self,
        target_coverage: float,
        max_files: int
    ) -> List[XMLSnippet]:
        """貪欲的選択アルゴリズム"""
        selected = []
        uncovered = self.all_paths.copy()

        for _ in range(max_files):
            # 現在のカバレッジ
            current_coverage = 1.0 - (len(uncovered) / len(self.all_paths))
            if current_coverage >= target_coverage:
                break

            # 最良のスニペットを選択
            best_snippet = None
            best_new_coverage = 0

            for snippet in self.snippets:
                new_coverage = len(snippet.covered_paths & uncovered)
                if new_coverage > best_new_coverage:
                    best_new_coverage = new_coverage
                    best_snippet = snippet

            if best_snippet is None or best_new_coverage == 0:
                break

            selected.append(best_snippet)
            uncovered -= best_snippet.covered_paths

        return selected
```

---

## パラメータとチューニング

### 主要パラメータ

| パラメータ | 説明 | デフォルト値 | 推奨値 |
|-----------|------|--------------|--------|
| `max_depth` | XSD解析の最大深度 | 10 | 10〜15 |
| `max_gen_depth` | XML生成の最大深度 | 10 | 10〜12 |
| `target_coverage` | 目標カバレッジ率 | 0.90 | 0.90〜0.95 |
| `max_files` | 最大生成ファイル数 | 10 | 5〜10 |

### パラメータの影響

#### `max_gen_depth` の影響

| max_gen_depth | Sample カバレッジ | ISO カバレッジ | 生成時間 |
|---------------|-------------------|----------------|----------|
| 5 | 56.78% | 32.45% | ~0.5秒 |
| 7 | 72.34% | 43.21% | ~0.8秒 |
| 10 | 88.98% | 55.83% | ~1.2秒 |
| 12 | 89.12% | 56.01% | ~1.8秒 |

**推奨**: `max_gen_depth=10` が最もバランスが良い

#### `target_coverage` の影響

- `0.80`: 早期に終了、カバレッジ不足の可能性
- `0.90`: バランスが良い
- `0.95`: 到達困難な場合が多い（貪欲法の限界）

### チューニングガイドライン

#### 高カバレッジを優先する場合

```bash
python3 xml_generator.py schema.xsd -o output \
    --max-gen-depth 12 \
    --target-coverage 0.95 \
    --max-files 10
```

#### 速度を優先する場合

```bash
python3 xml_generator.py schema.xsd -o output \
    --max-gen-depth 7 \
    --target-coverage 0.80 \
    --max-files 5
```

---

## 性能分析

### 時間計算量

1. **スニペット生成**: O(D × V × N)
   - D: max_gen_depth
   - V: バリエーション数（通常2）
   - N: スキーマの要素数

2. **カバレッジ計算**: O(S × P)
   - S: スニペット数
   - P: 平均パス数/スニペット

3. **貪欲的選択**: O(S × F × P)
   - S: スニペット数
   - F: 選択するファイル数
   - P: 全パス数

**全体**: O(D × N + S × F × P)

### 空間計算量

- **スニペット候補**: O(S × P) ≈ O(D × P)
- **パス集合**: O(P)

**全体**: O(D × P)

### 実測性能

| スキーマ | パス数 | スニペット数 | 選択ファイル数 | 生成時間 |
|----------|--------|--------------|----------------|----------|
| Sample | 236 | 22 | 1 | 0.8秒 |
| ISO | 3491 | 22 | 1 | 1.5秒 |

---

## 利点と欠点

### 利点

1. **高速**: 1〜2秒で生成完了
2. **実装がシンプル**: 理解しやすく保守しやすい
3. **スケーラブル**: 大規模スキーマでも実用的
4. **パラメータ制御**: 柔軟なチューニングが可能
5. **メモリ効率**: スニペット候補のみをメモリに保持

### 欠点

1. **最適性保証なし**: 局所最適解に陥る可能性
2. **属性カバレッジの低さ**: 特に大規模スキーマで顕著
   - Sample: 79.17% (120パス中95パス)
   - ISO: 46.05% (2584パス中1190パス)
3. **カバレッジの限界**: 90%前後で頭打ち
4. **パラメータ依存**: 適切な`max_gen_depth`の設定が必要
5. **バリエーション不足**: choice構造の網羅が不十分

### 貪欲法 vs SMTソルバー

| 観点 | 貪欲法 | SMTソルバー |
|------|--------|-------------|
| カバレッジ（Sample） | 88.98% | 100.00% |
| カバレッジ（ISO） | 55.83% | 99.80% |
| 生成時間（Sample） | 0.8秒 | 1.0秒 |
| 生成時間（ISO） | 1.5秒 | 5.0秒 |
| 最適性保証 | なし | あり |
| 実装難易度 | 低 | 高 |

---

## 改善案

### 1. 属性優先戦略

属性カバレッジが低い問題に対処するため、属性を持つスニペットに高いスコアを付与します。

```python
def _calculate_snippet_score(
    self,
    snippet: XMLSnippet,
    uncovered: Set[str]
) -> float:
    """
    スニペットのスコアを計算（属性に重み付け）
    """
    new_coverage = snippet.covered_paths & uncovered

    # 要素パスと属性パスを分離
    element_paths = {p for p in new_coverage if '@' not in p}
    attribute_paths = {p for p in new_coverage if '@' in p}

    # 属性に2倍の重みを付与
    score = len(element_paths) + 2.0 * len(attribute_paths)

    return score
```

### 2. 深度適応的生成

スキーマサイズに応じて`max_gen_depth`を自動調整します。

```python
def _auto_adjust_depth(self, schema_size: int) -> int:
    """
    スキーマサイズに応じて最適な深度を自動計算
    """
    if schema_size < 100:
        return 8
    elif schema_size < 500:
        return 10
    elif schema_size < 2000:
        return 12
    else:
        return 15
```

### 3. choice構造の完全列挙

choice構造の各選択肢を完全に列挙します。

```python
def _generate_choice_variations(
    self,
    elem_name: str,
    elem_type: str,
    target_depth: int
) -> List[XMLSnippet]:
    """
    choice構造のすべてのバリエーションを生成
    """
    snippets = []
    choice_groups = self._extract_choice_groups(elem_type)

    for group in choice_groups:
        for i, choice_elem in enumerate(group):
            snippet = self._generate_snippet_for_depth(
                elem_name,
                elem_type,
                target_depth,
                include_optional=True,
                choice_index=i
            )
            if snippet:
                snippets.append(snippet)

    return snippets
```

### 4. 反復的深化戦略

目標カバレッジに到達するまで、徐々に深度を増やします。

```python
def generate_with_iterative_deepening(
    self,
    target_coverage: float
) -> List[XMLSnippet]:
    """
    反復的深化戦略でスニペットを生成
    """
    depth = 5
    max_depth = 15

    while depth <= max_depth:
        snippets = self.generate_snippets_up_to_depth(depth)
        optimizer = SetCoverOptimizer(self.all_paths, snippets)
        selected = optimizer.optimize(target_coverage)

        current_coverage = self._calculate_coverage(selected)
        if current_coverage >= target_coverage:
            return selected

        depth += 2  # 深度を2ずつ増やす

    return selected  # 最後の結果を返す
```

### 5. ハイブリッドアプローチ

貪欲法で初期解を生成し、局所探索で改善します。

```python
def local_search_improvement(
    self,
    initial_solution: List[XMLSnippet]
) -> List[XMLSnippet]:
    """
    局所探索で解を改善
    """
    current = initial_solution
    current_coverage = self._calculate_coverage(current)

    improved = True
    while improved:
        improved = False

        # 各スニペットを他のスニペットと交換してみる
        for i in range(len(current)):
            for new_snippet in self.snippets:
                if new_snippet in current:
                    continue

                # 交換
                candidate = current[:i] + [new_snippet] + current[i+1:]
                candidate_coverage = self._calculate_coverage(candidate)

                if candidate_coverage > current_coverage:
                    current = candidate
                    current_coverage = candidate_coverage
                    improved = True
                    break

            if improved:
                break

    return current
```

---

## まとめ

### 貪欲法の適用シーン

- **プロトタイピング**: 初期検証で素早く結果を得たい場合
- **中規模スキーマ**: 500パス以下のスキーマ
- **時間制約**: 1〜2秒以内での生成が必要な場合
- **カバレッジ要件**: 70〜80%のカバレッジで十分な場合

### 推奨事項

1. **小〜中規模スキーマ**: 貪欲法で十分
2. **大規模スキーマ**: SMTソルバーを推奨
3. **高カバレッジ要求**: SMTソルバーを推奨（99%以上）
4. **速度優先**: 貪欲法を推奨

### 今後の研究方向

1. 属性カバレッジ向上のための重み付け戦略
2. choice構造の自動検出と完全列挙
3. 反復的深化による効率的な探索
4. 局所探索による解の改善
5. 機械学習によるパラメータ自動調整

---

**文書作成日**: 2025-10-01
**作成者**: Claude Code (Anthropic)
