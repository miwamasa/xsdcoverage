#!/usr/bin/env python3
"""
XSD Schema-based XML Generator
XSDスキーマから高カバレッジのXMLファイル群を自動生成するツール

【アルゴリズムの概要】
1. XSDスキーマを解析して、すべての要素パスと属性パスを列挙（カバレッジ項目集合U）
2. XMLスニペット候補を生成し、各候補がカバーするパス集合C_iを算出
3. セット被覆問題として、貪欲法で最小のXMLファイル数で最大カバレッジを達成
4. 生成されたXMLファイルをXSDで検証

詳細は spec/xml_generation.md を参照
"""

import sys
import os
from lxml import etree
from typing import Set, Dict, List, Tuple, Optional
from collections import defaultdict
import random
import argparse

# xsd_coverage.pyのSchemaAnalyzerを再利用
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xsd_coverage import SchemaAnalyzer


class XMLSnippet:
    """XMLスニペット候補を表すクラス"""

    def __init__(self, root_element: etree._Element, covered_paths: Set[str], depth: int):
        """
        Args:
            root_element: XMLのルート要素（lxml Element）
            covered_paths: このスニペットがカバーする要素パス・属性パスの集合
            depth: このスニペットの最大深度
        """
        self.root_element = root_element
        self.covered_paths = covered_paths
        self.depth = depth

    def to_string(self, pretty: bool = True) -> str:
        """XML文字列として出力"""
        return etree.tostring(
            self.root_element,
            pretty_print=pretty,
            xml_declaration=True,
            encoding='utf-8'
        ).decode('utf-8')


class XMLGenerator:
    """XSDスキーマからXMLスニペット候補を生成"""

    def __init__(self, xsd_path: str, max_depth: int = 10, namespace_map: Optional[Dict[str, str]] = None):
        """
        Args:
            xsd_path: XSDファイルのパス
            max_depth: 再帰的構造の最大展開深度
            namespace_map: 名前空間のマッピング（prefix -> URI）
        """
        self.xsd_path = xsd_path
        self.max_depth = max_depth

        # SchemaAnalyzerを使ってXSDを解析
        self.schema_analyzer = SchemaAnalyzer(xsd_path)
        self.schema_analyzer.analyze(max_recursion_depth=max_depth)

        # 定義されたパスを取得
        self.defined_element_paths, self.defined_attribute_paths = \
            self.schema_analyzer.get_defined_paths()

        # 全カバレッジ項目集合 U
        self.all_coverage_items: Set[str] = \
            self.defined_element_paths | self.defined_attribute_paths

        # 名前空間マップ
        self.namespace_map = namespace_map or {}
        if not self.namespace_map:
            # XSDからターゲット名前空間を取得
            target_ns = self.schema_analyzer.target_ns
            if target_ns:
                self.namespace_map = {
                    'ns': target_ns,
                    'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
                }

        # XSDスキーマツリー
        self.schema_tree = self.schema_analyzer.schema_tree
        self.schema_root = self.schema_analyzer.schema_root
        self.ns = self.schema_analyzer.ns

        # 型キャッシュ
        self.type_cache = self.schema_analyzer.type_cache

    def generate_snippets(self, max_snippets: int = 100,
                         max_gen_depth: Optional[int] = None) -> List[XMLSnippet]:
        """XMLスニペット候補を生成

        Args:
            max_snippets: 生成する最大スニペット数
            max_gen_depth: 生成時の最大深度（Noneの場合はmax_depthを使用）

        Returns:
            XMLSnippet候補のリスト
        """
        if max_gen_depth is None:
            max_gen_depth = min(self.max_depth, 5)  # 実用的な制限

        snippets = []

        # ルート要素を取得
        root_elements = self.schema_root.findall('.//xsd:element[@name]', self.ns)

        for elem_def in root_elements:
            parent = elem_def.getparent()
            if parent is not None and parent.tag == f"{{{self.ns['xsd']}}}schema":
                elem_name = elem_def.get('name')
                elem_type = elem_def.get('type')

                if elem_type:
                    # 深度別にスニペットを生成（depth 1 から max_gen_depth まで）
                    for target_depth in range(1, max_gen_depth + 1):
                        # 各深度で複数のバリエーションを生成
                        # バリエーション1: 全ての要素・属性を含める（最大カバレッジ）
                        snippet = self._generate_snippet_for_depth(
                            elem_name, elem_type, target_depth,
                            include_optional=True, choice_index=0
                        )
                        if snippet:
                            snippets.append(snippet)

                        # バリエーション2: 必須要素のみ（最小構成）
                        snippet = self._generate_snippet_for_depth(
                            elem_name, elem_type, target_depth,
                            include_optional=False, choice_index=0
                        )
                        if snippet:
                            snippets.append(snippet)

                        # バリエーション3〜: choice要素で異なる選択肢
                        for choice_idx in range(1, 3):  # choice要素の異なる選択肢
                            snippet = self._generate_snippet_for_depth(
                                elem_name, elem_type, target_depth,
                                include_optional=True, choice_index=choice_idx
                            )
                            if snippet:
                                snippets.append(snippet)

                        if len(snippets) >= max_snippets:
                            break

            if len(snippets) >= max_snippets:
                break

        return snippets

    def _generate_snippet_for_depth(self, elem_name: str, elem_type: str,
                                    target_depth: int, include_optional: bool = True,
                                    choice_index: int = 0) -> Optional[XMLSnippet]:
        """指定された深度のXMLスニペットを生成

        Args:
            elem_name: ルート要素名
            elem_type: ルート要素の型名
            target_depth: 目標とする深度
            include_optional: オプショナル要素・属性を含めるか
            choice_index: choice要素の選択インデックス

        Returns:
            XMLSnippet または None
        """
        # 名前空間を設定
        nsmap = self.namespace_map if self.namespace_map else None

        # ルート要素を作成
        if nsmap:
            # 名前空間付き
            ns_uri = nsmap.get('ns', '')
            root = etree.Element(f"{{{ns_uri}}}{elem_name}", nsmap=nsmap)

            # schemaLocation属性を追加
            if 'xsi' in nsmap:
                xsi_ns = nsmap['xsi']
                schema_location = f"{ns_uri} {os.path.basename(self.xsd_path)}"
                root.set(f"{{{xsi_ns}}}schemaLocation", schema_location)
        else:
            root = etree.Element(elem_name)

        # カバーされるパスを追跡
        covered_paths = set()
        root_path = f"/{elem_name}"
        covered_paths.add(root_path)

        # 型定義を処理してXMLを構築
        self._build_element(root, root_path, elem_type, 1, target_depth, covered_paths,
                          include_optional=include_optional, choice_index=choice_index)

        return XMLSnippet(root, covered_paths, target_depth)

    def _build_element(self, parent_elem: etree._Element, parent_path: str,
                      type_name: str, current_depth: int, max_depth: int,
                      covered_paths: Set[str], include_optional: bool = True,
                      choice_index: int = 0):
        """要素に対して型定義に基づいてXMLを構築

        Args:
            parent_elem: 親のXML要素
            parent_path: 親の要素パス
            type_name: 処理する型名
            current_depth: 現在の深度
            max_depth: 最大深度
            covered_paths: カバーされたパスの集合（更新される）
            include_optional: オプショナル要素・属性を含めるか
            choice_index: choice要素の選択インデックス
        """
        if current_depth > max_depth:
            return

        # 名前空間プレフィックスを除去
        clean_type_name = self.schema_analyzer._remove_ns_prefix(type_name)

        # キャッシュから型定義を取得
        type_def = self.type_cache.get(clean_type_name)
        if type_def is None:
            return

        # 【属性を追加】
        self._add_attributes(parent_elem, parent_path, type_def, covered_paths,
                           include_optional=include_optional)

        # 【子要素を追加】
        # sequence/choice/all内の要素を処理
        for container in type_def.findall('.//xsd:sequence', self.ns) + \
                       type_def.findall('.//xsd:choice', self.ns) + \
                       type_def.findall('.//xsd:all', self.ns):

            # choice の場合は1つだけ選択
            elements = container.findall('./xsd:element', self.ns)
            is_choice = 'choice' in container.tag

            if is_choice and elements:
                # choiceの場合は指定されたインデックスの要素を選択
                idx = choice_index % len(elements)  # 範囲外の場合は循環
                elements = [elements[idx]]

            for elem_def in elements:
                elem_name = elem_def.get('name')
                elem_ref = elem_def.get('ref')
                elem_type = elem_def.get('type')
                min_occurs = int(elem_def.get('minOccurs', '1'))
                max_occurs = elem_def.get('maxOccurs', '1')

                # minOccurs=0の要素はオプショナル
                # include_optional=Falseの場合はスキップ
                if min_occurs == 0 and not include_optional:
                    continue

                if elem_name:
                    # 名前空間を考慮して子要素を作成
                    if self.namespace_map and 'ns' in self.namespace_map:
                        child_elem = etree.SubElement(
                            parent_elem,
                            f"{{{self.namespace_map['ns']}}}{elem_name}"
                        )
                    else:
                        child_elem = etree.SubElement(parent_elem, elem_name)

                    child_path = f"{parent_path}/{elem_name}"
                    covered_paths.add(child_path)

                    # インライン型定義をチェック
                    inline_complex_type = elem_def.find('./xsd:complexType', self.ns)
                    if inline_complex_type is not None:
                        self._build_inline_type(child_elem, child_path,
                                              inline_complex_type,
                                              current_depth + 1, max_depth,
                                              covered_paths, include_optional, choice_index)
                    elif elem_type:
                        clean_elem_type = self.schema_analyzer._remove_ns_prefix(elem_type)

                        # 組み込み型の場合はサンプル値を設定
                        if clean_elem_type in ['string', 'integer', 'date', 'dateTime',
                                               'boolean', 'decimal', 'float', 'double']:
                            child_elem.text = self._generate_sample_value(clean_elem_type)
                        elif clean_elem_type in ['ID', 'NCName', 'token']:
                            child_elem.text = f"ID{random.randint(1000, 9999)}"
                        else:
                            # 複合型の場合は再帰的に処理
                            self._build_element(child_elem, child_path, elem_type,
                                              current_depth + 1, max_depth,
                                              covered_paths, include_optional, choice_index)

                elif elem_ref:
                    # ref要素の処理
                    ref_name = self.schema_analyzer._remove_ns_prefix(elem_ref)

                    if self.namespace_map and 'ns' in self.namespace_map:
                        child_elem = etree.SubElement(
                            parent_elem,
                            f"{{{self.namespace_map['ns']}}}{ref_name}"
                        )
                    else:
                        child_elem = etree.SubElement(parent_elem, ref_name)

                    child_path = f"{parent_path}/{ref_name}"
                    covered_paths.add(child_path)

                    # ref要素の型を探す
                    ref_elements = self.schema_root.findall(f'.//xsd:element[@name="{ref_name}"]', self.ns)
                    for ref_elem in ref_elements:
                        ref_type = ref_elem.get('type')
                        if ref_type:
                            self._build_element(child_elem, child_path, ref_type,
                                              current_depth + 1, max_depth,
                                              covered_paths, include_optional, choice_index)
                            break

    def _build_inline_type(self, parent_elem: etree._Element, parent_path: str,
                          type_elem: etree._Element, current_depth: int,
                          max_depth: int, covered_paths: Set[str],
                          include_optional: bool = True, choice_index: int = 0):
        """インライン型定義を処理してXMLを構築"""

        if current_depth > max_depth:
            return

        # 属性を追加
        for attr_def in type_elem.findall('./xsd:attribute[@name]', self.ns):
            attr_name = attr_def.get('name')
            attr_type = attr_def.get('type', 'xsd:string')
            attr_use = attr_def.get('use', 'optional')
            attr_path = f"{parent_path}@{attr_name}"

            # required属性または include_optional=True の場合に追加
            if attr_use == 'required' or include_optional:
                clean_attr_type = self.schema_analyzer._remove_ns_prefix(attr_type)
                sample_value = self._generate_sample_value(clean_attr_type)
                parent_elem.set(attr_name, sample_value)
                covered_paths.add(attr_path)

        # 子要素を追加
        for container in type_elem.findall('.//xsd:sequence', self.ns) + \
                       type_elem.findall('.//xsd:choice', self.ns) + \
                       type_elem.findall('.//xsd:all', self.ns):

            elements = container.findall('./xsd:element', self.ns)
            is_choice = 'choice' in container.tag

            if is_choice and elements:
                idx = choice_index % len(elements)
                elements = [elements[idx]]

            for elem_def in elements:
                elem_name = elem_def.get('name')
                elem_type = elem_def.get('type')
                min_occurs = int(elem_def.get('minOccurs', '1'))

                # minOccurs=0の要素はオプショナル
                if min_occurs == 0 and not include_optional:
                    continue

                if elem_name:
                    if self.namespace_map and 'ns' in self.namespace_map:
                        child_elem = etree.SubElement(
                            parent_elem,
                            f"{{{self.namespace_map['ns']}}}{elem_name}"
                        )
                    else:
                        child_elem = etree.SubElement(parent_elem, elem_name)

                    child_path = f"{parent_path}/{elem_name}"
                    covered_paths.add(child_path)

                    # ネストしたインライン型
                    nested_complex = elem_def.find('./xsd:complexType', self.ns)
                    if nested_complex is not None:
                        self._build_inline_type(child_elem, child_path, nested_complex,
                                              current_depth + 1, max_depth, covered_paths,
                                              include_optional, choice_index)
                    elif elem_type:
                        clean_elem_type = self.schema_analyzer._remove_ns_prefix(elem_type)
                        if clean_elem_type in ['string', 'integer', 'date', 'dateTime',
                                               'boolean', 'decimal', 'float', 'double']:
                            child_elem.text = self._generate_sample_value(clean_elem_type)
                        else:
                            self._build_element(child_elem, child_path, elem_type,
                                              current_depth + 1, max_depth, covered_paths,
                                              include_optional, choice_index)

    def _add_attributes(self, elem: etree._Element, elem_path: str,
                       type_def: etree._Element, covered_paths: Set[str],
                       include_optional: bool = True):
        """型定義に基づいて属性を追加"""

        # 直接定義された属性
        for attr_def in type_def.findall('./xsd:attribute[@name]', self.ns):
            attr_name = attr_def.get('name')
            attr_type = attr_def.get('type', 'xsd:string')
            attr_use = attr_def.get('use', 'optional')

            # required属性またはinclude_optional=Trueの場合に追加
            if attr_use == 'required' or include_optional:
                clean_attr_type = self.schema_analyzer._remove_ns_prefix(attr_type)

                # 列挙型の場合は列挙値から選択
                enum_values = self._get_enum_values(clean_attr_type)
                if enum_values:
                    sample_value = random.choice(enum_values)
                else:
                    sample_value = self._generate_sample_value(clean_attr_type)

                elem.set(attr_name, sample_value)

                attr_path = f"{elem_path}@{attr_name}"
                covered_paths.add(attr_path)

        # extension内の属性
        for ext in type_def.findall('.//xsd:extension', self.ns):
            for attr_def in ext.findall('./xsd:attribute[@name]', self.ns):
                attr_name = attr_def.get('name')
                attr_type = attr_def.get('type', 'xsd:string')
                attr_use = attr_def.get('use', 'optional')

                # required属性またはinclude_optional=Trueの場合に追加
                if attr_use == 'required' or include_optional:
                    clean_attr_type = self.schema_analyzer._remove_ns_prefix(attr_type)

                    enum_values = self._get_enum_values(clean_attr_type)
                    if enum_values:
                        sample_value = random.choice(enum_values)
                    else:
                        sample_value = self._generate_sample_value(clean_attr_type)

                    elem.set(attr_name, sample_value)

                    attr_path = f"{elem_path}@{attr_name}"
                    covered_paths.add(attr_path)

    def _get_enum_values(self, type_name: str) -> List[str]:
        """simpleTypeの列挙値を取得"""
        type_def = self.type_cache.get(type_name)
        if type_def is None:
            return []

        # simpleType内のenumerationを探す
        enums = type_def.findall('.//xsd:enumeration', self.ns)
        return [e.get('value') for e in enums if e.get('value')]

    def _generate_sample_value(self, type_name: str) -> str:
        """型に応じたサンプル値を生成"""
        type_samples = {
            'string': 'SampleText',
            'integer': '42',
            'int': '42',
            'long': '1234567890',
            'short': '100',
            'byte': '10',
            'decimal': '123.45',
            'float': '123.45',
            'double': '123.456789',
            'boolean': 'true',
            'date': '2025-01-15',
            'dateTime': '2025-01-15T10:30:00',
            'time': '10:30:00',
            'anyURI': 'http://example.com',
            'base64Binary': 'QmFzZTY0RGF0YQ==',
            'hexBinary': '48656C6C6F',
            'ID': f'ID{random.randint(1000, 9999)}',
            'NCName': f'NCName{random.randint(100, 999)}',
            'token': f'Token{random.randint(100, 999)}',
        }
        return type_samples.get(type_name, 'DefaultValue')


class SetCoverOptimizer:
    """セット被覆問題を解いて最適なスニペット組み合わせを選択"""

    def __init__(self, all_items: Set[str], snippets: List[XMLSnippet]):
        """
        Args:
            all_items: カバレッジ項目の全集合 U
            snippets: XMLスニペット候補のリスト
        """
        self.all_items = all_items
        self.snippets = snippets
        self.selected_snippets: List[XMLSnippet] = []

    def solve_greedy(self, target_coverage: float = 0.95,
                     max_files: int = 50) -> List[XMLSnippet]:
        """貪欲法でセット被覆問題を解く

        Args:
            target_coverage: 目標カバレッジ率（0.0〜1.0）
            max_files: 最大ファイル数

        Returns:
            選択されたXMLSnippetのリスト
        """
        uncovered = self.all_items.copy()
        selected = []

        print(f"セット被覆最適化開始:")
        print(f"  全カバレッジ項目数: {len(self.all_items)}")
        print(f"  候補スニペット数: {len(self.snippets)}")
        print(f"  目標カバレッジ: {target_coverage * 100:.1f}%")
        print()

        iteration = 0
        while uncovered and len(selected) < max_files:
            iteration += 1

            # 最も多くの未カバー項目をカバーするスニペットを選択
            best_snippet = None
            best_coverage_count = 0
            best_score = 0

            for snippet in self.snippets:
                # このスニペットが新たにカバーする項目数
                new_coverage = snippet.covered_paths & uncovered
                coverage_count = len(new_coverage)

                if coverage_count > 0:
                    # スコア計算（深度ペナルティを考慮）
                    # 浅い深度で多くカバーできるものを優先
                    depth_penalty = 1.0 / (1.0 + snippet.depth * 0.1)
                    score = coverage_count * depth_penalty

                    if score > best_score:
                        best_score = score
                        best_coverage_count = coverage_count
                        best_snippet = snippet

            if best_snippet is None:
                # これ以上カバーできない
                break

            # 選択
            selected.append(best_snippet)
            newly_covered = best_snippet.covered_paths & uncovered
            uncovered -= newly_covered

            current_coverage = (len(self.all_items) - len(uncovered)) / len(self.all_items)

            print(f"  反復 {iteration}: スニペット選択（深度={best_snippet.depth}）")
            print(f"    新規カバー: {best_coverage_count}項目")
            print(f"    累積カバレッジ: {current_coverage * 100:.2f}% "
                  f"({len(self.all_items) - len(uncovered)}/{len(self.all_items)})")

            # 目標カバレッジに到達したら終了
            if current_coverage >= target_coverage:
                print(f"\n目標カバレッジ {target_coverage * 100:.1f}% に到達しました")
                break

        print(f"\n最適化完了:")
        print(f"  選択されたファイル数: {len(selected)}")
        print(f"  最終カバレッジ: {((len(self.all_items) - len(uncovered)) / len(self.all_items) * 100):.2f}%")
        print(f"  未カバー項目数: {len(uncovered)}")
        print()

        self.selected_snippets = selected
        return selected


def save_snippets_to_files(snippets: List[XMLSnippet], output_dir: str, prefix: str = "generated"):
    """選択されたスニペットをXMLファイルとして保存

    Args:
        snippets: 保存するXMLスニペットのリスト
        output_dir: 出力ディレクトリ
        prefix: ファイル名のプレフィックス
    """
    os.makedirs(output_dir, exist_ok=True)

    for i, snippet in enumerate(snippets, 1):
        filename = f"{prefix}_{i:03d}_depth{snippet.depth}.xml"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(snippet.to_string())

        print(f"  {filename} (深度={snippet.depth}, カバー={len(snippet.covered_paths)}項目)")

    print(f"\n{len(snippets)}個のXMLファイルを {output_dir}/ に保存しました")


def main():
    parser = argparse.ArgumentParser(
        description='XSDスキーマから高カバレッジXMLファイル群を生成',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  # サンプルスキーマでXML生成
  python xml_generator.py test/sample/extended_schema.xsd -o generated/sample

  # ISOスキーマでXML生成（カバレッジ80%目標）
  python xml_generator.py test/ISO/IEC62474_Schema_X8.21-120240831.xsd \\
      -o generated/iso --target-coverage 0.8 --max-files 30

  # 深度5、最大20ファイルで生成
  python xml_generator.py schema.xsd -o output --max-depth 5 --max-files 20
        '''
    )
    parser.add_argument('xsd_file', help='XSDスキーマファイル')
    parser.add_argument('-o', '--output-dir', required=True, help='出力ディレクトリ')
    parser.add_argument('--max-depth', type=int, default=10,
                       help='再帰構造の最大展開深度（デフォルト: 10）')
    parser.add_argument('--max-gen-depth', type=int, default=None,
                       help='生成時の最大深度（デフォルト: min(max_depth, 5)）')
    parser.add_argument('--target-coverage', type=float, default=0.95,
                       help='目標カバレッジ率（0.0〜1.0、デフォルト: 0.95）')
    parser.add_argument('--max-files', type=int, default=50,
                       help='最大生成ファイル数（デフォルト: 50）')
    parser.add_argument('--max-snippets', type=int, default=100,
                       help='生成する候補スニペット数（デフォルト: 100）')
    parser.add_argument('--prefix', type=str, default='generated',
                       help='生成ファイルのプレフィックス（デフォルト: generated）')
    parser.add_argument('--namespace', type=str, default=None,
                       help='名前空間URI（自動検出されない場合に指定）')

    args = parser.parse_args()

    # 名前空間マップを構築
    namespace_map = None
    if args.namespace:
        namespace_map = {
            'ns': args.namespace,
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }

    print("=" * 80)
    print("XSD → 高カバレッジXML生成ツール")
    print("=" * 80)
    print(f"XSDファイル: {args.xsd_file}")
    print(f"出力ディレクトリ: {args.output_dir}")
    print(f"最大再帰深度: {args.max_depth}")
    print(f"生成最大深度: {args.max_gen_depth or f'min({args.max_depth}, 5)'}")
    print(f"目標カバレッジ: {args.target_coverage * 100:.1f}%")
    print(f"最大ファイル数: {args.max_files}")
    print()

    # ステップ1: XSDスキーマを解析
    print("ステップ1: XSDスキーマを解析中...")
    generator = XMLGenerator(args.xsd_file, args.max_depth, namespace_map)

    print(f"  定義された要素パス: {len(generator.defined_element_paths)}")
    print(f"  定義された属性パス: {len(generator.defined_attribute_paths)}")
    print(f"  全カバレッジ項目数: {len(generator.all_coverage_items)}")
    print()

    # ステップ2: XMLスニペット候補を生成
    print("ステップ2: XMLスニペット候補を生成中...")
    snippets = generator.generate_snippets(
        max_snippets=args.max_snippets,
        max_gen_depth=args.max_gen_depth
    )
    print(f"  生成された候補数: {len(snippets)}")

    # 候補の統計
    depth_counts = defaultdict(int)
    coverage_stats = []
    for snippet in snippets:
        depth_counts[snippet.depth] += 1
        coverage_stats.append(len(snippet.covered_paths))

    print(f"  深度別候補数:")
    for depth in sorted(depth_counts.keys()):
        print(f"    深度{depth}: {depth_counts[depth]}個")
    print(f"  平均カバー項目数/スニペット: {sum(coverage_stats) / len(coverage_stats):.1f}")
    print()

    # ステップ3: セット被覆最適化
    print("ステップ3: セット被覆最適化中...")
    optimizer = SetCoverOptimizer(generator.all_coverage_items, snippets)
    selected = optimizer.solve_greedy(
        target_coverage=args.target_coverage,
        max_files=args.max_files
    )

    # ステップ4: XMLファイルとして保存
    print("ステップ4: XMLファイルを保存中...")
    save_snippets_to_files(selected, args.output_dir, args.prefix)
    print()

    # サマリー
    total_covered = sum(len(s.covered_paths) for s in selected)
    unique_covered = set()
    for s in selected:
        unique_covered |= s.covered_paths

    print("=" * 80)
    print("生成完了サマリー")
    print("=" * 80)
    print(f"生成されたXMLファイル数: {len(selected)}")
    print(f"達成カバレッジ: {len(unique_covered) / len(generator.all_coverage_items) * 100:.2f}%")
    print(f"  カバーされた項目数: {len(unique_covered)}/{len(generator.all_coverage_items)}")
    print(f"  要素パスカバレッジ: {len(unique_covered & generator.defined_element_paths)}/{len(generator.defined_element_paths)}")
    print(f"  属性パスカバレッジ: {len(unique_covered & generator.defined_attribute_paths)}/{len(generator.defined_attribute_paths)}")
    print()
    print(f"次のステップ:")
    print(f"  1. 生成されたXMLの検証:")
    print(f"     python xsd_coverage.py {args.xsd_file} {args.output_dir}/*.xml")
    print(f"  2. 既存のXMLとの比較:")
    print(f"     既存XMLファイル群に対しても同じコマンドを実行して比較")
    print("=" * 80)


if __name__ == "__main__":
    main()
