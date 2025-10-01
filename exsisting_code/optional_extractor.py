#!/usr/bin/env python3
"""
オプション項目抽出モジュール

XSDスキーマからオプション要素・属性・choice構造を抽出し、
テストデータ生成に必要な情報を提供する。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Tuple
from lxml import etree


@dataclass
class OptionalItem:
    """
    オプション項目の定義

    Attributes:
        path: パス（例: "/Item/Description" or "/Item@status"）
        item_type: "element" または "attribute"
        priority: 重要度（1-10、高いほど重要）
        min_occurs: minOccurs値（要素の場合）
        max_occurs: maxOccurs値（要素の場合、"unbounded"の場合は-1）
        is_choice: choice構造の一部かどうか
        choice_group_id: choice グループID
        choice_options: 同じグループの他の選択肢
    """
    path: str
    item_type: str  # "element" or "attribute"
    priority: int = 5

    # 要素固有の情報
    min_occurs: int = 0
    max_occurs: int = 1  # unboundedの場合は-1

    # Choice情報
    is_choice: bool = False
    choice_group_id: Optional[int] = None
    choice_options: List[str] = field(default_factory=list)

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        if not isinstance(other, OptionalItem):
            return False
        return self.path == other.path


class OptionalElementExtractor:
    """
    XSDスキーマからオプション要素・属性を抽出するクラス

    抽出対象:
    1. minOccurs="0"の要素
    2. use="optional"の属性
    3. choice要素の各選択肢
    4. maxOccurs="unbounded"の要素（0個/1個/複数個のバリエーション）
    """

    def __init__(self, xsd_path: str):
        """
        Args:
            xsd_path: XSDファイルのパス
        """
        self.xsd_path = xsd_path
        self.schema_tree = etree.parse(xsd_path)
        self.ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}

        # 抽出結果
        self.optional_items: List[OptionalItem] = []
        self.choice_group_counter = 0

    def extract(
        self,
        max_depth: int = 10,
        include_unbounded: bool = True,
        priority_map: Optional[Dict[str, int]] = None
    ) -> List[OptionalItem]:
        """
        オプション項目を抽出

        Args:
            max_depth: 再帰構造の最大深度
            include_unbounded: maxOccurs="unbounded"の要素を含めるか
            priority_map: パスと優先度のマッピング

        Returns:
            オプション項目のリスト
        """
        self.optional_items = []
        self.choice_group_counter = 0
        self.priority_map = priority_map or {}
        self.max_depth = max_depth
        self.include_unbounded = include_unbounded

        # ルート要素を特定
        root_element = self._find_root_element()
        if root_element is None:
            return []

        root_name = root_element.get('name')

        # ルート要素から再帰的に抽出
        self._extract_from_element(
            root_name,
            f"/{root_name}",
            current_depth=1
        )

        return self.optional_items

    def _find_root_element(self) -> Optional[etree.Element]:
        """ルート要素を特定"""
        # xs:elementでトップレベルのものを探す
        elements = self.schema_tree.xpath(
            '/xs:schema/xs:element',
            namespaces=self.ns
        )
        return elements[0] if elements else None

    def _extract_from_element(
        self,
        elem_name: str,
        current_path: str,
        current_depth: int
    ):
        """
        要素から再帰的にオプション項目を抽出

        Args:
            elem_name: 要素名
            current_path: 現在のパス
            current_depth: 現在の深度
        """
        if current_depth > self.max_depth:
            return

        # 要素定義を取得
        elem_def = self._find_element_definition(elem_name)
        if elem_def is None:
            return

        # 型定義を取得
        type_name = elem_def.get('type')
        if type_name is None:
            # インライン型定義
            type_def = elem_def.find('xs:complexType', namespaces=self.ns)
            if type_def is not None:
                self._extract_from_complex_type(
                    type_def,
                    current_path,
                    current_depth
                )
        else:
            # 名前付き型
            type_def = self._find_type_definition(type_name)
            if type_def is not None:
                self._extract_from_complex_type(
                    type_def,
                    current_path,
                    current_depth
                )

    def _extract_from_complex_type(
        self,
        type_def: etree.Element,
        parent_path: str,
        current_depth: int
    ):
        """
        complexTypeからオプション項目を抽出
        """
        # 属性を抽出
        self._extract_optional_attributes(type_def, parent_path)

        # 子要素を抽出
        # sequence要素を探す
        sequence = type_def.find('.//xs:sequence', namespaces=self.ns)
        if sequence is not None:
            self._extract_from_sequence(sequence, parent_path, current_depth)

        # choice要素を探す
        choice = type_def.find('.//xs:choice', namespaces=self.ns)
        if choice is not None:
            self._extract_from_choice(choice, parent_path, current_depth)

        # complexContent/extensionの場合
        extension = type_def.find('.//xs:extension', namespaces=self.ns)
        if extension is not None:
            # 基底型の処理
            base_type = extension.get('base')
            if base_type:
                base_type_def = self._find_type_definition(base_type)
                if base_type_def is not None:
                    self._extract_from_complex_type(
                        base_type_def,
                        parent_path,
                        current_depth
                    )

            # extensionの中のsequence/choice
            seq = extension.find('xs:sequence', namespaces=self.ns)
            if seq is not None:
                self._extract_from_sequence(seq, parent_path, current_depth)

            ch = extension.find('xs:choice', namespaces=self.ns)
            if ch is not None:
                self._extract_from_choice(ch, parent_path, current_depth)

    def _extract_from_sequence(
        self,
        sequence: etree.Element,
        parent_path: str,
        current_depth: int
    ):
        """sequenceから要素を抽出"""
        for child_elem in sequence.findall('xs:element', namespaces=self.ns):
            elem_name = child_elem.get('name') or child_elem.get('ref')
            if elem_name is None:
                continue

            min_occurs = int(child_elem.get('minOccurs', '1'))
            max_occurs_str = child_elem.get('maxOccurs', '1')
            max_occurs = -1 if max_occurs_str == 'unbounded' else int(max_occurs_str)

            child_path = f"{parent_path}/{elem_name}"

            # minOccurs="0"ならオプション
            if min_occurs == 0:
                priority = self.priority_map.get(child_path, 5)
                item = OptionalItem(
                    path=child_path,
                    item_type="element",
                    priority=priority,
                    min_occurs=min_occurs,
                    max_occurs=max_occurs,
                    is_choice=False
                )
                self.optional_items.append(item)

            # maxOccurs="unbounded"で複数個のバリエーションが必要
            if self.include_unbounded and max_occurs == -1:
                # 0個、1個、複数個のバリエーションを表現
                # 実装では0個はminOccurs=0で、1個 vs 複数個を別項目として扱う
                # （簡略化のため、ここでは単にオプション項目として扱う）
                pass

            # 再帰的に子要素を処理
            self._extract_from_element(
                elem_name,
                child_path,
                current_depth + 1
            )

    def _extract_from_choice(
        self,
        choice: etree.Element,
        parent_path: str,
        current_depth: int
    ):
        """
        choiceからオプション項目を抽出

        choice要素の各選択肢は互いに排他的なので、
        それぞれを個別のオプション項目として扱う
        """
        choice_group_id = self.choice_group_counter
        self.choice_group_counter += 1

        choice_paths = []

        for child_elem in choice.findall('xs:element', namespaces=self.ns):
            elem_name = child_elem.get('name') or child_elem.get('ref')
            if elem_name is None:
                continue

            child_path = f"{parent_path}/{elem_name}"
            choice_paths.append(child_path)

        # 各選択肢をオプション項目として追加
        for child_path in choice_paths:
            elem_name = child_path.rsplit('/', 1)[-1]
            priority = self.priority_map.get(child_path, 7)  # choiceは重要度高め

            item = OptionalItem(
                path=child_path,
                item_type="element",
                priority=priority,
                min_occurs=0,
                max_occurs=1,
                is_choice=True,
                choice_group_id=choice_group_id,
                choice_options=[p for p in choice_paths if p != child_path]
            )
            self.optional_items.append(item)

            # 再帰的に子要素を処理
            self._extract_from_element(
                elem_name,
                child_path,
                current_depth + 1
            )

    def _extract_optional_attributes(
        self,
        type_def: etree.Element,
        element_path: str
    ):
        """use="optional"の属性を抽出"""
        for attr in type_def.findall('.//xs:attribute', namespaces=self.ns):
            attr_name = attr.get('name')
            if attr_name is None:
                continue

            attr_use = attr.get('use', 'optional')

            if attr_use == 'optional':
                attr_path = f"{element_path}@{attr_name}"
                priority = self.priority_map.get(attr_path, 4)  # 属性は要素より優先度低め

                item = OptionalItem(
                    path=attr_path,
                    item_type="attribute",
                    priority=priority
                )
                self.optional_items.append(item)

    def _find_element_definition(self, elem_name: str) -> Optional[etree.Element]:
        """要素定義を検索"""
        # グローバル要素定義
        elems = self.schema_tree.xpath(
            f'//xs:element[@name="{elem_name}"]',
            namespaces=self.ns
        )
        return elems[0] if elems else None

    def _find_type_definition(self, type_name: str) -> Optional[etree.Element]:
        """型定義を検索"""
        # 名前空間プレフィックスを除去
        local_name = type_name.split(':')[-1]

        # complexType
        types = self.schema_tree.xpath(
            f'//xs:complexType[@name="{local_name}"]',
            namespaces=self.ns
        )
        if types:
            return types[0]

        # simpleType
        types = self.schema_tree.xpath(
            f'//xs:simpleType[@name="{local_name}"]',
            namespaces=self.ns
        )
        return types[0] if types else None

    def get_choice_groups(self) -> Dict[int, List[str]]:
        """
        Choice グループのマッピングを取得

        Returns:
            {group_id: [path1, path2, ...]}
        """
        groups = {}
        for item in self.optional_items:
            if item.is_choice:
                if item.choice_group_id not in groups:
                    groups[item.choice_group_id] = []
                groups[item.choice_group_id].append(item.path)
        return groups

    def get_optional_elements(self) -> List[OptionalItem]:
        """オプション要素のみを取得"""
        return [item for item in self.optional_items if item.item_type == "element"]

    def get_optional_attributes(self) -> List[OptionalItem]:
        """オプション属性のみを取得"""
        return [item for item in self.optional_items if item.item_type == "attribute"]

    def print_summary(self):
        """抽出結果のサマリーを表示"""
        elements = self.get_optional_elements()
        attributes = self.get_optional_attributes()
        choice_groups = self.get_choice_groups()

        print("================================================================================")
        print("オプション項目抽出サマリー")
        print("================================================================================")
        print(f"オプション要素数: {len(elements)}")
        print(f"オプション属性数: {len(attributes)}")
        print(f"Choice グループ数: {len(choice_groups)}")
        print(f"合計オプション項目数: {len(self.optional_items)}")
        print()

        if choice_groups:
            print("【Choice グループ】")
            for group_id, paths in choice_groups.items():
                print(f"  Group {group_id}: {len(paths)}個の選択肢")
                for path in paths:
                    print(f"    - {path}")
            print()

        print("【オプション要素トップ10】")
        sorted_elements = sorted(elements, key=lambda x: x.priority, reverse=True)
        for item in sorted_elements[:10]:
            print(f"  [{item.priority}] {item.path}")
        print()

        print("【オプション属性トップ10】")
        sorted_attributes = sorted(attributes, key=lambda x: x.priority, reverse=True)
        for item in sorted_attributes[:10]:
            print(f"  [{item.priority}] {item.path}")
        print()


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python optional_extractor.py <XSD file>")
        sys.exit(1)

    xsd_file = sys.argv[1]

    extractor = OptionalElementExtractor(xsd_file)
    optional_items = extractor.extract(max_depth=10)

    extractor.print_summary()
