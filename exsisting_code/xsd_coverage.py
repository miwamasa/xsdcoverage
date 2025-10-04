#!/usr/bin/env python3
"""
XSD Schema Coverage Analyzer
階層構造を考慮した要素・属性カバレッジを計測するプログラム

【カバレッジ計測の基本方針】

■ 要素パスのカウント方法
  - XSDスキーマで定義されたすべての要素について、階層パスを生成
  - 同じ要素名でも、異なる階層に現れる場合は別パスとしてカウント
  - 例：/RootDocument/Header/Name と /RootDocument/Body/Item/Name は別パス

  カウント対象：
  1. ルート要素（XSDスキーマ直下のelement要素）
  2. complexType内のsequence/choice/all要素
  3. ref属性による参照要素
  4. 再帰的要素（最大深度まで展開）

  カウント例（extended_schema.xsd, max_depth=10）：
  - 基本パス数: 約28個
  - 再帰的SubItem展開: 約88個（2箇所×各44個）
  - 合計: 116個

■ 属性パスのカウント方法
  - 各要素パスについて、その型定義に含まれる属性を抽出
  - 親要素のパスと組み合わせて属性パスを生成
  - 例：/RootDocument/Body/Item@Status と /RootDocument/Header@Status は別パス

  カウント対象：
  1. complexType内のattribute要素
  2. extension/restrictionによる継承属性
  3. 再帰的要素の各レベルでの属性

  カウント例（extended_schema.xsd, max_depth=10）：
  - 基本属性数: 約30個
  - 再帰的SubItem展開に伴う属性: 約90個
  - 合計: 120個

■ 再帰深度の影響
  - max_recursion_depth パラメータで制御（デフォルト15）
  - ItemType → SubItem(ItemType) → SubItem(ItemType) → ... と展開
  - 深度が大きいほど、パス数が指数関数的に増加

■ カウント精度の検証方法
  - レポートの「XSDで未定義」が0であることを確認
  - 未定義=0 → XSD解析が正確、XMLがXSDに準拠
  - 未定義>0 → XSD解析に問題、またはXMLが非準拠

詳細は COUNTING_METHODOLOGY.md を参照してください。
"""

import sys
from lxml import etree
from collections import defaultdict
from typing import Set, Dict, List, Tuple
import glob


class SchemaAnalyzer:
    """XSDスキーマを解析して、定義されている要素・属性を抽出"""
    
    def __init__(self, xsd_path: str):
        self.xsd_path = xsd_path
        self.schema_tree = etree.parse(xsd_path)
        self.schema_root = self.schema_tree.getroot()
        
        # 名前空間の定義
        self.ns = {
            'xsd': 'http://www.w3.org/2001/XMLSchema'
        }
        
        # ターゲット名前空間を取得
        self.target_ns = self.schema_root.get('targetNamespace', '')
        
        # 定義された要素と属性のパスを格納
        self.defined_element_paths: Set[str] = set()
        self.defined_attribute_paths: Set[str] = set()
        
        # 型定義のキャッシュ
        self.type_cache: Dict[str, etree._Element] = {}
        
        # 処理済みの型を追跡（無限再帰を防ぐ）
        self.processing_types: Set[str] = set()
        
        # 処理済みのスキーマファイル
        self.processed_schemas: Set[str] = set()
        
        # XSDファイルのベースパス
        import os
        self.base_path = os.path.dirname(os.path.abspath(xsd_path))
        
    def analyze(self, max_recursion_depth: int = 15):
        """スキーマを解析して定義されたパスを抽出

        【要素パスカウントの開始点】
        このメソッドはXSDスキーマから要素パスと属性パスを抽出する処理のエントリーポイントです。

        Args:
            max_recursion_depth: 再帰的な要素（例：SubItemがItemType型）を展開する最大深度
                               デフォルトは15です。深いネスト構造のXMLに対応するため増加されました
                               この値が大きいほど、再帰構造のパス数が増加します

        処理の流れ:
        1. すべての型定義をキャッシュ（高速化のため）
        2. ルート要素を特定（XSDスキーマ要素の直接の子のみ）
        3. 各ルート要素について、その型定義を再帰的に展開してパスを抽出
        """

        # すべての型定義を事前にキャッシュ
        # これにより、同じ型を複数回解析する場合の効率が向上
        self._cache_type_definitions()

        # ルート要素を探す
        # .//はすべての子孫要素を検索するが、後でparentをチェックして
        # スキーマ直下の要素のみを処理する
        root_elements = self.schema_root.findall('.//xsd:element[@name]', self.ns)

        for elem in root_elements:
            elem_name = elem.get('name')
            elem_type = elem.get('type')

            # ルートレベルの要素のみを処理対象とする
            # これにより、型定義内の要素は後の再帰処理で扱われる
            parent = elem.getparent()
            if parent is not None and parent.tag == f"{{{self.ns['xsd']}}}schema":
                # 【要素パスのカウント①】
                # ルート要素のパスを追加（例: /RootDocument）
                path = f"/{self._remove_ns_prefix(elem_name)}"
                self.defined_element_paths.add(path)

                if elem_type:
                    # 【要素パスと属性パスのカウント開始】
                    # この要素の型定義を再帰的に処理して、すべての子孫要素と属性を抽出
                    # depth=0から開始し、max_recursion_depthまで展開
                    self._process_type(elem_type, path, 0, max_recursion_depth)
    
    def _cache_type_definitions(self):
        """すべての型定義をキャッシュに格納（インポート/インクルードも処理）"""
        self._cache_schema_types(self.schema_root)
        
        # import要素を処理
        for imp in self.schema_root.findall('./xsd:import', self.ns):
            schema_location = imp.get('schemaLocation')
            if schema_location and schema_location not in self.processed_schemas:
                self._process_imported_schema(schema_location)
        
        # include要素を処理
        for inc in self.schema_root.findall('./xsd:include', self.ns):
            schema_location = inc.get('schemaLocation')
            if schema_location and schema_location not in self.processed_schemas:
                self._process_imported_schema(schema_location)
    
    def _cache_schema_types(self, schema_root: etree._Element):
        """指定されたスキーマルートから型定義をキャッシュ"""
        complex_types = schema_root.findall('.//xsd:complexType[@name]', self.ns)
        for ct in complex_types:
            type_name = ct.get('name')
            if type_name:
                self.type_cache[type_name] = ct
        
        # simpleTypeも追加（列挙型などで使用される可能性）
        simple_types = schema_root.findall('.//xsd:simpleType[@name]', self.ns)
        for st in simple_types:
            type_name = st.get('name')
            if type_name:
                self.type_cache[type_name] = st
    
    def _process_imported_schema(self, schema_location: str):
        """インポート/インクルードされたスキーマを処理"""
        import os
        try:
            # 相対パスを解決
            if not os.path.isabs(schema_location):
                schema_path = os.path.join(self.base_path, schema_location)
            else:
                schema_path = schema_location
            
            # 既に処理済みかチェック
            if schema_path in self.processed_schemas:
                return
            
            self.processed_schemas.add(schema_path)
            
            # ファイルが存在するかチェック
            if os.path.exists(schema_path):
                imported_tree = etree.parse(schema_path)
                imported_root = imported_tree.getroot()
                self._cache_schema_types(imported_root)
                
                # インポートされたスキーマ内のさらなるインポートも処理
                for imp in imported_root.findall('./xsd:import', self.ns):
                    nested_location = imp.get('schemaLocation')
                    if nested_location:
                        # インポートされたスキーマのディレクトリを基準にパスを解決
                        nested_base = os.path.dirname(schema_path)
                        if not os.path.isabs(nested_location):
                            nested_path = os.path.join(nested_base, nested_location)
                        else:
                            nested_path = nested_location
                        if nested_path not in self.processed_schemas:
                            self._process_imported_schema(nested_path)
        except Exception as e:
            # インポートの処理に失敗しても続行
            print(f"警告: スキーマ '{schema_location}' の読み込みに失敗しました: {e}", file=sys.stderr)
    
    def _remove_ns_prefix(self, name: str) -> str:
        """名前空間プレフィックスを除去"""
        if ':' in name:
            return name.split(':')[1]
        return name
    
    def _process_type(self, type_name: str, current_path: str, depth: int, max_depth: int):
        """型定義を処理して、子要素と属性を抽出

        【要素パスと属性パスのカウントの中核】
        このメソッドは、XSDの型定義（complexType）を解析して、
        その型に含まれるすべての子要素と属性のパスを抽出します。

        Args:
            type_name: 処理する型の名前（例: "RootDocumentType", "ItemType"）
            current_path: 現在のパス（例: "/RootDocument/Body/Item"）
            depth: 現在の再帰深度（0から開始）
            max_depth: 最大再帰深度（通常10）

        再帰的構造の処理:
        ItemType型がSubItem要素を持ち、SubItemもItemType型の場合：
        - depth 0: /RootDocument/Body/Item を処理
        - depth 1: /RootDocument/Body/Item/SubItem を処理
        - depth 2: /RootDocument/Body/Item/SubItem/SubItem を処理
        - ...
        - depth 10: 最大深度に達したため処理を停止
        """

        # 【深度制限チェック】
        # 最大深度を超えたら処理を停止（無限再帰の防止）
        if depth > max_depth:
            return

        # 名前空間プレフィックスを除去
        # 例: "my:ItemType" → "ItemType"
        clean_type_name = self._remove_ns_prefix(type_name)

        # 【無限再帰の防止】
        # 同じパス・型・深度の組み合わせを追跡して、重複処理を防ぐ
        # 例: "/RootDocument/Body/Item#ItemType#3" のようなキー
        tracking_key = f"{current_path}#{clean_type_name}#{depth}"
        if tracking_key in self.processing_types:
            return

        self.processing_types.add(tracking_key)

        try:
            # キャッシュから型定義を取得
            type_def = self.type_cache.get(clean_type_name)

            if type_def is None:
                # 型定義が見つからない場合（組み込み型など）は処理をスキップ
                return

            # 【属性パスのカウント①】
            # この型に直接定義された属性を処理
            # 例: ItemType に @ItemID, @Quantity, @Status, @Priority が定義されている場合
            #     /RootDocument/Body/Item@ItemID
            #     /RootDocument/Body/Item@Quantity
            #     /RootDocument/Body/Item@Status
            #     /RootDocument/Body/Item@Priority
            # がカウントされる
            for attr in type_def.findall('./xsd:attribute[@name]', self.ns):
                attr_name = attr.get('name')
                attr_path = f"{current_path}@{attr_name}"
                self.defined_attribute_paths.add(attr_path)
            
            # 【属性パスのカウント②】
            # complexContent/extension内の属性も処理（継承による属性）
            # 例: ある型が別の型を継承している場合、基底型の属性も含める
            for ext in type_def.findall('.//xsd:extension', self.ns):
                base_type = ext.get('base')
                if base_type:
                    # 基底型の処理（基底型の属性も含まれる）
                    self._process_type(base_type, current_path, depth, max_depth)

                # extension内で新たに定義された属性
                for attr in ext.findall('./xsd:attribute[@name]', self.ns):
                    attr_name = attr.get('name')
                    attr_path = f"{current_path}@{attr_name}"
                    self.defined_attribute_paths.add(attr_path)

            # 【要素パスのカウント②】
            # sequence/choice/all内の要素を処理
            # .//で全子孫のsequence等を検索し、その中の直接の子要素を処理
            for container in type_def.findall('.//xsd:sequence', self.ns) + \
                           type_def.findall('.//xsd:choice', self.ns) + \
                           type_def.findall('.//xsd:all', self.ns):

                # 直接の子要素のみを処理（./で指定）
                # これにより、ネストした要素は再帰的に処理される
                for elem in container.findall('./xsd:element', self.ns):
                    elem_name = elem.get('name')
                    elem_ref = elem.get('ref')
                    elem_type = elem.get('type')

                    if elem_name:
                        # 【要素パスをカウント】
                        # 例: current_path="/RootDocument/Body", elem_name="Item"
                        #     → child_path="/RootDocument/Body/Item"
                        child_path = f"{current_path}/{elem_name}"
                        self.defined_element_paths.add(child_path)

                        # インライン型定義（匿名型）をチェック
                        # <xsd:element name="Foo"><xsd:complexType>...</xsd:complexType></xsd:element>
                        inline_complex_type = elem.find('./xsd:complexType', self.ns)
                        if inline_complex_type is not None:
                            # インライン型の処理
                            self._process_inline_type(inline_complex_type, child_path, depth + 1, max_depth)
                        elif elem_type:
                            # 名前付き型の処理
                            # 例: <xsd:element name="Item" type="ItemType"/>
                            clean_elem_type = self._remove_ns_prefix(elem_type)

                            # 【組み込み型のスキップ】
                            # xsd:stringなどの組み込み型は子要素や属性を持たないのでスキップ
                            if clean_elem_type not in ['string', 'integer', 'date', 'dateTime',
                                                        'boolean', 'decimal', 'float', 'double',
                                                        'time', 'gYear', 'gYearMonth', 'gMonth',
                                                        'gMonthDay', 'gDay', 'hexBinary', 'base64Binary',
                                                        'anyURI', 'QName', 'NOTATION', 'normalizedString',
                                                        'token', 'language', 'NMTOKEN', 'NMTOKENS',
                                                        'Name', 'NCName', 'ID', 'IDREF', 'IDREFS',
                                                        'ENTITY', 'ENTITIES', 'long', 'int', 'short',
                                                        'byte', 'nonNegativeInteger', 'positiveInteger',
                                                        'unsignedLong', 'unsignedInt', 'unsignedShort',
                                                        'unsignedByte', 'nonPositiveInteger', 'negativeInteger']:
                                # 【再帰的処理】
                                # この要素の型定義を処理（深度+1）
                                # 例: ItemType → SubItem(ItemType) → SubItem(ItemType) → ...
                                self._process_type(elem_type, child_path, depth + 1, max_depth)
                    elif elem_ref:
                        # ref属性で参照される要素の処理
                        ref_name = self._remove_ns_prefix(elem_ref)
                        child_path = f"{current_path}/{ref_name}"
                        self.defined_element_paths.add(child_path)
                        # ref要素の型を探す
                        ref_elements = self.schema_root.findall(f'.//xsd:element[@name="{ref_name}"]', self.ns)
                        for ref_elem in ref_elements:
                            ref_type = ref_elem.get('type')
                            if ref_type:
                                self._process_type(ref_type, child_path, depth + 1, max_depth)
        
        finally:
            self.processing_types.discard(tracking_key)
    
    def _process_inline_type(self, type_elem: etree._Element, current_path: str, depth: int, max_depth: int):
        """インライン（匿名）型定義を処理"""
        
        if depth > max_depth:
            return
        
        # 属性を処理
        for attr in type_elem.findall('./xsd:attribute[@name]', self.ns):
            attr_name = attr.get('name')
            attr_path = f"{current_path}@{attr_name}"
            self.defined_attribute_paths.add(attr_path)
        
        # sequence/choice/all内の要素を処理
        for container in type_elem.findall('.//xsd:sequence', self.ns) + \
                       type_elem.findall('.//xsd:choice', self.ns) + \
                       type_elem.findall('.//xsd:all', self.ns):
            
            for elem in container.findall('./xsd:element', self.ns):
                elem_name = elem.get('name')
                elem_type = elem.get('type')
                
                if elem_name:
                    child_path = f"{current_path}/{elem_name}"
                    self.defined_element_paths.add(child_path)
                    
                    # さらにネストしたインライン型
                    nested_complex_type = elem.find('./xsd:complexType', self.ns)
                    if nested_complex_type is not None:
                        self._process_inline_type(nested_complex_type, child_path, depth + 1, max_depth)
                    elif elem_type:
                        clean_elem_type = self._remove_ns_prefix(elem_type)
                        if clean_elem_type not in ['string', 'integer', 'date', 'dateTime', 'boolean', 'decimal', 'float', 'double']:
                            self._process_type(elem_type, child_path, depth + 1, max_depth)
    
    def get_defined_paths(self) -> Tuple[Set[str], Set[str]]:
        """定義された要素パスと属性パスを返す"""
        return self.defined_element_paths, self.defined_attribute_paths


class XMLCoverageAnalyzer:
    """XMLファイル群を解析して、使用されている要素・属性を抽出"""
    
    def __init__(self, xml_files: List[str]):
        self.xml_files = xml_files
        self.used_element_paths: Set[str] = set()
        self.used_attribute_paths: Set[str] = set()
    
    def analyze(self):
        """すべてのXMLファイルを解析"""
        for xml_file in self.xml_files:
            try:
                tree = etree.parse(xml_file)
                root = tree.getroot()
                self._process_element(root, "")
            except Exception as e:
                print(f"警告: {xml_file} の処理中にエラーが発生しました: {e}", file=sys.stderr)
    
    def _process_element(self, element: etree._Element, parent_path: str):
        """要素とその子要素を再帰的に処理"""
        
        try:
            # 名前空間を除去したタグ名を取得
            tag = etree.QName(element).localname
            
            # 現在の要素のパスを構築
            current_path = f"{parent_path}/{tag}"
            self.used_element_paths.add(current_path)
            
            # 属性を処理
            for attr_name, attr_value in element.attrib.items():
                try:
                    # 名前空間を除去した属性名を取得
                    clean_attr_name = etree.QName(attr_name).localname
                    
                    # xsi:schemaLocationなどの特殊属性をスキップ
                    if clean_attr_name not in ['schemaLocation', 'type', 'nil']:
                        attr_path = f"{current_path}@{clean_attr_name}"
                        self.used_attribute_paths.add(attr_path)
                except Exception as e:
                    # 属性の処理でエラーが発生しても続行
                    pass
            
            # 子要素を再帰的に処理（要素のみ）
            for child in element:
                # ElementノードかTagノードのみを処理
                if isinstance(child.tag, str):
                    self._process_element(child, current_path)
        except Exception as e:
            # 個別の要素の処理でエラーが発生しても続行
            pass
    
    def get_used_paths(self) -> Tuple[Set[str], Set[str]]:
        """使用された要素パスと属性パスを返す"""
        return self.used_element_paths, self.used_attribute_paths


class CoverageReporter:
    """カバレッジレポートを生成"""
    
    def __init__(self, 
                 defined_elements: Set[str], 
                 defined_attributes: Set[str],
                 used_elements: Set[str], 
                 used_attributes: Set[str]):
        self.defined_elements = defined_elements
        self.defined_attributes = defined_attributes
        self.used_elements = used_elements
        self.used_attributes = used_attributes
    
    def generate_report(self) -> str:
        """カバレッジレポートを生成"""
        
        report = []
        report.append("=" * 80)
        report.append("XSDカバレッジレポート（階層構造考慮版）")
        report.append("=" * 80)
        report.append("")
        
        # 要素の集合演算
        covered_elements = self.used_elements & self.defined_elements
        undefined_elements = self.used_elements - self.defined_elements
        
        # 属性の集合演算
        covered_attributes = self.used_attributes & self.defined_attributes
        undefined_attributes = self.used_attributes - self.defined_attributes
        
        # 要素カバレッジ
        element_coverage = self._calculate_coverage(
            self.defined_elements, 
            self.used_elements
        )
        
        report.append("【要素カバレッジ】")
        report.append(f"  XSDで定義された要素パス数: {len(self.defined_elements)}")
        report.append(f"  ├─ XMLで使用されている数: {len(covered_elements)}")
        report.append(f"  └─ XMLで未使用の数: {len(self.defined_elements) - len(covered_elements)}")
        report.append(f"  ")
        report.append(f"  XMLに存在する要素パス総数: {len(self.used_elements)}")
        report.append(f"  ├─ XSDで定義済み: {len(covered_elements)}")
        report.append(f"  └─ XSDで未定義: {len(undefined_elements)}")
        report.append(f"  ")
        report.append(f"  カバレッジ率: {element_coverage:.2f}%")
        report.append(f"  （定義された{len(self.defined_elements)}個のうち{len(covered_elements)}個が使用されている）")
        report.append("")
        
        # 属性カバレッジ
        attribute_coverage = self._calculate_coverage(
            self.defined_attributes, 
            self.used_attributes
        )
        
        report.append("【属性カバレッジ】")
        report.append(f"  XSDで定義された属性パス数: {len(self.defined_attributes)}")
        report.append(f"  ├─ XMLで使用されている数: {len(covered_attributes)}")
        report.append(f"  └─ XMLで未使用の数: {len(self.defined_attributes) - len(covered_attributes)}")
        report.append(f"  ")
        report.append(f"  XMLに存在する属性パス総数: {len(self.used_attributes)}")
        report.append(f"  ├─ XSDで定義済み: {len(covered_attributes)}")
        report.append(f"  └─ XSDで未定義: {len(undefined_attributes)}")
        report.append(f"  ")
        report.append(f"  カバレッジ率: {attribute_coverage:.2f}%")
        report.append(f"  （定義された{len(self.defined_attributes)}個のうち{len(covered_attributes)}個が使用されている）")
        report.append("")
        
        # 総合カバレッジ（修正版）
        total_defined = len(self.defined_elements) + len(self.defined_attributes)
        total_covered = len(covered_elements) + len(covered_attributes)
        total_in_xml = len(self.used_elements) + len(self.used_attributes)
        total_undefined = len(undefined_elements) + len(undefined_attributes)
        total_coverage = (total_covered / total_defined * 100) if total_defined > 0 else 0
        
        report.append("【総合カバレッジ】")
        report.append(f"  XSDで定義された総パス数: {total_defined}")
        report.append(f"  ├─ XMLで使用されている数: {total_covered}")
        report.append(f"  └─ XMLで未使用の数: {total_defined - total_covered}")
        report.append(f"  ")
        report.append(f"  XMLに存在する総パス数: {total_in_xml}")
        report.append(f"  ├─ XSDで定義済み: {total_covered}")
        report.append(f"  └─ XSDで未定義: {total_undefined}")
        report.append(f"  ")
        report.append(f"  カバレッジ率: {total_coverage:.2f}%")
        report.append(f"  （定義された{total_defined}個のうち{total_covered}個が使用されている）")
        report.append("")
        
        # 未使用の要素
        unused_elements = self.defined_elements - self.used_elements
        if unused_elements:
            report.append("【未使用の要素パス】")
            for elem in sorted(unused_elements):
                report.append(f"  - {elem}")
            report.append("")
        
        # 未使用の属性
        unused_attributes = self.defined_attributes - self.used_attributes
        if unused_attributes:
            report.append("【未使用の属性パス】")
            for attr in sorted(unused_attributes):
                report.append(f"  - {attr}")
            report.append("")
        
        # 定義されていないが使用されている要素（エラー検出）
        undefined_elements = self.used_elements - self.defined_elements
        if undefined_elements:
            # 外部名前空間の要素を検出（XML Digital Signatureなど）
            external_ns_elements = {e for e in undefined_elements
                                   if '/Signature/' in e}  # XML Digital Signature (ds:)
            truly_undefined_elements = undefined_elements - external_ns_elements

            # 外部スキーマで定義されている要素
            if external_ns_elements:
                report.append("【情報: 外部スキーマで定義されている要素パス】")
                report.append(f"  件数: {len(external_ns_elements)}個")
                report.append("  （これらはXML Digital Signatureなどの外部スキーマ（xsd:import）で定義されています）")
                report.append("")

                # 最初の50個のみ表示
                max_display = 50
                for i, elem in enumerate(sorted(external_ns_elements), 1):
                    if i <= max_display:
                        report.append(f"  ℹ️  {elem}")
                    else:
                        report.append(f"  ... 他 {len(external_ns_elements) - max_display}個")
                        break
                report.append("")

            # 本当に未定義の要素（エラー）
            if truly_undefined_elements:
                report.append("【警告: XSDで定義されていない要素パス】")
                report.append(f"  件数: {len(truly_undefined_elements)}個")
                report.append("  （これらはXSDにも外部スキーマにも定義されていません）")
                report.append("")

                # 最初の50個のみ表示
                max_display = 50
                for i, elem in enumerate(sorted(truly_undefined_elements), 1):
                    if i <= max_display:
                        report.append(f"  ⚠️  {elem}")
                    else:
                        report.append(f"  ... 他 {len(truly_undefined_elements) - max_display}個")
                        break
                report.append("")

        # 定義されていないが使用されている属性（エラー検出）
        undefined_attributes = self.used_attributes - self.defined_attributes
        if undefined_attributes:
            # 外部名前空間の属性を検出（XML Digital Signatureなど）
            external_ns_attributes = {a for a in undefined_attributes
                                     if '/Signature/' in a}  # XML Digital Signature (ds:)
            truly_undefined_attributes = undefined_attributes - external_ns_attributes

            # 外部スキーマで定義されている属性
            if external_ns_attributes:
                report.append("【情報: 外部スキーマで定義されている属性パス】")
                report.append(f"  件数: {len(external_ns_attributes)}個")
                report.append("  （これらはXML Digital Signatureなどの外部スキーマ（xsd:import）で定義されています）")
                report.append("")

                # 最初の50個のみ表示
                max_display = 50
                for i, attr in enumerate(sorted(external_ns_attributes), 1):
                    if i <= max_display:
                        report.append(f"  ℹ️  {attr}")
                    else:
                        report.append(f"  ... 他 {len(external_ns_attributes) - max_display}個")
                        break
                report.append("")

            # 本当に未定義の属性（エラー）
            if truly_undefined_attributes:
                report.append("【警告: XSDで定義されていない属性パス】")
                report.append(f"  件数: {len(truly_undefined_attributes)}個")
                report.append("  （これらはXSDにも外部スキーマにも定義されていません）")
                report.append("")

                # 最初の50個のみ表示
                max_display = 50
                for i, attr in enumerate(sorted(truly_undefined_attributes), 1):
                    if i <= max_display:
                        report.append(f"  ⚠️  {attr}")
                    else:
                        report.append(f"  ... 他 {len(truly_undefined_attributes) - max_display}個")
                        break
                report.append("")
        
        # 使用されている要素の一覧（最初の100個のみ）
        report.append("【使用されている要素パス一覧】")
        report.append(f"  総数: {len(self.used_elements)}個")
        report.append("")
        
        max_display = 100
        for i, elem in enumerate(sorted(self.used_elements), 1):
            if i <= max_display:
                status = "✓" if elem in self.defined_elements else "✗"
                report.append(f"  {status} {elem}")
            else:
                report.append(f"  ... 他 {len(self.used_elements) - max_display}個（詳細は省略）")
                break
        report.append("")
        
        # 使用されている属性の一覧（最初の100個のみ）
        report.append("【使用されている属性パス一覧】")
        report.append(f"  総数: {len(self.used_attributes)}個")
        report.append("")
        
        max_display = 100
        for i, attr in enumerate(sorted(self.used_attributes), 1):
            if i <= max_display:
                status = "✓" if attr in self.defined_attributes else "✗"
                report.append(f"  {status} {attr}")
            else:
                report.append(f"  ... 他 {len(self.used_attributes) - max_display}個（詳細は省略）")
                break
        report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def _calculate_coverage(self, defined: Set[str], used: Set[str]) -> float:
        """カバレッジ率を計算"""
        if len(defined) == 0:
            return 0.0
        
        covered = len(used & defined)
        return (covered / len(defined)) * 100


def main():
    """メイン処理"""
    
    import argparse
    parser = argparse.ArgumentParser(
        description='XSDカバレッジ分析ツール（階層構造考慮版）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  python xsd_coverage.py schema.xsd sample1.xml sample2.xml
  python xsd_coverage.py schema.xsd *.xml
  python xsd_coverage.py --debug schema.xsd sample.xml
        '''
    )
    parser.add_argument('xsd_file', help='XSDスキーマファイル')
    parser.add_argument('xml_files', nargs='+', help='XMLファイル（複数指定可、ワイルドカード可）')
    parser.add_argument('--debug', action='store_true', help='デバッグ情報を表示')
    parser.add_argument('--max-depth', type=int, default=15, help='最大再帰深度（デフォルト: 15）')
    
    args = parser.parse_args()
    
    xsd_file = args.xsd_file
    xml_files = []
    
    # XMLファイルのリストを展開（ワイルドカード対応）
    for pattern in args.xml_files:
        matched_files = glob.glob(pattern)
        if matched_files:
            xml_files.extend(matched_files)
        else:
            xml_files.append(pattern)
    
    if not xml_files:
        print("エラー: XMLファイルが指定されていません")
        sys.exit(1)
    
    print(f"XSDファイル: {xsd_file}")
    print(f"XMLファイル数: {len(xml_files)}")
    if args.debug:
        print(f"XMLファイル: {', '.join(xml_files)}")
    print(f"最大再帰深度: {args.max_depth}")
    print()
    
    # スキーマを解析
    print("XSDスキーマを解析中...")
    schema_analyzer = SchemaAnalyzer(xsd_file)
    schema_analyzer.analyze(max_recursion_depth=args.max_depth)
    defined_elements, defined_attributes = schema_analyzer.get_defined_paths()
    
    print(f"  定義された要素パス: {len(defined_elements)}")
    print(f"  定義された属性パス: {len(defined_attributes)}")
    
    if args.debug:
        print("\n  キャッシュされた型定義:")
        for type_name in sorted(schema_analyzer.type_cache.keys())[:20]:
            print(f"    - {type_name}")
        if len(schema_analyzer.type_cache) > 20:
            print(f"    ... 他 {len(schema_analyzer.type_cache) - 20}個")
    
    print()
    
    # XMLファイルを解析
    print("XMLファイルを解析中...")
    xml_analyzer = XMLCoverageAnalyzer(xml_files)
    xml_analyzer.analyze()
    used_elements, used_attributes = xml_analyzer.get_used_paths()
    
    print(f"  使用された要素パス: {len(used_elements)}")
    print(f"  使用された属性パス: {len(used_attributes)}")
    print()
    
    # レポートを生成
    reporter = CoverageReporter(
        defined_elements, 
        defined_attributes,
        used_elements, 
        used_attributes
    )
    
    report = reporter.generate_report()
    print(report)
    
    # レポートをファイルに保存
    report_file = "coverage_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nレポートを {report_file} に保存しました")


if __name__ == "__main__":
    main()
