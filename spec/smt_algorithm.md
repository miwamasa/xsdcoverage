# SMTソルバーベースXML生成アルゴリズム解説

## 目次

1. [概要](#概要)
2. [理論的背景](#理論的背景)
3. [アルゴリズムの動作原理](#アルゴリズムの動作原理)
4. [実装アーキテクチャ](#実装アーキテクチャ)
5. [詳細なアルゴリズムフロー](#詳細なアルゴリズムフロー)
6. [主要クラスとメソッド](#主要クラスとメソッド)
7. [制約エンコーディング](#制約エンコーディング)
8. [最適化と目的関数](#最適化と目的関数)
9. [性能分析](#性能分析)
10. [利点と欠点](#利点と欠点)
11. [高度なテクニック](#高度なテクニック)

---

## 概要

SMTソルバーベースXML生成アルゴリズムは、**充足可能性問題（SAT）の拡張であるSMT（Satisfiability Modulo Theories）** を用いて、XSDスキーマから理論的に最適なXMLファイルを生成するアプローチです。

### 基本的なアイデア

1. すべてのXSDパスに対してブール変数を割り当て
2. XSDの構造制約（階層、必須、choice）をSMT制約として定式化
3. カバレッジを最大化する目的関数を定義
4. Z3 SMTソルバーで最適解を探索
5. 得られた変数割り当て（モデル）からXMLを構築

### 適用シーン

- **高カバレッジ要求**: 95%以上のカバレッジが必要な場合
- **大規模スキーマ**: 1000〜5000パスのスキーマ
- **最適性保証**: 理論的に最適な解が必要な場合
- **品質重視**: 生成時間より完全性を優先する場合

---

## 理論的背景

### SMT（Satisfiability Modulo Theories）

**定義**: 一階述語論理の式が充足可能かを判定する問題。SATの拡張版。

**基本概念**:
- **変数**: ブール変数（True/False）
- **制約**: 論理式（∧, ∨, ¬, →）
- **理論**: 整数、実数、配列などの追加構造
- **モデル**: 制約を満たす変数の割り当て

### Z3ソルバー

MicrosoftリサーチによるSMTソルバー。以下の機能を提供：

1. **充足可能性判定**: 制約が充足可能か判定
2. **モデル生成**: 制約を満たす変数割り当てを出力
3. **最適化**: 目的関数を最大化/最小化する解を探索
4. **多様な理論**: ブール、整数、実数、ビットベクトル等をサポート

### XML生成問題のSMT定式化

#### 変数定義

各XSDパス `p` に対してブール変数 `v_p` を定義：

```
v_p = True  ⟺  パス p がXMLに含まれる
v_p = False ⟺  パス p がXMLに含まれない
```

**例**（Sample Schema、236パス）:
```
v_/RootDocument : Bool
v_/RootDocument/Header : Bool
v_/RootDocument/Header/Name : Bool
v_/RootDocument/Header@version : Bool
...（全236変数）
```

#### 制約定義

XSDの構造制約を論理式として表現：

1. **階層制約**: 子が存在 → 親も存在
   ```
   v_child → v_parent
   ```

2. **必須要素制約**: 親が存在 → 必須子も存在
   ```
   v_parent → v_required_child
   ```

3. **choice制約**: 親が存在 → 正確に1つの選択肢が存在
   ```
   v_parent → (v_choice1 ⊕ v_choice2 ⊕ ... ⊕ v_choiceN)
   ```

4. **深度制約**: 指定深度を超えるパスは無効
   ```
   depth(p) > max_depth → ¬v_p
   ```

#### 目的関数

カバレッジを最大化：
```
maximize: Σ v_p  （すべてのパス p について）
```

---

## アルゴリズムの動作原理

### 全体フロー

```
┌─────────────────────────────────────┐
│  1. XSDスキーマ解析                 │
│     - SchemaAnalyzerでパス列挙      │
│     - 全カバレッジ項目を取得        │
│     - 制約情報を抽出                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  2. 変数マッピング                  │
│     - PathVariableMapper            │
│     - 各パスにZ3ブール変数を割り当て│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  3. 制約構築                        │
│     - SMTConstraintBuilder          │
│     - 階層制約、必須制約、choice制約│
│     - 深度制約、ファイル割り当て    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  4. 最適化                          │
│     - Z3 Optimizeソルバー           │
│     - カバレッジ最大化              │
│     - タイムアウト制御              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  5. モデルからXML構築               │
│     - ModelToXMLConverter           │
│     - True変数に対応するパスを抽出  │
│     - XMLツリー構造を生成           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  6. XML出力                         │
│     - XMLファイルとして保存         │
│     - 整形とバリデーション          │
└─────────────────────────────────────┘
```

### 制約充足からXML生成への流れ

```
XSDスキーマ
    │
    ├─ 要素階層 ──→ 階層制約（Implies）
    ├─ 必須要素 ──→ 必須制約（Implies）
    ├─ choice   ──→ choice制約（XOR）
    └─ 深度     ──→ 深度制約（Not）
    │
    ▼
Z3制約システム
    │
    ├─ 変数: v_p1, v_p2, ..., v_pN
    ├─ Hard制約: 構造制約（必ず満たす）
    └─ Soft制約: カバレッジ最大化（できるだけ満たす）
    │
    ▼
Z3 Optimize求解
    │
    ├─ SAT: 制約を満たす解が存在
    ├─ UNSAT: 制約を満たす解が存在しない
    └─ UNKNOWN: タイムアウトまたは不明
    │
    ▼（SATの場合）
モデル（変数割り当て）
    │
    ├─ v_/RootDocument = True
    ├─ v_/RootDocument/Header = True
    ├─ v_/RootDocument/Header/Name = True
    ├─ v_/RootDocument/Header@version = True
    └─ ...
    │
    ▼
XMLツリー構築
    │
    └─ <RootDocument>
         <Header version="...">
           <Name>...</Name>
         </Header>
       </RootDocument>
```

---

## 実装アーキテクチャ

### クラス構造

```
xml_generator_smt.py
│
├── PathVariableMapper
│   ├── path_to_var: Dict[str, Bool]
│   └── メソッド:
│       └── get_or_create_var(path: str) -> Bool
│
├── XSDConstraintExtractor
│   ├── schema_analyzer: SchemaAnalyzer
│   ├── parent_child_pairs: List[Tuple[str, str]]
│   ├── required_elements: List[Tuple[str, str]]
│   └── choice_groups: List[List[str]]
│   └── メソッド:
│       ├── extract_constraints(max_depth: int)
│       ├── _extract_parent_child_relationships()
│       ├── _extract_required_elements()
│       └── _extract_choice_constraints()
│
├── SMTConstraintBuilder
│   ├── var_mapper: PathVariableMapper
│   ├── constraint_extractor: XSDConstraintExtractor
│   └── メソッド:
│       ├── build_constraints() -> List[BoolRef]
│       ├── _build_hierarchy_constraints()
│       ├── _build_required_constraints()
│       ├── _build_choice_constraints()
│       └── _build_depth_constraints()
│
├── ModelToXMLConverter
│   ├── model: ModelRef
│   ├── var_mapper: PathVariableMapper
│   └── メソッド:
│       ├── build_xml() -> etree.Element
│       ├── _build_element_tree()
│       └── _add_attributes()
│
└── SMTXMLGenerator
    ├── schema_analyzer: SchemaAnalyzer
    ├── var_mapper: PathVariableMapper
    ├── constraint_extractor: XSDConstraintExtractor
    ├── constraint_builder: SMTConstraintBuilder
    └── メソッド:
        ├── generate()
        ├── _solve_with_z3()
        └── _convert_model_to_xml()
```

---

## 詳細なアルゴリズムフロー

### Phase 1: スキーマ解析と制約抽出

```python
def extract_constraints(self, max_depth: int):
    """
    XSDスキーマから制約情報を抽出

    抽出する情報:
    1. 親子関係（階層構造）
    2. 必須要素
    3. choice制約グループ
    """
    # SchemaAnalyzerでパス列挙
    self.schema_analyzer.analyze(max_depth)

    # 親子関係を抽出
    self._extract_parent_child_relationships()

    # 必須要素を抽出
    self._extract_required_elements()

    # choice制約を抽出
    self._extract_choice_constraints()
```

**出力例**（Sample Schema）:
```
親子関係: 235組
  (/RootDocument, /RootDocument/Body)
  (/RootDocument/Body, /RootDocument/Body/Item)
  (/RootDocument/Body/Item, /RootDocument/Body/Item/Name)
  ...

必須要素: 20個
  (/RootDocument, /RootDocument/Body)
  (/RootDocument/Body/Item, /RootDocument/Body/Item/Name)
  ...

choice制約: 0組（Sample Schemaにはchoice構造なし）
```

### Phase 2: 変数マッピング

すべてのパスに対してZ3ブール変数を作成します。

```python
class PathVariableMapper:
    def __init__(self):
        self.path_to_var = {}

    def get_or_create_var(self, path: str) -> Bool:
        """
        パスに対応するZ3変数を取得または作成

        変数名の生成規則:
        - '/' → '_'
        - '@' → '_AT_'

        例:
        - "/RootDocument" → v_RootDocument
        - "/Item@id" → v_Item_AT_id
        """
        if path in self.path_to_var:
            return self.path_to_var[path]

        # 変数名を生成
        var_name = path.replace('/', '_').replace('@', '_AT_')
        var = Bool(var_name)

        self.path_to_var[path] = var
        return var
```

**出力例**:
```python
v_RootDocument = Bool('_RootDocument')
v_RootDocument_Body = Bool('_RootDocument_Body')
v_RootDocument_Body_Item = Bool('_RootDocument_Body_Item')
v_RootDocument_Body_Item_AT_ItemID = Bool('_RootDocument_Body_Item_AT_ItemID')
...（全236変数）
```

### Phase 3: 制約構築

#### 3.1 階層制約

**論理**: 子が存在すれば、親も存在しなければならない

```python
def _build_hierarchy_constraints(self) -> List[BoolRef]:
    """
    階層制約: child → parent

    Z3表現: Implies(child_var, parent_var)
    """
    constraints = []

    for parent_path, child_path in self.parent_child_pairs:
        parent_var = self.var_mapper.get_or_create_var(parent_path)
        child_var = self.var_mapper.get_or_create_var(child_path)

        # child → parent
        constraints.append(Implies(child_var, parent_var))

    return constraints
```

**例**:
```python
Implies(v_RootDocument_Body_Item, v_RootDocument_Body)
Implies(v_RootDocument_Body, v_RootDocument)
```

**意味**:
- `/RootDocument/Body/Item` が存在する場合、`/RootDocument/Body` も存在する
- `/RootDocument/Body` が存在する場合、`/RootDocument` も存在する

#### 3.2 必須要素制約

**論理**: 親が存在すれば、必須子も存在しなければならない

```python
def _build_required_constraints(self) -> List[BoolRef]:
    """
    必須要素制約: parent → required_child

    Z3表現: Implies(parent_var, child_var)
    """
    constraints = []

    for parent_path, required_child_path in self.required_elements:
        parent_var = self.var_mapper.get_or_create_var(parent_path)
        child_var = self.var_mapper.get_or_create_var(required_child_path)

        # parent → required_child
        constraints.append(Implies(parent_var, child_var))

    return constraints
```

**例**:
```python
Implies(v_RootDocument, v_RootDocument_Body)
Implies(v_RootDocument_Body_Item, v_RootDocument_Body_Item_Name)
```

**意味**:
- `/RootDocument` が存在する場合、`/RootDocument/Body` も存在する（必須）
- `/RootDocument/Body/Item` が存在する場合、`.../Item/Name` も存在する（必須）

#### 3.3 Choice制約

**論理**: 親が存在すれば、選択肢のうち正確に1つが存在する

```python
def _build_choice_constraints(self) -> List[BoolRef]:
    """
    Choice制約: parent → exactly_one(choices)

    Z3表現:
    1. 親が存在すれば、少なくとも1つの選択肢が存在
       Implies(parent_var, Or(choice_vars))

    2. 選択肢は互いに排他的（ペアワイズ排除）
       For all i, j (i ≠ j):
         Not(And(choice_i, choice_j))
    """
    constraints = []

    for parent_path, choice_paths in self.choice_groups:
        parent_var = self.var_mapper.get_or_create_var(parent_path)
        choice_vars = [
            self.var_mapper.get_or_create_var(path)
            for path in choice_paths
        ]

        # 親が存在すれば、少なくとも1つの選択肢が存在
        constraints.append(Implies(parent_var, Or(choice_vars)))

        # 選択肢は互いに排他的
        for i, var1 in enumerate(choice_vars):
            for var2 in choice_vars[i+1:]:
                constraints.append(Not(And(var1, var2)))

    return constraints
```

**例**（仮想的なchoice構造）:
```xml
<Contact>
  <choice>
    <Email>...</Email>
    <Phone>...</Phone>
    <Address>...</Address>
  </choice>
</Contact>
```

```python
# 少なくとも1つ
Implies(v_Contact, Or(v_Contact_Email, v_Contact_Phone, v_Contact_Address))

# 互いに排他的
Not(And(v_Contact_Email, v_Contact_Phone))
Not(And(v_Contact_Email, v_Contact_Address))
Not(And(v_Contact_Phone, v_Contact_Address))
```

#### 3.4 深度制約

**論理**: 指定深度を超えるパスは無効

```python
def _build_depth_constraints(self, max_depth: int) -> List[BoolRef]:
    """
    深度制約: depth(p) > max_depth → ¬v_p

    Z3表現: Not(var)
    """
    constraints = []

    for path in self.var_mapper.path_to_var.keys():
        depth = path.count('/')
        if depth > max_depth:
            var = self.var_mapper.get_or_create_var(path)
            constraints.append(Not(var))

    return constraints
```

### Phase 4: 最適化

```python
def _solve_with_z3(
    self,
    constraints: List[BoolRef],
    timeout_ms: int,
    target_coverage: float
) -> Tuple[str, Optional[ModelRef], float]:
    """
    Z3 Optimizeソルバーで最適化

    目的: カバレッジを最大化
    """
    # Optimizeソルバーを作成
    optimizer = Optimize()

    # タイムアウト設定
    optimizer.set("timeout", timeout_ms)

    # Hard制約を追加（必ず満たす）
    for constraint in constraints:
        optimizer.add(constraint)

    # Soft制約（目的関数）: すべてのパスをTrueにしたい
    objective_sum = Sum([
        If(var, 1, 0)
        for var in self.var_mapper.path_to_var.values()
    ])

    # 最大化
    optimizer.maximize(objective_sum)

    # 求解
    result = optimizer.check()

    if result == sat:
        model = optimizer.model()
        coverage = self._calculate_coverage(model)
        return ("SAT", model, coverage)
    elif result == unsat:
        return ("UNSAT", None, 0.0)
    else:
        return ("UNKNOWN", None, 0.0)
```

**Z3の実行例**:
```
Z3ソルバーを実行中...
  変数数: 236
  制約数: 255 (階層235 + 必須20)
  タイムアウト: 60000ms

  結果: SAT（解が見つかりました）
  達成カバレッジ: 100.00%
  実行時間: 0.8秒
```

### Phase 5: モデルからXML構築

Z3が返すモデル（変数の真偽値割り当て）からXMLツリーを構築します。

```python
class ModelToXMLConverter:
    def build_xml(self, root_elem_name: str) -> etree.Element:
        """
        Z3モデルからXMLツリーを構築

        手順:
        1. モデルからTrue変数を抽出
        2. パスを階層的にソート
        3. 要素ツリーを構築
        4. 属性を追加
        """
        # True変数に対応するパスを抽出
        true_paths = self._extract_true_paths()

        # 要素パスと属性パスに分離
        element_paths = {p for p in true_paths if '@' not in p}
        attribute_paths = {p for p in true_paths if '@' in p}

        # ルート要素を作成
        root = self._build_element_tree(root_elem_name, element_paths)

        # 属性を追加
        self._add_attributes(root, attribute_paths)

        return root

    def _extract_true_paths(self) -> Set[str]:
        """モデルからTrue変数を抽出"""
        true_paths = set()

        for path, var in self.var_mapper.path_to_var.items():
            # モデルで変数の値を評価
            if is_true(self.model.eval(var)):
                true_paths.add(path)

        return true_paths

    def _build_element_tree(
        self,
        root_name: str,
        element_paths: Set[str]
    ) -> etree.Element:
        """要素ツリーを階層的に構築"""
        root = etree.Element(root_name)

        # パスを深度順にソート
        sorted_paths = sorted(element_paths, key=lambda p: p.count('/'))

        # 各パスに対して要素を作成
        path_to_elem = {f"/{root_name}": root}

        for path in sorted_paths:
            if path == f"/{root_name}":
                continue

            # 親パスを特定
            parent_path = '/'.join(path.rsplit('/', 1)[:-1])
            elem_name = path.rsplit('/', 1)[-1]

            # 親要素を取得
            parent_elem = path_to_elem.get(parent_path)
            if parent_elem is None:
                continue

            # 子要素を作成
            child_elem = etree.SubElement(parent_elem, elem_name)
            path_to_elem[path] = child_elem

        return root

    def _add_attributes(
        self,
        root: etree.Element,
        attribute_paths: Set[str]
    ):
        """属性を追加"""
        path_to_elem = self._build_path_map(root)

        for attr_path in attribute_paths:
            # 属性パスを分解
            # "/Item@id" → element_path="/Item", attr_name="id"
            element_path, attr_name = attr_path.rsplit('@', 1)

            # 対応する要素を取得
            elem = path_to_elem.get(element_path)
            if elem is not None:
                # ダミー値を設定
                elem.set(attr_name, self._generate_dummy_value(attr_name))
```

**構築例**:

**Z3モデル**:
```python
v_RootDocument = True
v_RootDocument_Body = True
v_RootDocument_Body_Item = True
v_RootDocument_Body_Item_Name = True
v_RootDocument_Body_Item_AT_ItemID = True
```

**生成されるXML**:
```xml
<RootDocument>
  <Body>
    <Item ItemID="id_1">
      <Name>sample_text</Name>
    </Item>
  </Body>
</RootDocument>
```

---

## 主要クラスとメソッド

### 1. PathVariableMapper クラス

パスとZ3ブール変数のマッピングを管理します。

```python
class PathVariableMapper:
    """
    パスとZ3ブール変数のマッピングを管理するクラス

    役割:
    - 各パスに対して一意のZ3変数を作成
    - パス名を有効なZ3変数名に変換
    - 変数の重複作成を防止
    """

    def __init__(self):
        self.path_to_var: Dict[str, Bool] = {}

    def get_or_create_var(self, path: str) -> Bool:
        """
        パスに対応するZ3変数を取得または作成

        Args:
            path: XSDパス（例: "/RootDocument/Body/Item@id"）

        Returns:
            Z3ブール変数
        """
        if path in self.path_to_var:
            return self.path_to_var[path]

        # 変数名を生成（/と@を置換）
        var_name = path.replace('/', '_').replace('@', '_AT_')

        # Z3変数を作成
        var = Bool(var_name)

        # マッピングに登録
        self.path_to_var[path] = var

        return var

    def get_all_vars(self) -> List[Bool]:
        """すべてのZ3変数を取得"""
        return list(self.path_to_var.values())

    def get_path_for_var(self, var: Bool) -> Optional[str]:
        """Z3変数から対応するパスを取得"""
        for path, v in self.path_to_var.items():
            if v.eq(var):
                return path
        return None
```

### 2. XSDConstraintExtractor クラス

XSDスキーマから制約情報を抽出します。

```python
class XSDConstraintExtractor:
    """
    XSDスキーマから制約情報を抽出するクラス

    抽出する情報:
    1. 親子関係（階層構造）
    2. 必須要素
    3. choice制約グループ
    """

    def __init__(self, xsd_path: str):
        self.schema_analyzer = SchemaAnalyzer(xsd_path)
        self.parent_child_pairs: List[Tuple[str, str]] = []
        self.required_elements: List[Tuple[str, str]] = []
        self.choice_groups: List[Tuple[str, List[str]]] = []

    def extract_constraints(self, max_depth: int):
        """制約情報を抽出"""
        # SchemaAnalyzerでパス列挙
        self.schema_analyzer.analyze(max_depth)

        # 各種制約を抽出
        self._extract_parent_child_relationships()
        self._extract_required_elements()
        self._extract_choice_constraints()

    def _extract_parent_child_relationships(self):
        """親子関係を抽出"""
        # 各要素パスについて、親パスを特定
        for path in self.schema_analyzer.element_paths:
            if path.count('/') <= 1:
                continue  # ルート要素

            # 親パスを計算
            parent_path = '/'.join(path.rsplit('/', 1)[:-1])

            # 親子ペアを追加
            self.parent_child_pairs.append((parent_path, path))

        # 属性についても同様
        for path in self.schema_analyzer.attribute_paths:
            # 属性の親要素パスを計算
            element_path = path.rsplit('@', 1)[0]

            # 要素-属性ペアを追加
            self.parent_child_pairs.append((element_path, path))

    def _extract_required_elements(self):
        """必須要素を抽出"""
        # XSDのminOccurs >= 1の要素を必須とする
        for elem_path in self.schema_analyzer.element_paths:
            # 要素の定義を取得
            elem_def = self._find_element_definition(elem_path)
            if elem_def is None:
                continue

            # minOccursをチェック
            min_occurs = int(elem_def.get('minOccurs', '1'))
            if min_occurs >= 1:
                # 親パスを計算
                if elem_path.count('/') > 1:
                    parent_path = '/'.join(elem_path.rsplit('/', 1)[:-1])
                    self.required_elements.append((parent_path, elem_path))

    def _extract_choice_constraints(self):
        """choice制約を抽出"""
        # XSDのchoice構造を検出
        # （実装は複雑なため、簡略化）
        # choice要素の子要素を列挙し、グループとして登録
        pass
```

### 3. SMTConstraintBuilder クラス

XSD制約をZ3 SMT制約に変換します。

```python
class SMTConstraintBuilder:
    """
    XSD制約をZ3 SMT制約に変換するクラス

    生成する制約:
    1. 階層制約: child → parent
    2. 必須要素制約: parent → required_child
    3. choice制約: parent → exactly_one(choices)
    4. 深度制約: depth > max_depth → ¬var
    """

    def __init__(
        self,
        var_mapper: PathVariableMapper,
        constraint_extractor: XSDConstraintExtractor
    ):
        self.var_mapper = var_mapper
        self.constraint_extractor = constraint_extractor

    def build_constraints(self, max_depth: int) -> List[BoolRef]:
        """すべての制約を構築"""
        constraints = []

        # 階層制約
        constraints.extend(self._build_hierarchy_constraints())

        # 必須要素制約
        constraints.extend(self._build_required_constraints())

        # choice制約
        constraints.extend(self._build_choice_constraints())

        # 深度制約
        constraints.extend(self._build_depth_constraints(max_depth))

        return constraints

    def _build_hierarchy_constraints(self) -> List[BoolRef]:
        """階層制約を構築"""
        constraints = []

        for parent_path, child_path in self.constraint_extractor.parent_child_pairs:
            parent_var = self.var_mapper.get_or_create_var(parent_path)
            child_var = self.var_mapper.get_or_create_var(child_path)

            # child → parent
            constraints.append(Implies(child_var, parent_var))

        return constraints

    def _build_required_constraints(self) -> List[BoolRef]:
        """必須要素制約を構築"""
        constraints = []

        for parent_path, child_path in self.constraint_extractor.required_elements:
            parent_var = self.var_mapper.get_or_create_var(parent_path)
            child_var = self.var_mapper.get_or_create_var(child_path)

            # parent → required_child
            constraints.append(Implies(parent_var, child_var))

        return constraints

    def _build_choice_constraints(self) -> List[BoolRef]:
        """choice制約を構築"""
        constraints = []

        for parent_path, choice_paths in self.constraint_extractor.choice_groups:
            parent_var = self.var_mapper.get_or_create_var(parent_path)
            choice_vars = [
                self.var_mapper.get_or_create_var(path)
                for path in choice_paths
            ]

            # 親が存在すれば、少なくとも1つの選択肢が存在
            constraints.append(Implies(parent_var, Or(choice_vars)))

            # 選択肢は互いに排他的
            for i, var1 in enumerate(choice_vars):
                for var2 in choice_vars[i+1:]:
                    constraints.append(Not(And(var1, var2)))

        return constraints

    def _build_depth_constraints(self, max_depth: int) -> List[BoolRef]:
        """深度制約を構築"""
        constraints = []

        for path in self.var_mapper.path_to_var.keys():
            depth = path.count('/')
            if depth > max_depth:
                var = self.var_mapper.get_or_create_var(path)
                constraints.append(Not(var))

        return constraints
```

### 4. SMTXMLGenerator クラス

メインの生成ロジックを統合します。

```python
class SMTXMLGenerator:
    """
    SMTソルバーを用いてXMLを生成するメインクラス

    統合する処理:
    1. スキーマ解析
    2. 変数マッピング
    3. 制約構築
    4. Z3求解
    5. XML構築
    """

    def __init__(
        self,
        xsd_path: str,
        max_depth: int,
        namespace_map: Dict[str, str]
    ):
        self.schema_analyzer = SchemaAnalyzer(xsd_path)
        self.max_depth = max_depth
        self.namespace_map = namespace_map

        # サブコンポーネントを初期化
        self.var_mapper = PathVariableMapper()
        self.constraint_extractor = XSDConstraintExtractor(xsd_path)
        self.constraint_builder = None  # 後で初期化

    def generate(
        self,
        target_coverage: float = 0.95,
        timeout_ms: int = 60000
    ) -> List[etree.Element]:
        """
        XMLを生成

        Args:
            target_coverage: 目標カバレッジ率
            timeout_ms: Z3タイムアウト（ミリ秒）

        Returns:
            生成されたXML要素のリスト
        """
        # Step 1: 制約情報を抽出
        self.constraint_extractor.extract_constraints(self.max_depth)

        # Step 2: 変数を作成
        for path in (
            self.schema_analyzer.element_paths |
            self.schema_analyzer.attribute_paths
        ):
            self.var_mapper.get_or_create_var(path)

        # Step 3: 制約を構築
        self.constraint_builder = SMTConstraintBuilder(
            self.var_mapper,
            self.constraint_extractor
        )
        constraints = self.constraint_builder.build_constraints(self.max_depth)

        # Step 4: Z3で求解
        result, model, coverage = self._solve_with_z3(
            constraints,
            timeout_ms,
            target_coverage
        )

        if result != "SAT":
            raise Exception(f"Z3 solver returned {result}")

        # Step 5: XMLを構築
        xml_elements = self._convert_model_to_xml(model)

        return xml_elements

    def _solve_with_z3(
        self,
        constraints: List[BoolRef],
        timeout_ms: int,
        target_coverage: float
    ) -> Tuple[str, Optional[ModelRef], float]:
        """Z3で求解"""
        optimizer = Optimize()
        optimizer.set("timeout", timeout_ms)

        # Hard制約を追加
        for constraint in constraints:
            optimizer.add(constraint)

        # Soft制約（目的関数）
        objective_sum = Sum([
            If(var, 1, 0)
            for var in self.var_mapper.get_all_vars()
        ])
        optimizer.maximize(objective_sum)

        # 求解
        result = optimizer.check()

        if result == sat:
            model = optimizer.model()
            coverage = self._calculate_coverage(model)
            return ("SAT", model, coverage)
        else:
            return (str(result), None, 0.0)

    def _convert_model_to_xml(
        self,
        model: ModelRef
    ) -> List[etree.Element]:
        """モデルからXMLを構築"""
        converter = ModelToXMLConverter(
            model,
            self.var_mapper,
            self.namespace_map
        )

        root_elem_name = self._find_root_element()
        xml_elem = converter.build_xml(root_elem_name)

        return [xml_elem]
```

---

## 制約エンコーディング

### 論理演算子のZ3表現

| 論理 | 数学記号 | Z3 表現 | 意味 |
|------|----------|---------|------|
| AND | p ∧ q | `And(p, q)` | pかつq |
| OR | p ∨ q | `Or(p, q)` | pまたはq |
| NOT | ¬p | `Not(p)` | pでない |
| IMPLIES | p → q | `Implies(p, q)` | pならばq |
| IFF | p ↔ q | `p == q` | pとqは同値 |
| XOR | p ⊕ q | `Xor(p, q)` | pまたはqどちらか一方 |

### 制約パターン

#### パターン1: 親子関係（階層制約）

**論理**: 子が存在すれば、親も存在する

```
child → parent
```

**Z3コード**:
```python
Implies(v_child, v_parent)
```

**真理値表**:
| v_child | v_parent | Implies(v_child, v_parent) |
|---------|----------|----------------------------|
| False   | False    | True ✓                     |
| False   | True     | True ✓                     |
| True    | False    | False ✗                    |
| True    | True     | True ✓                     |

**意味**: 子がFalse（存在しない）なら親の存在は任意。子がTrue（存在する）なら親もTrue（存在する）でなければならない。

#### パターン2: 必須要素

**論理**: 親が存在すれば、必須子も存在する

```
parent → required_child
```

**Z3コード**:
```python
Implies(v_parent, v_required_child)
```

**真理値表**:
| v_parent | v_required_child | Implies(v_parent, v_required_child) |
|----------|------------------|-------------------------------------|
| False    | False            | True ✓                              |
| False    | True             | True ✓                              |
| True     | False            | False ✗                             |
| True     | True             | True ✓                              |

#### パターン3: Exactly-One (XOR)

**論理**: 親が存在すれば、選択肢のうち正確に1つが存在する

```
parent → (choice1 ⊕ choice2 ⊕ ... ⊕ choiceN)
```

**Z3コード**:
```python
# 少なくとも1つ
Implies(v_parent, Or(v_choice1, v_choice2, v_choice3))

# 互いに排他的
Not(And(v_choice1, v_choice2))
Not(And(v_choice1, v_choice3))
Not(And(v_choice2, v_choice3))
```

**代替実装（PbEq使用）**:
```python
# 正確に1つがTrueでなければならない
Implies(v_parent, PbEq([(v_choice1, 1), (v_choice2, 1), (v_choice3, 1)], 1))
```

#### パターン4: At-Least-One

**論理**: 親が存在すれば、選択肢の少なくとも1つが存在する

```
parent → (choice1 ∨ choice2 ∨ ... ∨ choiceN)
```

**Z3コード**:
```python
Implies(v_parent, Or(v_choice1, v_choice2, v_choice3))
```

#### パターン5: At-Most-N

**論理**: 選択肢のうち最大N個まで存在できる

```
Σ choices ≤ N
```

**Z3コード**:
```python
# Pseudo-Boolean制約を使用
PbLe([(v_choice1, 1), (v_choice2, 1), (v_choice3, 1)], N)
```

---

## 最適化と目的関数

### 目的関数の定義

カバレッジを最大化するため、できるだけ多くのパスをTrueにします。

```python
# 目的関数: すべてのパスの合計を最大化
objective = Sum([
    If(var, 1, 0)
    for var in all_vars
])

optimizer.maximize(objective)
```

### Hard制約 vs Soft制約

#### Hard制約（必ず満たす）

- 階層制約
- 必須要素制約
- choice制約
- 深度制約

```python
optimizer.add(constraint)  # Hard制約
```

#### Soft制約（できるだけ満たす）

- カバレッジ最大化

```python
optimizer.maximize(objective)  # Soft制約
```

### 複数の目的関数

複数の目的を持つ場合、優先順位を設定できます。

```python
# 優先度1: カバレッジを最大化
h1 = optimizer.maximize(coverage_sum)

# 優先度2: ファイル数を最小化（カバレッジを維持しつつ）
h2 = optimizer.minimize(file_count)
```

---

## 性能分析

### 時間計算量

1. **変数作成**: O(P)
   - P: 全パス数

2. **制約構築**: O(C)
   - C: 制約数 ≈ O(P)

3. **Z3求解**: O(2^P) 最悪ケース、実際はヒューリスティックで高速化
   - 実測: P=236で1秒、P=3491で5秒

4. **XML構築**: O(P)

**全体**: O(P + 2^P) ≈ O(2^P) 理論上、実際はO(P log P)程度

### 空間計算量

- **変数**: O(P)
- **制約**: O(C) ≈ O(P)
- **Z3内部状態**: O(P^2) 推定

**全体**: O(P^2)

### 実測性能

| スキーマ | パス数 | 変数数 | 制約数 | Z3時間 | XML構築時間 | 合計時間 |
|----------|--------|--------|--------|--------|-------------|----------|
| Sample | 236 | 236 | 255 | 0.8秒 | 0.2秒 | 1.0秒 |
| ISO | 3491 | 3491 | 3888 | 4.5秒 | 0.5秒 | 5.0秒 |

### スケーラビリティ

| パス数 | 推定時間 |
|--------|----------|
| < 500 | < 2秒 |
| 500-1000 | 2-5秒 |
| 1000-2000 | 5-15秒 |
| 2000-5000 | 15-60秒 |
| > 5000 | > 60秒（タイムアウト推奨） |

---

## 利点と欠点

### 利点

1. **最適性保証**: 制約の範囲内で理論的に最適な解を発見
2. **完全カバレッジ**: ほぼ100%のカバレッジを達成
   - Sample: 100.00%
   - ISO: 99.80%
3. **制約表現力**: 複雑なXSD制約を正確にモデル化
4. **探索の網羅性**: 解空間を系統的に探索
5. **パラメータ不要**: 貪欲法のような細かいチューニングが不要
6. **実用的な速度**: 大規模スキーマでも数秒で完了

### 欠点

1. **計算コスト**: 貪欲法より遅い（1秒 vs 5秒）
2. **実装の複雑さ**: Z3制約の構築とデバッグが難しい
3. **ブラックボックス**: Z3の内部動作が不透明
4. **スケーラビリティの限界**: 超大規模スキーマ（> 10000パス）ではタイムアウトの可能性
5. **外部依存**: Z3ライブラリが必要

### 貪欲法との比較

| 観点 | 貪欲法 | SMTソルバー |
|------|--------|-------------|
| カバレッジ（Sample） | 88.98% | **100.00%** ✓ |
| カバレッジ（ISO） | 55.83% | **99.80%** ✓ |
| 生成時間（Sample） | **0.8秒** ✓ | 1.0秒 |
| 生成時間（ISO） | **1.5秒** ✓ | 5.0秒 |
| 最適性保証 | なし | **あり** ✓ |
| 実装難易度 | **低** ✓ | 高 |
| パラメータ調整 | 必要 | **不要** ✓ |

**結論**: カバレッジと最適性を優先する場合はSMTソルバー、速度を優先する場合は貪欲法。

---

## 高度なテクニック

### 1. 増分求解（Incremental Solving）

複数の類似した問題を効率的に解くために、制約を段階的に追加します。

```python
solver = Solver()

# 基本制約を追加
solver.add(hierarchy_constraints)
solver.add(required_constraints)

# 最初の求解
solver.push()
solver.add(depth_constraint_10)
result1 = solver.check()
model1 = solver.model()
solver.pop()

# 2回目の求解（深度を変更）
solver.push()
solver.add(depth_constraint_12)
result2 = solver.check()
model2 = solver.model()
solver.pop()
```

### 2. 複数解の列挙

異なるXMLバリエーションを生成するために、複数の解を列挙します。

```python
def enumerate_solutions(solver, vars, max_count=10):
    """
    複数の解を列挙

    各解を見つけたら、その解を除外する制約を追加し、
    次の解を探索する。
    """
    solutions = []

    for _ in range(max_count):
        if solver.check() == sat:
            model = solver.model()
            solutions.append(model)

            # この解を除外する制約を追加
            block_constraint = Or([
                var != model.eval(var)
                for var in vars
            ])
            solver.add(block_constraint)
        else:
            break  # これ以上解がない

    return solutions
```

### 3. 仮定を用いた求解（Solving with Assumptions）

一時的な制約を追加して求解します。

```python
# 通常の求解
result = solver.check()

# 仮定付き求解（一時的に追加制約を課す）
result = solver.check(v_optional_element)  # v_optional_elementがTrueと仮定

# 仮定は次のcheck()呼び出しには影響しない
```

### 4. 未解決コア（Unsat Core）の分析

制約が充足不可能な場合、どの制約が矛盾しているかを特定します。

```python
solver = Solver()
solver.set(unsat_core=True)

# 制約に名前を付けて追加
c1 = Bool('c1')
c2 = Bool('c2')
c3 = Bool('c3')

solver.add(Implies(c1, constraint1))
solver.add(Implies(c2, constraint2))
solver.add(Implies(c3, constraint3))

# 求解
result = solver.check([c1, c2, c3])

if result == unsat:
    # 矛盾している制約を特定
    core = solver.unsat_core()
    print("矛盾している制約:", core)
```

### 5. Quantifier Elimination

複雑な制約を単純化します。

```python
from z3 import *

# 複雑な制約（量化子を含む）
x, y = Ints('x y')
f = Exists([x], And(x > 0, x < 10, y == x + 5))

# 量化子を除去
simplified = Tactic('qe')(f).as_expr()
print(simplified)  # y > 5 ∧ y < 15
```

### 6. タクティック（Tactic）の使用

Z3の求解戦略をカスタマイズします。

```python
from z3 import *

# タクティックの組み合わせ
t = Then(
    'simplify',      # 式を簡略化
    'propagate-values',  # 値の伝播
    'solve-eqs',     # 等式を解く
    'smt'            # SMTソルバーを実行
)

# タクティックを適用
solver = t.solver()
solver.add(constraints)
result = solver.check()
```

### 7. 並列求解

複数のZ3インスタンスを並列実行します。

```python
from multiprocessing import Pool

def solve_with_config(config):
    """
    異なる設定でZ3を実行
    """
    solver = Solver()
    solver.set(**config)
    solver.add(constraints)
    return solver.check()

# 異なる設定を並列実行
configs = [
    {'timeout': 30000, 'random_seed': 42},
    {'timeout': 30000, 'random_seed': 123},
    {'timeout': 30000, 'random_seed': 456},
]

with Pool(3) as pool:
    results = pool.map(solve_with_config, configs)
```

---

## まとめ

### SMTソルバーの適用シーン

- **高カバレッジ要求**: 95%以上のカバレッジが必要
- **大規模スキーマ**: 1000〜5000パスのスキーマ
- **最適性保証**: 理論的に最適な解が必要
- **複雑な制約**: choice、必須、条件付き要素が多い

### 推奨事項

1. **小〜中規模スキーマ（< 1000パス）**: SMTソルバーが最適
2. **大規模スキーマ（1000〜5000パス）**: SMTソルバーを推奨（タイムアウト設定に注意）
3. **超大規模スキーマ（> 5000パス）**: ハイブリッドアプローチ（貪欲法 + SMT）を検討
4. **時間制約が厳しい**: 貪欲法を使用

### 今後の研究方向

1. **choice制約の自動検出**: XSDからchoice構造を正確に抽出
2. **条件付き属性のモデル化**: 属性の存在条件を制約として表現
3. **複数ファイル最適化**: 最小ファイル数で目標カバレッジを達成
4. **ハイブリッドアプローチ**: 貪欲法の初期解をSMTで改善
5. **並列化**: 大規模スキーマを部分問題に分割し並列求解
6. **機械学習との統合**: Z3のヒューリスティックを学習で最適化

---

**文書作成日**: 2025-10-01
**作成者**: Claude Code (Anthropic)
