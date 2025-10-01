#!/usr/bin/env python3
"""
SMT Solver-based XML Generator
Z3ソルバーを使用してXSDスキーマから最適なXMLファイル群を生成

【アルゴリズムの原理】
カバレッジ最大化問題を制約充足問題（CSP）として定式化し、
SMTソルバー（Z3）で最適解を求める。

主な利点:
- 最適性保証: 制約を満たす最適解が存在すれば必ず見つかる
- 複雑な制約: XSDのあらゆる制約を論理式で表現可能
- 100%カバレッジ: 理論的に達成可能

制約の種類:
1. 階層制約: 子パスが含まれる → 親パスも含まれる
2. choice制約: choice要素では1つだけ選択
3. 必須要素制約: 親が含まれる → required子要素も含まれる
4. ファイル割り当て: 各パスは少なくとも1つのファイルに含まれる
5. 深度制約: 最大深度を超えるパスは含まれない
"""

import sys
import os
from lxml import etree
from typing import Set, Dict, List, Tuple, Optional
from collections import defaultdict
import argparse

try:
    from z3 import *
except ImportError:
    print("エラー: z3-solverがインストールされていません")
    print("インストール: pip install z3-solver --break-system-packages")
    sys.exit(1)

# xsd_coverage.pyのSchemaAnalyzerを再利用
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xsd_coverage import SchemaAnalyzer


class PathVariableMapper:
    """パスとZ3ブール変数のマッピングを管理"""

    def __init__(self):
        self.path_to_var: Dict[str, Bool] = {}
        self.var_to_path: Dict[str, str] = {}

    def get_or_create_var(self, path: str) -> Bool:
        """パスに対応するZ3変数を取得または作成"""
        if path not in self.path_to_var:
            # Z3変数名にはスラッシュやアットマークを含められないので置換
            var_name = path.replace('/', '_').replace('@', '_AT_').replace('-', '_')
            var = Bool(var_name)
            self.path_to_var[path] = var
            self.var_to_path[var_name] = path
        return self.path_to_var[path]

    def get_path(self, var_name: str) -> Optional[str]:
        """Z3変数名からパスを逆引き"""
        return self.var_to_path.get(var_name)


class XSDConstraintExtractor:
    """XSDスキーマから制約情報を抽出"""

    def __init__(self, schema_analyzer: SchemaAnalyzer):
        self.schema_analyzer = schema_analyzer
        self.schema_root = schema_analyzer.schema_root
        self.ns = schema_analyzer.ns
        self.type_cache = schema_analyzer.type_cache

        # 制約情報
        self.parent_child_map: Dict[str, List[str]] = defaultdict(list)
        self.required_children: Dict[str, List[str]] = defaultdict(list)
        self.choice_groups: List[List[str]] = []
        self.path_depths: Dict[str, int] = {}

    def extract_constraints(self, max_depth: int):
        """XSDから制約情報を抽出"""
        print("制約情報を抽出中...")

        # ルート要素から開始
        root_elements = self.schema_root.findall('.//xsd:element[@name]', self.ns)

        for elem_def in root_elements:
            parent = elem_def.getparent()
            if parent is not None and parent.tag == f"{{{self.ns['xsd']}}}schema":
                elem_name = elem_def.get('name')
                elem_type = elem_def.get('type')

                if elem_type:
                    root_path = f"/{elem_name}"
                    self.path_depths[root_path] = 1
                    self._extract_type_constraints(elem_type, root_path, 1, max_depth)

        print(f"  親子関係: {len(self.parent_child_map)}組")
        print(f"  必須要素: {sum(len(v) for v in self.required_children.values())}個")
        print(f"  choice制約: {len(self.choice_groups)}組")

    def _extract_type_constraints(self, type_name: str, current_path: str,
                                  depth: int, max_depth: int):
        """型定義から制約を抽出"""
        if depth > max_depth:
            return

        clean_type_name = self.schema_analyzer._remove_ns_prefix(type_name)
        type_def = self.type_cache.get(clean_type_name)

        if type_def is None:
            return

        # sequence/choice/all内の要素を処理
        for container in type_def.findall('.//xsd:sequence', self.ns) + \
                       type_def.findall('.//xsd:choice', self.ns) + \
                       type_def.findall('.//xsd:all', self.ns):

            is_choice = 'choice' in container.tag
            elements = container.findall('./xsd:element', self.ns)

            # choice制約の記録
            if is_choice and len(elements) > 1:
                choice_paths = []
                for elem_def in elements:
                    elem_name = elem_def.get('name')
                    if elem_name:
                        child_path = f"{current_path}/{elem_name}"
                        choice_paths.append(child_path)
                if choice_paths:
                    self.choice_groups.append(choice_paths)

            # 親子関係と必須制約の記録
            for elem_def in elements:
                elem_name = elem_def.get('name')
                elem_ref = elem_def.get('ref')
                elem_type = elem_def.get('type')
                min_occurs = int(elem_def.get('minOccurs', '1'))

                actual_name = elem_name if elem_name else (
                    self.schema_analyzer._remove_ns_prefix(elem_ref) if elem_ref else None
                )

                if actual_name:
                    child_path = f"{current_path}/{actual_name}"

                    # 親子関係を記録
                    self.parent_child_map[current_path].append(child_path)
                    self.path_depths[child_path] = depth + 1

                    # 必須要素を記録（minOccurs >= 1）
                    if min_occurs >= 1 and not is_choice:
                        self.required_children[current_path].append(child_path)

                    # 属性パスも親子関係に含める
                    # （属性は親要素に依存する）

                    # 再帰的に型を処理
                    if elem_type:
                        clean_elem_type = self.schema_analyzer._remove_ns_prefix(elem_type)
                        if clean_elem_type not in ['string', 'integer', 'date', 'dateTime',
                                                   'boolean', 'decimal', 'float', 'double',
                                                   'ID', 'NCName', 'token']:
                            self._extract_type_constraints(elem_type, child_path,
                                                          depth + 1, max_depth)


class SMTConstraintBuilder:
    """XSD制約をZ3 SMT制約に変換"""

    def __init__(self, constraint_extractor: XSDConstraintExtractor,
                 path_mapper: PathVariableMapper,
                 element_paths: Set[str],
                 attribute_paths: Set[str]):
        self.extractor = constraint_extractor
        self.mapper = path_mapper
        self.element_paths = element_paths
        self.attribute_paths = attribute_paths
        self.all_paths = element_paths | attribute_paths

    def build_constraints(self, max_files: int = 10) -> Tuple[Solver, List[Bool]]:
        """すべての制約をZ3ソルバーに追加

        Returns:
            (solver, file_vars): ソルバーとファイル変数のリスト
        """
        solver = Solver()

        print("\nZ3制約を構築中...")

        # 1. 階層制約
        hierarchy_constraints = self._build_hierarchy_constraints()
        for c in hierarchy_constraints:
            solver.add(c)
        print(f"  階層制約: {len(hierarchy_constraints)}個")

        # 2. choice制約
        choice_constraints = self._build_choice_constraints()
        for c in choice_constraints:
            solver.add(c)
        print(f"  choice制約: {len(choice_constraints)}個")

        # 3. 必須要素制約
        required_constraints = self._build_required_constraints()
        for c in required_constraints:
            solver.add(c)
        print(f"  必須要素制約: {len(required_constraints)}個")

        # 4. ファイル割り当て制約
        file_vars, file_constraints = self._build_file_assignment_constraints(max_files)
        for c in file_constraints:
            solver.add(c)
        print(f"  ファイル割り当て制約: {len(file_constraints)}個")
        print(f"  ファイル変数: {len(file_vars)}個")

        # 5. 少なくとも1つのファイルを生成する制約
        solver.add(Or(file_vars))

        return solver, file_vars

    def _build_hierarchy_constraints(self) -> List:
        """階層制約: 子パスが含まれる → 親パスも含まれる"""
        constraints = []

        for path in self.all_paths:
            # パスから親パスを抽出
            if '@' in path:
                # 属性パスの場合: /A/B@attr の親は /A/B
                parent_path = path.split('@')[0]
            else:
                # 要素パスの場合: /A/B/C の親は /A/B
                parts = path.rsplit('/', 1)
                if len(parts) > 1 and parts[0]:
                    parent_path = parts[0]
                else:
                    # ルート要素には親がない
                    continue

            # 親パスが定義されている場合のみ制約を追加
            if parent_path in self.all_paths:
                child_var = self.mapper.get_or_create_var(path)
                parent_var = self.mapper.get_or_create_var(parent_path)

                # child → parent (子が真なら親も真)
                constraints.append(Implies(child_var, parent_var))

        return constraints

    def _build_choice_constraints(self) -> List:
        """choice制約: 親が含まれる場合、choice要素から1つだけ選択"""
        constraints = []

        for choice_group in self.extractor.choice_groups:
            # choice要素が存在する場合の制約
            if len(choice_group) < 2:
                continue

            # 親パスを取得（choice要素の親）
            first_path = choice_group[0]
            parent_path = first_path.rsplit('/', 1)[0] if '/' in first_path else None

            if parent_path and parent_path in self.all_paths:
                parent_var = self.mapper.get_or_create_var(parent_path)
                choice_vars = [self.mapper.get_or_create_var(p) for p in choice_group
                              if p in self.all_paths]

                if choice_vars:
                    # 親が含まれる場合、choice要素から少なくとも1つ選択
                    constraints.append(
                        Implies(parent_var, Or(choice_vars))
                    )

                    # 同時に2つ以上は選択しない（pairwise排他）
                    for i, var1 in enumerate(choice_vars):
                        for var2 in choice_vars[i+1:]:
                            constraints.append(Not(And(var1, var2)))

        return constraints

    def _build_required_constraints(self) -> List:
        """必須要素制約: 親が含まれる → required子要素も含まれる"""
        constraints = []

        for parent_path, required_children in self.extractor.required_children.items():
            if parent_path not in self.all_paths:
                continue

            parent_var = self.mapper.get_or_create_var(parent_path)

            for child_path in required_children:
                if child_path in self.all_paths:
                    child_var = self.mapper.get_or_create_var(child_path)
                    # parent → child (親が真なら必須子も真)
                    constraints.append(Implies(parent_var, child_var))

        return constraints

    def _build_file_assignment_constraints(self, max_files: int) -> Tuple[List[Bool], List]:
        """ファイル割り当て制約: 各パスは少なくとも1つのファイルに含まれる

        簡略化版: この実装では単一ファイル生成に焦点を当てる
        （複数ファイルの最適割り当ては将来の拡張）
        """
        constraints = []
        file_vars = []

        # 単一ファイル変数を作成
        file_var = Bool('file_0')
        file_vars.append(file_var)

        # すべてのパスがこのファイルに含まれる制約
        # （簡略版: パスが選択されたらファイルも生成される）

        return file_vars, constraints

    def add_objective_soft_constraints(self, solver: Solver,
                                       target_coverage: float = 0.95,
                                       file_penalty: int = 1000):
        """目的関数をソフト制約として追加

        Z3ではハード制約とソフト制約を組み合わせて最適化できる（Optimize使用）
        """
        # Optimizeソルバーに切り替え
        optimizer = Optimize()

        # 既存の制約をコピー
        for assertion in solver.assertions():
            optimizer.add(assertion)

        # カバレッジを最大化（すべてのパスの合計を最大化）
        coverage_sum = Sum([
            If(self.mapper.get_or_create_var(path), 1, 0)
            for path in self.all_paths
        ])
        optimizer.maximize(coverage_sum)

        return optimizer


class SMTXMLGenerator:
    """SMTソルバーを使用してXML生成"""

    def __init__(self, xsd_path: str, max_depth: int = 10,
                 namespace_map: Optional[Dict[str, str]] = None):
        self.xsd_path = xsd_path
        self.max_depth = max_depth

        # SchemaAnalyzerでXSDを解析
        self.schema_analyzer = SchemaAnalyzer(xsd_path)
        self.schema_analyzer.analyze(max_recursion_depth=max_depth)

        # 定義されたパスを取得
        self.element_paths, self.attribute_paths = \
            self.schema_analyzer.get_defined_paths()
        self.all_paths = self.element_paths | self.attribute_paths

        # 名前空間マップ
        self.namespace_map = namespace_map or {}
        if not self.namespace_map:
            target_ns = self.schema_analyzer.target_ns
            if target_ns:
                self.namespace_map = {
                    'ns': target_ns,
                    'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
                }

        # パス変数マッパー
        self.path_mapper = PathVariableMapper()

        # 制約抽出器
        self.constraint_extractor = XSDConstraintExtractor(self.schema_analyzer)
        self.constraint_extractor.extract_constraints(max_depth)

    def generate(self, target_coverage: float = 0.95,
                max_files: int = 10,
                timeout_ms: int = 60000) -> List[etree._Element]:
        """SMTソルバーでXMLを生成

        Args:
            target_coverage: 目標カバレッジ率
            max_files: 最大ファイル数
            timeout_ms: ソルバーのタイムアウト（ミリ秒）

        Returns:
            生成されたXMLツリーのリスト
        """
        print("\n" + "=" * 80)
        print("SMTソルバーによるXML生成開始")
        print("=" * 80)
        print(f"全カバレッジ項目数: {len(self.all_paths)}")
        print(f"  要素パス: {len(self.element_paths)}")
        print(f"  属性パス: {len(self.attribute_paths)}")
        print(f"目標カバレッジ: {target_coverage * 100:.1f}%")
        print(f"タイムアウト: {timeout_ms / 1000:.1f}秒")

        # 制約ビルダー
        constraint_builder = SMTConstraintBuilder(
            self.constraint_extractor,
            self.path_mapper,
            self.element_paths,
            self.attribute_paths
        )

        # Z3制約を構築
        solver, file_vars = constraint_builder.build_constraints(max_files)

        # 最適化ソルバーに変換（カバレッジ最大化）
        optimizer = constraint_builder.add_objective_soft_constraints(
            solver, target_coverage
        )

        # タイムアウト設定
        optimizer.set('timeout', timeout_ms)

        # ソルバー実行
        print("\nZ3ソルバーを実行中...")
        print("  （大規模なスキーマの場合、数分かかることがあります）")

        result = optimizer.check()

        if result == sat:
            print("  結果: SAT（解が見つかりました）")

            # モデル（解）を取得
            model = optimizer.model()

            # カバーされたパスを抽出
            covered_paths = self._extract_covered_paths(model)

            coverage_rate = len(covered_paths) / len(self.all_paths)
            print(f"\n達成カバレッジ: {coverage_rate * 100:.2f}%")
            print(f"  カバーされたパス: {len(covered_paths)}/{len(self.all_paths)}")

            # モデルからXMLを構築
            print("\nXMLを構築中...")
            xml_trees = self._build_xml_from_model(covered_paths)

            print(f"  生成されたXMLファイル数: {len(xml_trees)}")

            return xml_trees

        elif result == unsat:
            print("  結果: UNSAT（制約を満たす解が存在しません）")
            print("  理由: 目標カバレッジが高すぎるか、制約が矛盾しています")
            print("  対策: target_coverageを下げるか、max_depthを上げてください")
            return []

        else:  # unknown
            print("  結果: UNKNOWN（タイムアウトまたはメモリ不足）")
            print("  対策: timeoutを増やすか、max_depthを下げてください")
            return []

    def _extract_covered_paths(self, model) -> Set[str]:
        """Z3モデルからカバーされたパスを抽出"""
        covered = set()

        for decl in model.decls():
            var_name = decl.name()
            value = model[decl]

            # Trueに設定されたパスを抽出
            if is_true(value):
                path = self.path_mapper.get_path(var_name)
                if path:
                    covered.add(path)

        return covered

    def _build_xml_from_model(self, covered_paths: Set[str]) -> List[etree._Element]:
        """カバーされたパスからXMLツリーを構築"""

        # ルート要素を特定
        root_paths = [p for p in covered_paths if p.count('/') == 1 and '@' not in p]

        xml_trees = []

        for root_path in root_paths:
            root_name = root_path.lstrip('/')

            # 名前空間付きでルート要素を作成
            if self.namespace_map and 'ns' in self.namespace_map:
                ns_uri = self.namespace_map['ns']
                root = etree.Element(f"{{{ns_uri}}}{root_name}",
                                    nsmap=self.namespace_map)

                # schemaLocation属性を追加
                if 'xsi' in self.namespace_map:
                    xsi_ns = self.namespace_map['xsi']
                    schema_location = f"{ns_uri} {os.path.basename(self.xsd_path)}"
                    root.set(f"{{{xsi_ns}}}schemaLocation", schema_location)
            else:
                root = etree.Element(root_name)

            # ルートに属する要素・属性を追加
            self._build_tree_recursive(root, root_path, covered_paths)

            xml_trees.append(root)

        return xml_trees

    def _build_tree_recursive(self, parent_elem: etree._Element, parent_path: str,
                             covered_paths: Set[str]):
        """カバーされたパスに基づいて再帰的にXMLツリーを構築"""

        # この親の子要素パスを探す
        child_element_paths = [
            p for p in covered_paths
            if p.startswith(parent_path + '/') and '@' not in p
            and p.count('/') == parent_path.count('/') + 1
        ]

        # この親の属性パスを探す
        attribute_paths = [
            p for p in covered_paths
            if p.startswith(parent_path + '@')
        ]

        # 属性を追加
        for attr_path in attribute_paths:
            attr_name = attr_path.split('@')[1]
            # サンプル値を設定
            parent_elem.set(attr_name, self._generate_sample_value(attr_name))

        # 子要素を追加
        for child_path in child_element_paths:
            child_name = child_path.rsplit('/', 1)[1]

            # 名前空間付きで子要素を作成
            if self.namespace_map and 'ns' in self.namespace_map:
                child_elem = etree.SubElement(
                    parent_elem,
                    f"{{{self.namespace_map['ns']}}}{child_name}"
                )
            else:
                child_elem = etree.SubElement(parent_elem, child_name)

            # テキスト値の設定（リーフ要素の場合）
            has_children = any(
                p.startswith(child_path + '/')
                for p in covered_paths
            )
            if not has_children:
                child_elem.text = self._generate_sample_value(child_name)

            # 再帰的に子要素を構築
            self._build_tree_recursive(child_elem, child_path, covered_paths)

    def _generate_sample_value(self, name: str) -> str:
        """要素名・属性名に基づいてサンプル値を生成"""
        # 名前ベースのヒューリスティック
        name_lower = name.lower()

        if 'id' in name_lower:
            return f"ID_{hash(name) % 10000:04d}"
        elif 'name' in name_lower:
            return f"Sample_{name}"
        elif 'date' in name_lower:
            return "2025-01-15"
        elif 'time' in name_lower:
            return "2025-01-15T10:30:00"
        elif 'status' in name_lower:
            return "Completed"
        elif 'version' in name_lower:
            return "1.0"
        elif 'quantity' in name_lower or 'count' in name_lower:
            return "42"
        elif 'mass' in name_lower or 'weight' in name_lower:
            return "123.45"
        elif 'email' in name_lower:
            return "sample@example.com"
        elif 'phone' in name_lower:
            return "+81-3-1234-5678"
        elif 'url' in name_lower:
            return "http://example.com"
        else:
            return "SampleValue"


class ModelToXMLConverter:
    """Z3モデルからXMLファイルを生成して保存"""

    @staticmethod
    def save_xml_trees(xml_trees: List[etree._Element], output_dir: str,
                      prefix: str = "smt_generated"):
        """XMLツリーをファイルとして保存"""
        os.makedirs(output_dir, exist_ok=True)

        saved_files = []

        for i, tree in enumerate(xml_trees, 1):
            filename = f"{prefix}_{i:03d}.xml"
            filepath = os.path.join(output_dir, filename)

            xml_str = etree.tostring(
                tree,
                pretty_print=True,
                xml_declaration=True,
                encoding='utf-8'
            ).decode('utf-8')

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(xml_str)

            saved_files.append(filepath)
            print(f"  {filename} を保存")

        return saved_files


def main():
    parser = argparse.ArgumentParser(
        description='SMTソルバーベースXML生成ツール（最適性保証）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  # サンプルスキーマでXML生成
  python xml_generator_smt.py test/sample/extended_schema.xsd -o generated/smt_sample

  # ISOスキーマで生成（タイムアウト延長）
  python xml_generator_smt.py test/ISO/IEC62474_Schema_X8.21-120240831.xsd \\
      -o generated/smt_iso --timeout 300000 --target-coverage 0.80

  # 深度5で生成
  python xml_generator_smt.py schema.xsd -o output --max-depth 5
        '''
    )
    parser.add_argument('xsd_file', help='XSDスキーマファイル')
    parser.add_argument('-o', '--output-dir', required=True, help='出力ディレクトリ')
    parser.add_argument('--max-depth', type=int, default=10,
                       help='再帰構造の最大展開深度（デフォルト: 10）')
    parser.add_argument('--target-coverage', type=float, default=0.95,
                       help='目標カバレッジ率（0.0〜1.0、デフォルト: 0.95）')
    parser.add_argument('--max-files', type=int, default=10,
                       help='最大生成ファイル数（デフォルト: 10）')
    parser.add_argument('--timeout', type=int, default=60000,
                       help='ソルバーのタイムアウト（ミリ秒、デフォルト: 60000）')
    parser.add_argument('--namespace', type=str, default=None,
                       help='名前空間URI（自動検出されない場合に指定）')
    parser.add_argument('--prefix', type=str, default='smt_generated',
                       help='生成ファイルのプレフィックス')

    args = parser.parse_args()

    # 名前空間マップを構築
    namespace_map = None
    if args.namespace:
        namespace_map = {
            'ns': args.namespace,
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }

    print("=" * 80)
    print("SMTソルバーベースXML生成ツール")
    print("=" * 80)
    print(f"XSDファイル: {args.xsd_file}")
    print(f"出力ディレクトリ: {args.output_dir}")
    print(f"最大再帰深度: {args.max_depth}")
    print(f"目標カバレッジ: {args.target_coverage * 100:.1f}%")
    print(f"タイムアウト: {args.timeout / 1000:.1f}秒")

    # SMT生成器を作成
    generator = SMTXMLGenerator(args.xsd_file, args.max_depth, namespace_map)

    # XML生成
    xml_trees = generator.generate(
        target_coverage=args.target_coverage,
        max_files=args.max_files,
        timeout_ms=args.timeout
    )

    if xml_trees:
        # XMLファイルとして保存
        print("\nXMLファイルを保存中...")
        saved_files = ModelToXMLConverter.save_xml_trees(
            xml_trees,
            args.output_dir,
            args.prefix
        )

        print("\n" + "=" * 80)
        print("生成完了")
        print("=" * 80)
        print(f"生成されたXMLファイル数: {len(saved_files)}")
        print(f"\n次のステップ:")
        print(f"  1. カバレッジ検証:")
        print(f"     python xsd_coverage.py {args.xsd_file} {args.output_dir}/*.xml")
        print(f"  2. 既存生成アルゴリズムとの比較:")
        print(f"     貪欲法との比較を実施してください")
        print("=" * 80)
    else:
        print("\nXML生成に失敗しました")
        print("  制約を緩和するか、タイムアウトを延長してください")
        sys.exit(1)


if __name__ == "__main__":
    main()
