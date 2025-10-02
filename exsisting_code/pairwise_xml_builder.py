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

        # XSDを解析
        with open(xsd_path, 'r', encoding='utf-8') as f:
            self.schema_tree = etree.parse(f)

        # 名前空間定義（XSD namespace prefix自動検出）
        root = self.schema_tree.getroot()
        self.xsd_prefix = None
        for prefix, ns_uri in root.nsmap.items():
            if ns_uri == 'http://www.w3.org/2001/XMLSchema':
                self.xsd_prefix = prefix if prefix else 'xs'
                break
        if not self.xsd_prefix:
            self.xsd_prefix = 'xs'  # デフォルト
        self.ns = {self.xsd_prefix: 'http://www.w3.org/2001/XMLSchema'}

        # ターゲット名前空間を取得
        target_ns = root.get('targetNamespace')
        if not namespace_map:
            namespace_map = {}
        if target_ns and 'ns' not in namespace_map:
            namespace_map['ns'] = target_ns
        self.namespace_map = namespace_map

        # XMLGeneratorを初期化（基礎となるXML生成機能を提供）
        self.xml_generator = XMLGenerator(
            xsd_path,
            max_depth=max_depth,
            namespace_map=self.namespace_map
        )

        # SchemaAnalyzerから情報を取得
        self.schema_analyzer = self.xml_generator.schema_analyzer
        self.type_cache = self.xml_generator.type_cache

        # ルート要素を特定
        self.root_elem_name = self._find_root_element()
        if not self.root_elem_name:
            raise ValueError("Could not find root element in XSD")

        # パターンに含まれるオプションパス（初期化）
        self.optional_paths_in_pattern = set()

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

        # パターンに含まれていないパスは必須として扱う
        # （大規模スキーマでサンプリングされた場合の対応）
        self.optional_paths_in_pattern = set(pattern.assignments.keys())

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
        # elem_nameが空でないことを確認
        if not elem_name:
            return None

        # 名前空間プレフィックスを除去（refの場合）
        if ':' in elem_name:
            elem_name = elem_name.split(':', 1)[1]

        if not elem_name:  # 再確認
            return None

        try:
            qname = etree.QName(self.namespace_map.get('ns', ''), elem_name)
            elem = etree.Element(qname)
        except ValueError as e:
            print(f"Error creating element '{elem_name}': {e}")
            return None

        # 要素定義を取得
        elem_def = self._find_element_definition(elem_name)
        if elem_def is None:
            # 定義が見つからない場合、デフォルトの要素を返す（空のまま）
            return elem

        # 型を取得
        type_name = elem_def.get('type')
        if type_name is None:
            # インライン型定義
            type_def = elem_def.find(f'{self.xsd_prefix}:complexType', namespaces=self.ns)
            # インラインsimpleTypeもチェック
            if type_def is None:
                simple_type_def = elem_def.find(f'{self.xsd_prefix}:simpleType', namespaces=self.ns)
                if simple_type_def is not None:
                    # インラインsimpleTypeの場合、テキストを設定
                    elem.text = self._generate_text_value(elem_name, 'xs:string')
                    return elem
        else:
            # 外部名前空間の型（ds:SignatureTypeなど）はサポートしない
            if type_name and ':' in type_name and not type_name.startswith('xs:') and not type_name.startswith('xsd:'):
                # Signature要素の特別処理
                if elem_name == 'Signature' and type_name == 'ds:SignatureType':
                    # XML Signatureの最小限の必須構造を追加
                    ds_ns = 'http://www.w3.org/2000/09/xmldsig#'

                    # SignedInfo要素とその必須子要素
                    signed_info = etree.Element(etree.QName(ds_ns, 'SignedInfo'))

                    # CanonicalizationMethod（必須）
                    canon_method = etree.Element(etree.QName(ds_ns, 'CanonicalizationMethod'))
                    canon_method.set('Algorithm', 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
                    signed_info.append(canon_method)

                    # SignatureMethod（必須）
                    sig_method = etree.Element(etree.QName(ds_ns, 'SignatureMethod'))
                    sig_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#rsa-sha1')
                    signed_info.append(sig_method)

                    # Reference（必須）
                    reference = etree.Element(etree.QName(ds_ns, 'Reference'))
                    reference.set('URI', '')

                    # Transforms（必須）
                    transforms = etree.Element(etree.QName(ds_ns, 'Transforms'))
                    transform = etree.Element(etree.QName(ds_ns, 'Transform'))
                    transform.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#enveloped-signature')
                    transforms.append(transform)
                    reference.append(transforms)

                    # DigestMethod（必須）
                    digest_method = etree.Element(etree.QName(ds_ns, 'DigestMethod'))
                    digest_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
                    reference.append(digest_method)

                    # DigestValue（必須）
                    digest_value = etree.Element(etree.QName(ds_ns, 'DigestValue'))
                    digest_value.text = 'U2FtcGxlRGlnZXN0VmFsdWU='  # Valid base64
                    reference.append(digest_value)

                    signed_info.append(reference)
                    elem.append(signed_info)

                    # SignatureValue（必須）
                    sig_value = etree.Element(etree.QName(ds_ns, 'SignatureValue'))
                    sig_value.text = 'U2FtcGxlU2lnbmF0dXJlVmFsdWU='  # Valid base64
                    elem.append(sig_value)

                    return elem
                # その他の外部名前空間の型は処理できないため、空要素を返す
                return elem

            type_def = self._find_type_definition(type_name)

        if type_def is None:
            # simpleTypeの場合（型名が指定されているが定義が見つからない）
            # 型名を使ってテキストを生成
            if type_name and (type_name.startswith('xs:') or type_name.startswith('xsd:')):
                elem.text = self._generate_text_value(elem_name, type_name)
            # 外部名前空間や不明な型の場合は空要素のまま
            return elem

        # 属性を追加（パターンに従って）- 必須属性を含む
        self._add_attributes_with_pattern(
            elem,
            type_def,
            current_path,
            included_paths
        )

        # complexTypeの内容モデルを詳細にチェック
        # 直接の子要素をチェック（深い階層は見ない）
        has_sequence = type_def.find(f'{self.xsd_prefix}:sequence', namespaces=self.ns) is not None
        has_choice = type_def.find(f'{self.xsd_prefix}:choice', namespaces=self.ns) is not None
        has_all = type_def.find(f'{self.xsd_prefix}:all', namespaces=self.ns) is not None
        has_simple_content = type_def.find(f'{self.xsd_prefix}:simpleContent', namespaces=self.ns) is not None
        has_complex_content = type_def.find(f'{self.xsd_prefix}:complexContent', namespaces=self.ns) is not None

        # complexContent/extensionの中も確認
        if has_complex_content:
            extension = type_def.find(f'.//{self.xsd_prefix}:extension', namespaces=self.ns)
            if extension is not None:
                has_sequence = has_sequence or extension.find(f'{self.xsd_prefix}:sequence', namespaces=self.ns) is not None
                has_choice = has_choice or extension.find(f'{self.xsd_prefix}:choice', namespaces=self.ns) is not None
                has_all = has_all or extension.find(f'{self.xsd_prefix}:all', namespaces=self.ns) is not None

        # コンテンツモデルに基づいて処理
        if has_sequence or has_choice or has_all:
            # element-only content: 子要素を追加
            self._add_child_elements_with_pattern(
                elem,
                type_def,
                current_path,
                current_depth,
                included_paths
            )
        elif has_simple_content:
            # simpleContent: テキスト値を設定
            # simpleContentの基底型を確認
            extension = type_def.find(f'.//{self.xsd_prefix}:simpleContent/{self.xsd_prefix}:extension', namespaces=self.ns)
            if extension is not None:
                base_type = extension.get('base', 'xs:string')
                elem.text = self._generate_text_value(elem_name, base_type)
            else:
                elem.text = self._generate_text_value(elem_name, 'xs:string')
        elif has_complex_content:
            # complexContent with no child elements = empty content
            # Do nothing (no text)
            pass
        else:
            # No content model elements = empty content (attributes only)
            # Do nothing (no text)
            pass

        return elem

    def _add_required_children_minimal(
        self,
        parent_elem: etree.Element,
        type_def: etree.Element,
        recursion_level: int = 0
    ):
        """必須子要素のみを追加（max_depth時の最小限処理）"""
        # 深すぎる再帰を防ぐ
        if recursion_level > 2:
            return

        # sequence内の必須要素を探す
        for sequence in type_def.findall(f'.//{self.xsd_prefix}:sequence', namespaces=self.ns):
            for child_elem_def in sequence.findall(f'{self.xsd_prefix}:element', namespaces=self.ns):
                min_occurs = int(child_elem_def.get('minOccurs', '1'))
                if min_occurs >= 1:
                    # 必須要素を追加
                    child_name = child_elem_def.get('name') or child_elem_def.get('ref')
                    if not child_name:
                        continue

                    # Signature要素は複雑なXML Digital Signature構造なのでスキップ
                    if child_name == 'Signature' or child_name.endswith(':Signature'):
                        continue

                    # refの場合、名前空間プレフィックスを除去
                    if ':' in child_name:
                        child_name = child_name.split(':', 1)[1]

                    ns = self.namespace_map.get('ns', '')
                    qname = etree.QName(ns, child_name)
                    child_elem = etree.Element(qname)

                    # 子要素の型を確認
                    child_elem_definition = self._find_element_definition(child_name)
                    if child_elem_definition is not None:
                        child_type_name = child_elem_definition.get('type')
                        if child_type_name:
                            if not child_type_name.startswith('xs:') and not child_type_name.startswith('xsd:'):
                                # complexTypeの場合、その必須属性と子要素を追加（再帰レベル制限）
                                child_type_def = self._find_type_definition(child_type_name)
                                if child_type_def is not None:
                                    self._add_required_attributes_only(child_elem, child_type_def)
                                    if recursion_level < 2:
                                        self._add_required_children_minimal(child_elem, child_type_def, recursion_level + 1)
                            else:
                                # simpleTypeの場合、テキストを設定
                                child_elem.text = self._generate_text_value(child_name, child_type_name)

                    parent_elem.append(child_elem)

        # complexContent/extensionの場合、基底型の必須要素も処理
        extension = type_def.find(f'.//{self.xsd_prefix}:extension', namespaces=self.ns)
        if extension is not None:
            # extensionの中のsequence
            for sequence in extension.findall(f'{self.xsd_prefix}:sequence', namespaces=self.ns):
                for child_elem_def in sequence.findall(f'{self.xsd_prefix}:element', namespaces=self.ns):
                    min_occurs = int(child_elem_def.get('minOccurs', '1'))
                    if min_occurs >= 1:
                        child_name = child_elem_def.get('name') or child_elem_def.get('ref')
                        if not child_name:
                            continue

                        if ':' in child_name:
                            child_name = child_name.split(':', 1)[1]

                        ns = self.namespace_map.get('ns', '')
                        qname = etree.QName(ns, child_name)
                        child_elem = etree.Element(qname)

                        # 子要素の型を確認して適切な内容を設定
                        child_elem_definition = self._find_element_definition(child_name)
                        if child_elem_definition is not None:
                            child_type_name = child_elem_definition.get('type')
                            if child_type_name:
                                if not child_type_name.startswith('xs:') and not child_type_name.startswith('xsd:'):
                                    child_type_def = self._find_type_definition(child_type_name)
                                    if child_type_def is not None:
                                        self._add_required_attributes_only(child_elem, child_type_def)
                                        if recursion_level < 2:
                                            self._add_required_children_minimal(child_elem, child_type_def, recursion_level + 1)
                                else:
                                    child_elem.text = self._generate_text_value(child_name, child_type_name)

                        parent_elem.append(child_elem)

    def _add_required_attributes_only(
        self,
        elem: etree.Element,
        type_def: etree.Element
    ):
        """必須属性のみを追加（max_depth時の簡易処理）"""
        # 直接の属性定義を取得
        for attr in type_def.findall(f'{self.xsd_prefix}:attribute', namespaces=self.ns):
            attr_use = attr.get('use', 'optional')
            if attr_use == 'required':
                attr_name = attr.get('name')
                if attr_name:
                    attr_type = attr.get('type', 'xs:string')
                    dummy_value = self._generate_dummy_value(attr_name, attr_type)
                    elem.set(attr_name, dummy_value)

        # complexContent/extension からの属性も取得
        extension = type_def.find(f'.//{self.xsd_prefix}:extension', namespaces=self.ns)
        if extension is not None:
            # extensionの属性
            for attr in extension.findall(f'{self.xsd_prefix}:attribute', namespaces=self.ns):
                attr_use = attr.get('use', 'optional')
                if attr_use == 'required':
                    attr_name = attr.get('name')
                    if attr_name:
                        attr_type = attr.get('type', 'xs:string')
                        dummy_value = self._generate_dummy_value(attr_name, attr_type)
                        elem.set(attr_name, dummy_value)

            # 基底型の必須属性も再帰的に追加
            base_type = extension.get('base')
            if base_type and not base_type.startswith('xs:'):
                base_type_def = self._find_type_definition(base_type)
                if base_type_def is not None:
                    self._add_required_attributes_only(elem, base_type_def)

        # simpleContent/extension からの属性も取得
        simple_extension = type_def.find(f'.//{self.xsd_prefix}:simpleContent/{self.xsd_prefix}:extension', namespaces=self.ns)
        if simple_extension is not None:
            for attr in simple_extension.findall(f'{self.xsd_prefix}:attribute', namespaces=self.ns):
                attr_use = attr.get('use', 'optional')
                if attr_use == 'required':
                    attr_name = attr.get('name')
                    if attr_name:
                        attr_type = attr.get('type', 'xs:string')
                        dummy_value = self._generate_dummy_value(attr_name, attr_type)
                        elem.set(attr_name, dummy_value)

    def _add_attributes_with_pattern(
        self,
        elem: etree.Element,
        type_def: etree.Element,
        element_path: str,
        included_paths: Set[str]
    ):
        """パターンに従って属性を追加（必須属性も含む）"""
        # 直接定義されている属性
        attrs_to_add = []

        # 直接の属性定義を取得
        for attr in type_def.findall(f'{self.xsd_prefix}:attribute', namespaces=self.ns):
            attrs_to_add.append(attr)

        # complexContent/extension からの属性も取得
        extension = type_def.find(f'.//{self.xsd_prefix}:extension', namespaces=self.ns)
        if extension is not None:
            # extensionの属性
            for attr in extension.findall(f'{self.xsd_prefix}:attribute', namespaces=self.ns):
                attrs_to_add.append(attr)

            # 基底型の属性も再帰的に追加
            base_type = extension.get('base')
            if base_type and not base_type.startswith('xs:'):
                base_type_def = self._find_type_definition(base_type)
                if base_type_def is not None:
                    # 基底型の属性も追加
                    self._add_attributes_with_pattern(
                        elem,
                        base_type_def,
                        element_path,
                        included_paths
                    )

        # simpleContent/extension からの属性も取得
        simple_extension = type_def.find(f'.//{self.xsd_prefix}:simpleContent/{self.xsd_prefix}:extension', namespaces=self.ns)
        if simple_extension is not None:
            for attr in simple_extension.findall(f'{self.xsd_prefix}:attribute', namespaces=self.ns):
                attrs_to_add.append(attr)

        # 属性を処理
        for attr in attrs_to_add:
            attr_name = attr.get('name')
            if attr_name is None:
                continue

            attr_path = f"{element_path}@{attr_name}"
            attr_use = attr.get('use', 'optional')

            # パターンに含まれていない属性は必須として扱う
            is_in_pattern = attr_path in self.optional_paths_in_pattern
            is_included_in_pattern = attr_path in included_paths

            # 以下の場合に属性を追加:
            # 1. 必須属性（use='required'）
            # 2. パターンに含まれていない（サンプリングで除外された）
            # 3. パターンでTrueと指定されている
            if attr_use == 'required' or not is_in_pattern or is_included_in_pattern:
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
        sequence = type_def.find(f'.//{self.xsd_prefix}:sequence', namespaces=self.ns)
        if sequence is not None:
            self._process_sequence_with_pattern(
                parent_elem,
                sequence,
                parent_path,
                current_depth,
                included_paths
            )

        # choice要素を探す
        choice = type_def.find(f'.//{self.xsd_prefix}:choice', namespaces=self.ns)
        if choice is not None:
            self._process_choice_with_pattern(
                parent_elem,
                choice,
                parent_path,
                current_depth,
                included_paths
            )

        # complexContent/extensionの場合
        extension = type_def.find(f'.//{self.xsd_prefix}:extension', namespaces=self.ns)
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
            seq = extension.find(f'{self.xsd_prefix}:sequence', namespaces=self.ns)
            if seq is not None:
                self._process_sequence_with_pattern(
                    parent_elem,
                    seq,
                    parent_path,
                    current_depth,
                    included_paths
                )

            ch = extension.find(f'{self.xsd_prefix}:choice', namespaces=self.ns)
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
        for child_elem_def in sequence.findall(f'{self.xsd_prefix}:element', namespaces=self.ns):
            child_name = child_elem_def.get('name') or child_elem_def.get('ref')
            if child_name is None:
                continue

            # refの場合、名前空間も考慮
            if child_elem_def.get('ref') and ':' in child_name:
                # 名前空間プレフィックスを処理
                prefix, local_name = child_name.split(':', 1)
                # localNameが空でないことを確認
                if local_name:
                    child_name = local_name

            child_path = f"{parent_path}/{child_name}"
            min_occurs = int(child_elem_def.get('minOccurs', '1'))

            # パターンに含まれていないパスは必須として扱う
            is_in_pattern = child_path in self.optional_paths_in_pattern
            is_included_in_pattern = child_path in included_paths

            # 以下の場合に要素を追加:
            # 1. 必須要素（minOccurs >= 1）
            # 2. パターンに含まれていない（サンプリングで除外された）
            # 3. パターンでTrueと指定されている
            if min_occurs >= 1 or not is_in_pattern or is_included_in_pattern:
                child_elem = self._build_element_with_pattern(
                    child_name,
                    child_path,
                    current_depth + 1,
                    included_paths
                )
                if child_elem is not None:
                    parent_elem.append(child_elem)
                elif min_occurs >= 1 and current_depth + 1 > self.max_depth:
                    # 必須要素だが max_depth に達した場合、最小限の要素を追加
                    # 名前空間を適切に設定
                    ns = self.namespace_map.get('ns', '')
                    if child_elem_def.get('ref') and ':' in child_elem_def.get('ref'):
                        # refで別の名前空間を参照している可能性
                        ref = child_elem_def.get('ref')
                        if ref.startswith('ds:'):
                            # XML Signature namespace
                            ns = 'http://www.w3.org/2000/09/xmldsig#'

                    qname = etree.QName(ns, child_name)
                    simple_elem = etree.Element(qname)

                    # 型を確認して適切な内容と必須属性を設定
                    elem_def = self._find_element_definition(child_name)
                    if elem_def is not None:
                        type_name = elem_def.get('type')
                        if type_name and not type_name.startswith('xs:'):
                            # complexTypeの場合 - 必須属性と必須子要素を追加
                            type_def = self._find_type_definition(type_name)
                            if type_def is not None:
                                # 必須属性のみを追加（簡易版）
                                self._add_required_attributes_only(simple_elem, type_def)
                                # 必須子要素も追加（1レベルのみ）
                                self._add_required_children_minimal(simple_elem, type_def)
                        elif type_name:
                            # simpleTypeの場合、テキストを設定
                            simple_elem.text = self._generate_text_value(child_name, type_name)
                    parent_elem.append(simple_elem)

    def _process_choice_with_pattern(
        self,
        parent_elem: etree.Element,
        choice: etree.Element,
        parent_path: str,
        current_depth: int,
        included_paths: Set[str]
    ):
        """choiceの子要素を処理（パターンで指定されたものだけ）"""
        for child_elem_def in choice.findall(f'{self.xsd_prefix}:element', namespaces=self.ns):
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
        prefix = self.xsd_prefix
        root_elems = self.schema_tree.xpath(
            f'/{prefix}:schema/{prefix}:element',
            namespaces=self.ns
        )
        if root_elems:
            return root_elems[0].get('name')
        return None

    def _find_element_definition(self, elem_name: str) -> Optional[etree.Element]:
        """要素定義を検索"""
        elems = self.schema_tree.xpath(
            f'//{self.xsd_prefix}:element[@name="{elem_name}"]',
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
            f'//{self.xsd_prefix}:complexType[@name="{local_name}"]',
            namespaces=self.ns
        )
        if types:
            self.type_cache[local_name] = types[0]
            return types[0]

        # simpleType
        types = self.schema_tree.xpath(
            f'//{self.xsd_prefix}:simpleType[@name="{local_name}"]',
            namespaces=self.ns
        )
        if types:
            self.type_cache[local_name] = types[0]
            return types[0]

        return None

    def _get_enumeration_values(self, type_name: str) -> list:
        """
        型定義から列挙値を取得

        Args:
            type_name: 型名（例: "my:StatusType"）

        Returns:
            列挙値のリスト（列挙型でない場合は空リスト）
        """
        type_def = self._find_type_definition(type_name)
        if type_def is None:
            return []

        # simpleType/restriction/enumeration を探す
        enumerations = type_def.xpath(
            f'.//{self.xsd_prefix}:restriction/{self.xsd_prefix}:enumeration/@value',
            namespaces=self.ns
        )

        return enumerations if enumerations else []

    def _generate_dummy_value(self, name: str, attr_type: str) -> str:
        """
        ダミー値を生成（列挙型対応）

        Args:
            name: 属性名
            attr_type: 属性の型（例: "my:StatusType", "xs:string"）

        Returns:
            適切なダミー値
        """
        # 列挙型の場合、定義された値から選択
        enum_values = self._get_enumeration_values(attr_type)
        if enum_values:
            # 最初の値を使用（一貫性のため）
            return enum_values[0]

        # 型に応じたダミー値
        type_mapping = {
            'xs:string': f'{name}_value',
            'xs:int': '1',
            'xs:integer': '1',
            'xs:decimal': '1.0',
            'xs:float': '1.0',
            'xs:double': '1.0',
            'xs:boolean': 'true',
            'xs:date': '2024-01-01',
            'xs:dateTime': '2024-01-01T00:00:00',
            'xs:time': '12:00:00',
            'xs:base64Binary': 'U2FtcGxlRGF0YQ==',  # "SampleData" in base64
            'xs:hexBinary': '48656C6C6F',  # "Hello" in hex
        }

        local_type = attr_type.split(':')[-1] if ':' in attr_type else attr_type
        return type_mapping.get(f'xs:{local_type}', f'{name}_value')

    def _generate_text_value(self, elem_name: str, elem_type: str) -> str:
        """
        要素のテキスト値を生成（型制約対応）

        Args:
            elem_name: 要素名
            elem_type: 要素の型

        Returns:
            適切なテキスト値
        """
        # 列挙型の場合、定義された値から選択
        enum_values = self._get_enumeration_values(elem_type)
        if enum_values:
            return enum_values[0]

        # 型に応じたダミー値
        type_mapping = {
            'xs:string': f'{elem_name}_value',
            'xs:int': '1',
            'xs:integer': '100',
            'xs:decimal': '1.0',
            'xs:float': '1.0',
            'xs:double': '1.0',
            'xs:boolean': 'true',
            'xs:date': '2024-01-01',
            'xs:dateTime': '2024-01-01T00:00:00Z',
            'xs:time': '12:00:00',
            'xs:base64Binary': 'U2FtcGxlRGF0YQ==',  # "SampleData" in base64
            'xs:hexBinary': '48656C6C6F',  # "Hello" in hex
        }

        local_type = elem_type.split(':')[-1] if ':' in elem_type else elem_type
        return type_mapping.get(f'xs:{local_type}', 'sample_text')
