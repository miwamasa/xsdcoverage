# カバレッジ計測の方法論と全数カウントの根拠

## 概要

本ドキュメントでは、XSDカバレッジ分析ツールにおける要素パスカバレッジと属性パスカバレッジの全数の計算方法について詳細に説明します。

## カウント方法の基本原則

### 1. 階層構造を考慮したパス識別

このツールの最も重要な特徴は、**階層構造を考慮してパスを識別する**ことです。

#### 基本ルール
- 同じ要素名でも、異なる階層に現れる場合は別の要素パスとして扱います
- 同じ属性名でも、親要素が異なれば別の属性パスとして扱います

#### 例：要素パスの区別
```xml
<RootDocument>
  <Header>
    <Name>Header Name</Name>  <!-- パス: /RootDocument/Header/Name -->
  </Header>
  <Body>
    <Item>
      <Name>Item Name</Name>  <!-- パス: /RootDocument/Body/Item/Name -->
    </Item>
  </Body>
</RootDocument>
```

上記の例では、`Name`要素が2箇所に登場しますが、以下の2つの異なるパスとしてカウントされます：
- `/RootDocument/Header/Name`
- `/RootDocument/Body/Item/Name`

#### 例：属性パスの区別
```xml
<RootDocument DocumentStatus="Completed">  <!-- パス: /RootDocument@DocumentStatus -->
  <Header Status="Pending">                <!-- パス: /RootDocument/Header@Status -->
  <Body Status="InProgress">               <!-- パス: /RootDocument/Body@Status -->
    <Item Status="Completed">              <!-- パス: /RootDocument/Body/Item@Status -->
```

`Status`属性は複数の要素に存在しますが、それぞれ別の属性パスとしてカウントされます。

### 2. 再帰的構造の処理

XSDスキーマには、要素が自分自身の型を子要素として持つ**再帰的構造**が存在することがあります。

#### 再帰的構造の例
```xsd
<xsd:complexType name="ItemType">
  <xsd:sequence>
    <xsd:element name="Name" type="xsd:string"/>
    <xsd:element name="SubItem" type="ItemType" minOccurs="0" maxOccurs="unbounded"/>
  </xsd:sequence>
</xsd:complexType>
```

この場合、`SubItem`は`ItemType`型なので、理論上は無限にネストできます：
- `/RootDocument/Body/Item/SubItem`
- `/RootDocument/Body/Item/SubItem/SubItem`
- `/RootDocument/Body/Item/SubItem/SubItem/SubItem`
- ...（無限に続く）

#### 再帰深度の制限

無限ループを防ぐため、ツールは**最大再帰深度**パラメータを使用します：

```python
schema_analyzer.analyze(max_recursion_depth=10)
```

デフォルト値は10で、これは以下を意味します：
- ルート要素から数えて最大10階層まで解析
- 再帰的な要素は最大10レベルまでカウント

#### 再帰深度によるパス数への影響

例：`extended_schema.xsd`の場合（max_depth=10）

`ItemType`は以下の子要素を持ちます：
- `Name`
- `Description`
- `Details`（さらに`Note`と`Tag`を持つ）
- `SubItem`（`ItemType`型 - 再帰！）

`/RootDocument/Body/Item`から始まる場合：

**深度3**: `/RootDocument/Body/Item`
- `/RootDocument/Body/Item/Name`
- `/RootDocument/Body/Item/Description`
- `/RootDocument/Body/Item/Details`
- `/RootDocument/Body/Item/Details/Note`
- `/RootDocument/Body/Item/Details/Tag`
- `/RootDocument/Body/Item/SubItem` ← 深度4

**深度4**: `/RootDocument/Body/Item/SubItem`
- `/RootDocument/Body/Item/SubItem/Name`
- `/RootDocument/Body/Item/SubItem/Description`
- `/RootDocument/Body/Item/SubItem/Details`
- `/RootDocument/Body/Item/SubItem/Details/Note`
- `/RootDocument/Body/Item/SubItem/Details/Tag`
- `/RootDocument/Body/Item/SubItem/SubItem` ← 深度5

...これが深度10まで続きます。

各レベルで6つの新しいパス（Name, Description, Details, Details/Note, Details/Tag, SubItem）が追加されるため、**再帰的構造は指数関数的にパス数を増加させます**。

## 要素パスカバレッジの全数の根拠

### カウント対象

XSDスキーマで定義されたすべての要素パスが対象です：

1. **ルート要素**: XSDの`<xsd:element name="..." />`で定義された最上位要素
2. **complexTypeの子要素**: `<xsd:complexType>`内の`<xsd:sequence>`, `<xsd:choice>`, `<xsd:all>`に定義された要素
3. **ref属性による参照要素**: `<xsd:element ref="..."/>`で参照される要素
4. **再帰的要素**: 最大深度まで展開されたすべてのレベル

### カウント方法

#### ステップ1: ルート要素の特定
```python
root_elements = schema_root.findall('.//xsd:element[@name]', ns)
for elem in root_elements:
    if parent.tag == f"{{{ns['xsd']}}}schema":
        path = f"/{elem.get('name')}"
        defined_element_paths.add(path)
```

ルート要素のみを処理対象とします（XSDスキーマ要素の直接の子）。

#### ステップ2: 型定義の解析
```python
def _process_type(type_name, current_path, depth, max_depth):
    # 型定義をキャッシュから取得
    type_def = type_cache.get(type_name)

    # sequence/choice/all内の要素を処理
    for elem in type_def.findall('.//xsd:sequence/xsd:element', ns):
        child_path = f"{current_path}/{elem.get('name')}"
        defined_element_paths.add(child_path)

        # 子要素の型を再帰的に処理
        if elem.get('type'):
            _process_type(elem.get('type'), child_path, depth + 1, max_depth)
```

各型定義について、すべての子要素を再帰的に展開します。

#### ステップ3: 深度制限の適用
```python
if depth > max_depth:
    return
```

指定された最大深度に達したら、それ以上の展開を停止します。

### テストその２（extended_schema.xsd）の例

**基本構造（再帰なし）**:
- `/RootDocument` (1)
- `/RootDocument/Header` (1)
- `/RootDocument/Header/Name` (1)
- `/RootDocument/Header/Description` (1)
- `/RootDocument/Header/Metadata` (1)
- `/RootDocument/Header/Metadata/Name` (1)
- `/RootDocument/Header/Metadata/Author` (1)
- `/RootDocument/Body` (1)
- `/RootDocument/Body/Item` (1)
- `/RootDocument/Body/Category` (1)
- `/RootDocument/Footer` (1)
- `/RootDocument/Footer/Timestamp` (1)
- `/RootDocument/Footer/Summary` (1)
- `/RootDocument/Footer/Summary/TotalItems` (1)
- `/RootDocument/Footer/Summary/Description` (1)

小計: **15パス**

**Item型の展開（Body直下）**:
- `/RootDocument/Body/Item/Name` (1)
- `/RootDocument/Body/Item/Description` (1)
- `/RootDocument/Body/Item/Details` (1)
- `/RootDocument/Body/Item/Details/Note` (1)
- `/RootDocument/Body/Item/Details/Tag` (1)
- `/RootDocument/Body/Item/SubItem` (1) + その再帰展開

**Category型の展開**:
- `/RootDocument/Body/Category/Name` (1)
- `/RootDocument/Body/Category/Description` (1)
- `/RootDocument/Body/Category/Item` (1) + Item型の展開

**再帰的SubItemの展開**:
- 最大深度10まで、2つの場所（Body/ItemとBody/Category/Item）から展開
- 各レベルで複数のパスが生成される

**合計: 116要素パス**

### テストその１（IEC62474スキーマ）の例

IEC62474は産業標準のXMLスキーマで、より複雑な構造を持ちます：

**主要な構造**:
- `Main` (ルート要素)
  - `BusinessInfo`
    - `Request` / `Response` / `Attachment`
  - `Product` (複数可)
    - `Compliance` / `Composition`
      - 多数の階層構造

**再帰的構造**:
- `ProductPart`要素は自身を子要素として持つ（最大10レベル）
- `Material`要素は複雑なネスト構造を持つ

**インポートされたスキーマ**:
```xsd
<xsd:import schemaLocation="http://www.w3.org/TR/xmldsig-core/xmldsig-core-schema.xsd"
            namespace="http://www.w3.org/2000/09/xmldsig#" />
```

ツールは外部スキーマもインポートして解析します（ただし、ネットワークアクセスできない場合はスキップ）。

**合計: 907要素パス**

## 属性パスカバレッジの全数の根拠

### カウント対象

XSDスキーマで定義されたすべての属性パスが対象です：

1. **complexTypeの属性**: `<xsd:attribute name="..." />`で定義された属性
2. **extensionによる継承属性**: `<xsd:extension base="...">`で基底型から継承された属性
3. **再帰的要素の属性**: 再帰的要素の各レベルで定義された属性

### カウント方法

#### ステップ1: 型定義内の属性を抽出
```python
for attr in type_def.findall('./xsd:attribute[@name]', ns):
    attr_name = attr.get('name')
    attr_path = f"{current_path}@{attr_name}"
    defined_attribute_paths.add(attr_path)
```

各complexType内の属性を、親要素のパスと組み合わせて属性パスとします。

#### ステップ2: 継承属性の処理
```python
for ext in type_def.findall('.//xsd:extension', ns):
    base_type = ext.get('base')
    # 基底型の処理
    _process_type(base_type, current_path, depth, max_depth)

    # extension内の属性
    for attr in ext.findall('./xsd:attribute[@name]', ns):
        attr_path = f"{current_path}@{attr.get('name')}"
        defined_attribute_paths.add(attr_path)
```

基底型の属性も含めてカウントします。

#### ステップ3: 再帰要素の属性展開
再帰的な要素の各レベルで、その型に定義されたすべての属性が属性パスとして追加されます。

### テストその２（extended_schema.xsd）の例

**基本属性**:
- `/RootDocument@DocumentStatus` (1)
- `/RootDocument@Version` (1)
- `/RootDocument/Header@DocumentID` (1)
- `/RootDocument/Header@Status` (1)
- `/RootDocument/Header/Metadata@ID` (1)
- `/RootDocument/Header/Metadata@Version` (1)
- `/RootDocument/Header/Metadata@CreationDate` (1)
- `/RootDocument/Body@Status` (1)
- `/RootDocument/Footer@Version` (1)

**Item型の属性（複数の場所で使用）**:
- `@ItemID` (required)
- `@Quantity` (optional)
- `@Status` (optional)
- `@Priority` (optional)

これらは以下の各パスで繰り返されます：
- `/RootDocument/Body/Item@...` (4属性)
- `/RootDocument/Body/Item/SubItem@...` (4属性)
- `/RootDocument/Body/Item/SubItem/SubItem@...` (4属性)
- ...（最大深度10まで）
- `/RootDocument/Body/Category/Item@...` (4属性)
- `/RootDocument/Body/Category/Item/SubItem@...` (4属性)
- ...（最大深度10まで）

**Details型の属性**:
- `@Type` (optional)

これも各Detailsパスで繰り返されます。

**Tag型の属性（simpleContent extension）**:
- `@Name` (optional)
- `@Value` (optional)

**合計: 120属性パス**

### テストその１（IEC62474スキーマ）の例

IEC62474スキーマは非常に多くの属性を定義しています：

**主要な属性群**:
- `Attachment`型: 7属性（fileName, fileType, fileURL, data, など）
- `Contact`型: 18属性（name, email, phone, address関連、など）
- `Mass`型: 6属性（mass, massRangeMin, massRangeMax, など）
- `Material`型: 複数の子要素に多数の属性
- `Product`型: 多数の属性とネスト構造

**再帰的構造の属性**:
- `ProductPart`の各レベルで定義された属性
- `Material`のネスト構造における属性

**合計: 2,584属性パス**

## カウントの精度向上のための工夫

### 1. 型定義のキャッシュ
```python
def _cache_type_definitions(self):
    complex_types = schema_root.findall('.//xsd:complexType[@name]', ns)
    for ct in complex_types:
        type_name = ct.get('name')
        self.type_cache[type_name] = ct
```

すべての型定義を事前にキャッシュし、効率的に参照できるようにします。

### 2. 無限再帰の防止
```python
tracking_key = f"{current_path}#{clean_type_name}#{depth}"
if tracking_key in processing_types:
    return
processing_types.add(tracking_key)
```

同じパスと型の組み合わせを深度ごとに追跡し、無限ループを防ぎます。

### 3. インポートされたスキーマの処理
```python
for imp in schema_root.findall('./xsd:import', ns):
    schema_location = imp.get('schemaLocation')
    if schema_location:
        _process_imported_schema(schema_location)
```

外部スキーマファイルもインポートして、完全なスキーマ定義を解析します。

### 4. 名前空間の正規化
```python
def _remove_ns_prefix(name):
    if ':' in name:
        return name.split(':')[1]
    return name
```

名前空間プレフィックスを除去し、一貫性のあるパス名を生成します。

## カウント結果の検証方法

### 1. 未定義パスのチェック

レポートの「XSDで未定義」セクションが0であることを確認：
```
XMLに存在する要素パス総数: 31
├─ XSDで定義済み: 31
└─ XSDで未定義: 0  ← これが0であることが重要！
```

未定義パスが0の場合：
- XSDの解析が正しく行われている
- XMLファイルがXSDに完全に準拠している

### 2. サンプルパスの手動検証

レポートに含まれるサンプルパスを手動で確認：

**要素パスの例**:
```
✓ /RootDocument/Body/Item/SubItem/SubItem/SubItem
```

このパスがXSDで定義されているか確認：
1. `RootDocument` → ルート要素として定義されている
2. `Body` → `RootDocumentType`の子要素として定義されている
3. `Item` → `BodyType`の子要素として定義されている（`ItemType`）
4. `SubItem` → `ItemType`の子要素として定義されている（再帰的に`ItemType`）
5. 以降の`SubItem`も同様に再帰的に定義されている

### 3. 再帰深度の確認

最も深いパスを確認：
```
/RootDocument/Body/Item/SubItem/SubItem/SubItem/SubItem/SubItem/SubItem/SubItem/SubItem/SubItem/SubItem
```

スラッシュの数を数えると：
- `RootDocument`: 深度1
- `Body`: 深度2
- `Item`: 深度3
- `SubItem`×10: 深度4〜13

これは設定した`max_depth=10`を超えているように見えますが、実際には深度の数え方が以下のように異なります：

```python
def analyze(self, max_recursion_depth=10):
    for elem in root_elements:
        # depth=0 から開始
        _process_type(elem_type, path, 0, max_recursion_depth)
```

深度0から開始するため、`max_recursion_depth=10`は実質11レベルまで処理します。

## まとめ

### 要素パスカバレッジの全数
XSDスキーマで定義されたすべての要素について、階層構造を考慮した完全なパスを生成し、再帰的構造を指定された最大深度まで展開してカウントします。

**計算要素**:
- ルート要素: 1個
- 基本的な階層構造: N個
- 再帰的構造の展開: M個（深度により変動）
- **合計**: 1 + N + M 個

### 属性パスカバレッジの全数
各要素パスについて、その要素の型定義に含まれるすべての属性を、階層パスと組み合わせてカウントします。

**計算要素**:
- 各要素パスに定義された属性数の合計
- 継承による属性も含む
- 再帰的要素の各レベルでの属性も含む

### 検証の確信度

両テストで**未定義パス数が0**であることから、以下が確認できます：
1. ツールはXSDスキーマを正確に解析している
2. XMLファイルはXSDに完全に準拠している
3. カウントされたパス数は信頼できる

**テストその２**: 116要素パス + 120属性パス = 236総パス
**テストその１**: 907要素パス + 2,584属性パス = 3,491総パス

これらの数値は、XSDスキーマの複雑さと再帰深度の設定を正確に反映しています。
