#!/usr/bin/env python3
"""
ペアワイズXMLビルダー

テストパターンに従ってXMLを構築するモジュール。
オプション要素・属性の有無をパターンで制御する。
"""

import sys
import os
from lxml import etree
from typing import Dict, Optional, Set
from xml_generator import XMLGenerator
from pairwise_generator import TestPattern


class PairwiseXMLBuilder:
    """
    ペアワイズテストパターンからXMLを構築するクラス

    既存のXMLGeneratorを活用し、パターンに従って
    オプション要素・属性を選択的に含める。
    """

    def __init__(
        self,
        xsd_path: str,
        max_depth: int = 10,
        namespace_map: Optional[Dict[str, str]] = None
    ):
        """
        Args:
            xsd_path: XSDファイルのパス
            max_depth: 再帰構造の最大深度
            namespace_map: 名前空間マッピング
        """
        self.xsd_path = xsd_path
        self.max_depth = max_depth
        self.namespace_map = namespace_map or {}

        # XMLGeneratorを初期化（基礎となるXML生成機能を提供）
        self.xml_generator = XMLGenerator(
            xsd_path,
            max_depth=max_depth,
            namespace_map=namespace_map
        )

        # SchemaAnalyzerから情報を取得
        self.schema_analyzer = self.xml_generator.schema_analyzer
        self.schema_tree = self.xml_generator.schema_tree
        self.type_cache = self.xml_generator.type_cache

        # 名前空間定義
        self.ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}

        # ルート要素を特定
        self.root_elem_name = self._find_root_element()

    def build_xml(self, pattern: TestPattern) -> etree.Element:
        """
        テストパターンからXMLを構築

        Args:
            pattern: テストパターン（オプション項目の有効/無効）

        Returns:
            XMLルート要素
        """
        # パターンを元に、どのパスを含めるかのセットを作成
        included_paths = {
            path for path, include in pattern.assignments.items() if include
        }

        # ルート要素を構築
        root_elem = self._build_element_with_pattern(
            elem_name=self.root_elem_name,
            current_path=f"/{self.root_elem_name}",
            current_depth=1,
            included_paths=included_paths
        )

        return root_elem

    def _build_element_with_pattern(
        self,
        elem_name: str,
        current_path: str,
        current_depth: int,
        included_paths: Set[str]
    ) -> Optional[etree.Element]:
        """
        パターンに従って要素を構築

        Args:
            elem_name: 要素名
            current_path: 現在のパス
            current_depth: 現在の深度
            included_paths: 含めるべきパスの集合

        Returns:
            lxml Element または None
        """
        if current_depth > self.max_depth:
            return None

        # 名前空間を考慮して要素を作成
        qname = etree.QName(self.namespace_map.get('ns', ''), elem_name)
        elem = etree.Element(qname)

        # 要素定義を取得
        elem_def = self._find_element_definition(elem_name)
        if elem_def is None:
            # 定義が見つからない場合、デフォルトの要素を返す
            elem.text = "sample_text"
            return elem

        # 型を取得
        type_name = elem_def.get('type')
        if type_name is None:
            # インライン型定義
            type_def = elem_def.find('xs:complexType', namespaces=self.ns)
        else:
            type_def = self._find_type_definition(type_name)

        if type_def is None:
            # simpleTypeの場合、テキストを設定
            elem.text = "sample_text"
            return elem

        # 属性を追加（パターンに従って）
        self._add_attributes_with_pattern(
            elem,
            type_def,
            current_path,
            included_paths
        )

        # 子要素を追加（パターンに従って）
        self._add_child_elements_with_pattern(
            elem,
            type_def,
            current_path,
            current_depth,
            included_paths
        )

        return elem

    def _add_attributes_with_pattern(
        self,
        elem: etree.Element,
        type_def: etree.Element,
        element_path: str,
        included_paths: Set[str]
    ):
        """パターンに従って属性を追加"""
        # 属性定義を取得
        for attr in type_def.findall('.//xs:attribute', namespaces=self.ns):
            attr_name = attr.get('name')
            if attr_name is None:
                continue

            attr_path = f"{element_path}@{attr_name}"
            attr_use = attr.get('use', 'optional')

            # 必須属性、またはパターンに含まれるオプション属性
            if attr_use == 'required' or attr_path in included_paths:
                # ダミー値を設定
                attr_type = attr.get('type', 'xs:string')
                dummy_value = self._generate_dummy_value(attr_name, attr_type)
                elem.set(attr_name, dummy_value)

    def _add_child_elements_with_pattern(
        self,
        parent_elem: etree.Element,
        type_def: etree.Element,
        parent_path: str,
        current_depth: int,
        included_paths: Set[str]
    ):
        """パターンに従って子要素を追加"""
        # sequence要素を探す
        sequence = type_def.find('.//xs:sequence', namespaces=self.ns)
        if sequence is not None:
            self._process_sequence_with_pattern(
                parent_elem,
                sequence,
                parent_path,
                current_depth,
                included_paths
            )

        # choice要素を探す
        choice = type_def.find('.//xs:choice', namespaces=self.ns)
        if choice is not None:
            self._process_choice_with_pattern(
                parent_elem,
                choice,
                parent_path,
                current_depth,
                included_paths
            )

        # complexContent/extensionの場合
        extension = type_def.find('.//xs:extension', namespaces=self.ns)
        if extension is not None:
            # 基底型の処理
            base_type = extension.get('base')
            if base_type:
                base_type_def = self._find_type_definition(base_type)
                if base_type_def is not None:
                    self._add_child_elements_with_pattern(
                        parent_elem,
                        base_type_def,
                        parent_path,
                        current_depth,
                        included_paths
                    )

            # extensionの中のsequence/choice
            seq = extension.find('xs:sequence', namespaces=self.ns)
            if seq is not None:
                self._process_sequence_with_pattern(
                    parent_elem,
                    seq,
                    parent_path,
                    current_depth,
                    included_paths
                )

            ch = extension.find('xs:choice', namespaces=self.ns)
            if ch is not None:
                self._process_choice_with_pattern(
                    parent_elem,
                    ch,
                    parent_path,
                    current_depth,
                    included_paths
                )

    def _process_sequence_with_pattern(
        self,
        parent_elem: etree.Element,
        sequence: etree.Element,
        parent_path: str,
        current_depth: int,
        included_paths: Set[str]
    ):
        """sequenceの子要素を処理"""
        for child_elem_def in sequence.findall('xs:element', namespaces=self.ns):
            child_name = child_elem_def.get('name') or child_elem_def.get('ref')
            if child_name is None:
                continue

            child_path = f"{parent_path}/{child_name}"
            min_occurs = int(child_elem_def.get('minOccurs', '1'))

            # 必須要素、またはパターンに含まれるオプション要素
            if min_occurs >= 1 or child_path in included_paths:
                child_elem = self._build_element_with_pattern(
                    child_name,
                    child_path,
                    current_depth + 1,
                    included_paths
                )
                if child_elem is not None:
                    parent_elem.append(child_elem)

    def _process_choice_with_pattern(
        self,
        parent_elem: etree.Element,
        choice: etree.Element,
        parent_path: str,
        current_depth: int,
        included_paths: Set[str]
    ):
        """choiceの子要素を処理（パターンで指定されたものだけ）"""
        for child_elem_def in choice.findall('xs:element', namespaces=self.ns):
            child_name = child_elem_def.get('name') or child_elem_def.get('ref')
            if child_name is None:
                continue

            child_path = f"{parent_path}/{child_name}"

            # パターンに含まれる選択肢のみ追加
            if child_path in included_paths:
                child_elem = self._build_element_with_pattern(
                    child_name,
                    child_path,
                    current_depth + 1,
                    included_paths
                )
                if child_elem is not None:
                    parent_elem.append(child_elem)
                    # choiceは1つだけ選択するのでbreak
                    break

    def _find_root_element(self) -> str:
        """ルート要素名を取得"""
        root_elems = self.schema_tree.xpath(
            '/xs:schema/xs:element',
            namespaces=self.ns
        )
        if root_elems:
            return root_elems[0].get('name')
        return "Root"

    def _find_element_definition(self, elem_name: str) -> Optional[etree.Element]:
        """要素定義を検索"""
        elems = self.schema_tree.xpath(
            f'//xs:element[@name="{elem_name}"]',
            namespaces=self.ns
        )
        return elems[0] if elems else None

    def _find_type_definition(self, type_name: str) -> Optional[etree.Element]:
        """型定義を検索"""
        local_name = type_name.split(':')[-1]

        # キャッシュを確認
        if local_name in self.type_cache:
            return self.type_cache[local_name]

        # complexType
        types = self.schema_tree.xpath(
            f'//xs:complexType[@name="{local_name}"]',
            namespaces=self.ns
        )
        if types:
            self.type_cache[local_name] = types[0]
            return types[0]

        # simpleType
        types = self.schema_tree.xpath(
            f'//xs:simpleType[@name="{local_name}"]',
            namespaces=self.ns
        )
        if types:
            self.type_cache[local_name] = types[0]
            return types[0]

        return None

    def _generate_dummy_value(self, name: str, attr_type: str) -> str:
        """ダミー値を生成"""
        # 型に応じたダミー値
        type_mapping = {
            'xs:string': f'{name}_value',
            'xs:int': '1',
            'xs:integer': '1',
            'xs:decimal': '1.0',
            'xs:boolean': 'true',
            'xs:date': '2024-01-01',
            'xs:dateTime': '2024-01-01T00:00:00',
        }

        local_type = attr_type.split(':')[-1] if ':' in attr_type else attr_type
        return type_mapping.get(f'xs:{local_type}', f'{name}_value')
