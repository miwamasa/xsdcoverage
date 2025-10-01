#!/usr/bin/env python3
"""
ペアワイズカバレッジ生成モジュール

組合せテストの理論に基づき、すべてのオプション項目のペア（2-way組合せ）を
カバーする最小のテストパターンを生成する。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional
from itertools import combinations
import random


@dataclass
class TestPattern:
    """
    テストパターン（1つのXMLに対応）

    Attributes:
        pattern_id: パターンID
        assignments: {path: True/False} のマッピング
        covered_pairs: このパターンがカバーするペアの集合
    """
    pattern_id: int
    assignments: Dict[str, bool]
    covered_pairs: Set[Tuple[Tuple[str, bool], Tuple[str, bool]]] = field(default_factory=set)

    def get_assignment(self, path: str) -> bool:
        """パスの割り当てを取得（デフォルトFalse）"""
        return self.assignments.get(path, False)


@dataclass
class CoveringArray:
    """
    ペアワイズカバーリング配列

    Attributes:
        parameters: オプション項目のパスリスト
        patterns: テストパターンのリスト
        coverage: ペアカバレッジ率
        strength: カバレッジ強度（2=pairwise）
    """
    parameters: List[str]
    patterns: List[TestPattern]
    coverage: float
    strength: int = 2


class PairwiseCoverageGenerator:
    """
    ペアワイズカバーリング配列を生成するクラス

    Greedy アルゴリズムを使用して、すべての2-wayペアを
    カバーする最小のパターンセットを生成する。
    """

    def __init__(self, algorithm: str = "greedy", random_seed: int = 42):
        """
        Args:
            algorithm: "greedy" のみサポート
            random_seed: 乱数シード
        """
        self.algorithm = algorithm
        random.seed(random_seed)

    def generate(
        self,
        optional_paths: List[str],
        strength: int = 2,
        max_patterns: int = 100,
        choice_groups: Optional[Dict[int, List[str]]] = None
    ) -> CoveringArray:
        """
        ペアワイズカバーリング配列を生成

        Args:
            optional_paths: オプション項目のパスリスト
            strength: カバレッジ強度（2=pairwise）
            max_patterns: 最大パターン数
            choice_groups: Choice制約グループ {group_id: [paths]}

        Returns:
            CoveringArray
        """
        if strength != 2:
            raise ValueError("現在はstrength=2（pairwise）のみサポート")

        if self.algorithm == "greedy":
            return self._greedy_pairwise(
                optional_paths,
                max_patterns,
                choice_groups or {}
            )
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

    def _greedy_pairwise(
        self,
        paths: List[str],
        max_patterns: int,
        choice_groups: Dict[int, List[str]]
    ) -> CoveringArray:
        """
        貪欲アルゴリズムでペアワイズ配列を生成

        手順:
        1. すべてのペア（2-way組合せ）を列挙
        2. 未カバーのペアを最も多くカバーするパターンを追加
        3. すべてのペアがカバーされるまで繰り返し
        """
        print(f"ペアワイズ生成開始: {len(paths)}個のオプション項目")

        # すべてのペアを列挙
        all_pairs = self._enumerate_all_pairs(paths, choice_groups)
        print(f"  全ペア数: {len(all_pairs)}")

        uncovered_pairs = set(all_pairs)
        patterns: List[TestPattern] = []
        pattern_id = 0

        # 基本パターンを追加
        # パターン1: すべてTrue
        pattern1 = self._create_pattern(
            pattern_id,
            paths,
            {path: True for path in paths},
            choice_groups
        )
        patterns.append(pattern1)
        uncovered_pairs -= pattern1.covered_pairs
        pattern_id += 1
        print(f"  パターン{pattern1.pattern_id}: {len(pattern1.covered_pairs)}ペアカバー, 残り{len(uncovered_pairs)}ペア")

        # パターン2: すべてFalse
        pattern2 = self._create_pattern(
            pattern_id,
            paths,
            {path: False for path in paths},
            choice_groups
        )
        patterns.append(pattern2)
        uncovered_pairs -= pattern2.covered_pairs
        pattern_id += 1
        print(f"  パターン{pattern2.pattern_id}: {len(pattern2.covered_pairs)}ペアカバー, 残り{len(uncovered_pairs)}ペア")

        # 残りのペアをカバーするパターンを貪欲的に追加
        iteration = 0
        while uncovered_pairs and len(patterns) < max_patterns:
            iteration += 1

            # 最も多くの未カバーペアをカバーするパターンを見つける
            best_pattern = self._find_best_pattern(
                pattern_id,
                paths,
                uncovered_pairs,
                choice_groups,
                num_candidates=50  # 候補数を制限して高速化
            )

            if best_pattern is None or len(best_pattern.covered_pairs) == 0:
                # これ以上改善できない
                break

            patterns.append(best_pattern)
            uncovered_pairs -= best_pattern.covered_pairs
            pattern_id += 1

            if iteration % 5 == 0 or len(uncovered_pairs) == 0:
                print(f"  パターン{best_pattern.pattern_id}: {len(best_pattern.covered_pairs)}ペアカバー, 残り{len(uncovered_pairs)}ペア")

        # カバレッジ計算
        total_pairs = len(all_pairs)
        covered_pairs = total_pairs - len(uncovered_pairs)
        coverage = covered_pairs / total_pairs if total_pairs > 0 else 1.0

        print(f"ペアワイズ生成完了:")
        print(f"  生成パターン数: {len(patterns)}")
        print(f"  カバレッジ: {coverage*100:.2f}% ({covered_pairs}/{total_pairs})")

        return CoveringArray(
            parameters=paths,
            patterns=patterns,
            coverage=coverage,
            strength=2
        )

    def _enumerate_all_pairs(
        self,
        paths: List[str],
        choice_groups: Dict[int, List[str]]
    ) -> Set[Tuple[Tuple[str, bool], Tuple[str, bool]]]:
        """
        すべてのペアを列挙

        各パラメータは True/False の2値を取るので、
        ペアは ((path1, value1), (path2, value2)) の形式

        Returns:
            ペアの集合
        """
        pairs = set()

        # すべてのパスのペアを列挙
        for path1, path2 in combinations(paths, 2):
            # choice制約のチェック: 同じグループなら両方Trueは不可
            if self._are_in_same_choice_group(path1, path2, choice_groups):
                # (True, True)の組合せは除外
                pairs.add(((path1, True), (path2, False)))
                pairs.add(((path1, False), (path2, True)))
                pairs.add(((path1, False), (path2, False)))
            else:
                # 通常のペア（4通り）
                pairs.add(((path1, True), (path2, True)))
                pairs.add(((path1, True), (path2, False)))
                pairs.add(((path1, False), (path2, True)))
                pairs.add(((path1, False), (path2, False)))

        return pairs

    def _are_in_same_choice_group(
        self,
        path1: str,
        path2: str,
        choice_groups: Dict[int, List[str]]
    ) -> bool:
        """2つのパスが同じchoiceグループに属するか"""
        for group_paths in choice_groups.values():
            if path1 in group_paths and path2 in group_paths:
                return True
        return False

    def _create_pattern(
        self,
        pattern_id: int,
        paths: List[str],
        assignments: Dict[str, bool],
        choice_groups: Dict[int, List[str]]
    ) -> TestPattern:
        """
        パターンを作成し、カバーするペアを計算

        Args:
            pattern_id: パターンID
            paths: すべてのオプションパス
            assignments: 割り当て
            choice_groups: Choice制約

        Returns:
            TestPattern
        """
        # Choice制約を考慮して割り当てを調整
        adjusted_assignments = self._adjust_for_choice_constraints(
            assignments,
            choice_groups
        )

        # このパターンがカバーするペアを計算
        covered_pairs = set()
        for path1, path2 in combinations(paths, 2):
            val1 = adjusted_assignments.get(path1, False)
            val2 = adjusted_assignments.get(path2, False)

            pair = ((path1, val1), (path2, val2))
            covered_pairs.add(pair)

        return TestPattern(
            pattern_id=pattern_id,
            assignments=adjusted_assignments,
            covered_pairs=covered_pairs
        )

    def _adjust_for_choice_constraints(
        self,
        assignments: Dict[str, bool],
        choice_groups: Dict[int, List[str]]
    ) -> Dict[str, bool]:
        """
        Choice制約を考慮して割り当てを調整

        同じグループで複数がTrueになっている場合、1つだけTrueにする
        """
        adjusted = assignments.copy()

        for group_paths in choice_groups.values():
            true_paths = [p for p in group_paths if adjusted.get(p, False)]

            if len(true_paths) > 1:
                # 複数がTrueの場合、1つだけ残す（ランダムに選択）
                selected = random.choice(true_paths)
                for path in true_paths:
                    if path != selected:
                        adjusted[path] = False

        return adjusted

    def _find_best_pattern(
        self,
        pattern_id: int,
        paths: List[str],
        uncovered_pairs: Set[Tuple[Tuple[str, bool], Tuple[str, bool]]],
        choice_groups: Dict[int, List[str]],
        num_candidates: int = 50
    ) -> Optional[TestPattern]:
        """
        未カバーペアを最も多くカバーするパターンを見つける

        ランダムなパターンを複数生成し、最良のものを選択する
        """
        best_pattern = None
        best_score = 0

        for _ in range(num_candidates):
            # ランダムな割り当てを生成
            assignments = {
                path: random.choice([True, False])
                for path in paths
            }

            # パターンを作成
            pattern = self._create_pattern(
                pattern_id,
                paths,
                assignments,
                choice_groups
            )

            # スコア計算: 未カバーペアとの重なり
            score = len(pattern.covered_pairs & uncovered_pairs)

            if score > best_score:
                best_score = score
                best_pattern = pattern

        return best_pattern


if __name__ == '__main__':
    # テスト用
    paths = [f"path_{i}" for i in range(10)]

    generator = PairwiseCoverageGenerator()
    covering_array = generator.generate(paths, strength=2, max_patterns=20)

    print("\n生成されたパターン:")
    for pattern in covering_array.patterns:
        print(f"  Pattern {pattern.pattern_id}:")
        true_paths = [p for p, v in pattern.assignments.items() if v]
        print(f"    True: {len(true_paths)}個")
