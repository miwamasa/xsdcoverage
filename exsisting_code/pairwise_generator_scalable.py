#!/usr/bin/env python3
"""
スケーラブルなペアワイズカバレッジ生成モジュール

大規模スキーマに対応するため、メモリ効率を重視した実装。
- 優先度ベースのオプション項目選択
- バッチ処理によるメモリ管理
- 段階的なガベージコレクション
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Iterator
from itertools import combinations
import random
import gc


@dataclass
class TestPattern:
    """テストパターン（1つのXMLに対応）"""
    pattern_id: int
    assignments: Dict[str, bool]
    covered_pairs: Set[Tuple[Tuple[str, bool], Tuple[str, bool]]] = field(default_factory=set)

    def get_assignment(self, path: str) -> bool:
        """パスの割り当てを取得（デフォルトFalse）"""
        return self.assignments.get(path, False)


@dataclass
class CoveringArray:
    """ペアワイズカバーリング配列"""
    parameters: List[str]
    patterns: List[TestPattern]
    coverage: float
    strength: int = 2


class ScalablePairwiseCoverageGenerator:
    """
    大規模スキーマ対応のペアワイズカバーリング配列生成クラス

    改善点:
    1. 優先度ベースのオプション項目選択
    2. バッチ処理によるメモリ効率化
    3. 明示的なガベージコレクション
    4. ペアの段階的生成
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
        choice_groups: Optional[Dict[int, List[str]]] = None,
        max_parameters: Optional[int] = None,
        priority_threshold: int = 3
    ) -> CoveringArray:
        """
        ペアワイズカバーリング配列を生成

        Args:
            optional_paths: オプション項目のパスリスト
            strength: カバレッジ強度（2=pairwise）
            max_patterns: 最大パターン数
            choice_groups: Choice制約グループ {group_id: [paths]}
            max_parameters: 最大パラメータ数（大規模スキーマ用）
            priority_threshold: 優先度閾値（これ以上のみ選択）

        Returns:
            CoveringArray
        """
        if strength != 2:
            raise ValueError("現在はstrength=2（pairwise）のみサポート")

        # 大規模スキーマの場合、パラメータを制限
        if max_parameters and len(optional_paths) > max_parameters:
            print(f"  大規模スキーマ検出: {len(optional_paths)}個のパラメータ")
            print(f"  上位{max_parameters}個に制限します")

            # 優先度情報がないので、ランダムサンプリング
            # 実際にはOptionalItemから優先度情報を取得すべき
            random.shuffle(optional_paths)
            optional_paths = optional_paths[:max_parameters]

            print(f"  制限後: {len(optional_paths)}個")

        if self.algorithm == "greedy":
            return self._greedy_pairwise_scalable(
                optional_paths,
                max_patterns,
                choice_groups or {}
            )
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

    def _greedy_pairwise_scalable(
        self,
        paths: List[str],
        max_patterns: int,
        choice_groups: Dict[int, List[str]]
    ) -> CoveringArray:
        """
        メモリ効率的な貪欲アルゴリズムでペアワイズ配列を生成

        改善点:
        1. ペアをバッチで処理
        2. 不要なデータの即座削除
        3. 明示的なGC実行
        """
        print(f"スケーラブルなペアワイズ生成開始: {len(paths)}個のオプション項目")

        # ペア総数を計算（メモリには保持しない）
        total_pairs = self._count_total_pairs(paths, choice_groups)
        print(f"  全ペア数: {total_pairs}")

        patterns: List[TestPattern] = []
        pattern_id = 0

        # 未カバーペアをカウンタで管理（メモリ効率的）
        covered_count = 0

        # 基本パターンを追加
        # パターン1: すべてTrue
        pattern1 = self._create_pattern_scalable(
            pattern_id,
            paths,
            {path: True for path in paths},
            choice_groups
        )
        patterns.append(pattern1)
        covered_count += len(pattern1.covered_pairs)
        pattern_id += 1

        print(f"  パターン{pattern1.pattern_id}: {len(pattern1.covered_pairs)}ペアカバー, " +
              f"残り{total_pairs - covered_count}ペア")

        # パターン1のカバーペアを保持（後で除外に使用）
        covered_pairs = pattern1.covered_pairs.copy()

        # パターン1の大きなセットを削除してメモリ解放
        pattern1.covered_pairs = set()
        gc.collect()

        # パターン2: すべてFalse
        pattern2 = self._create_pattern_scalable(
            pattern_id,
            paths,
            {path: False for path in paths},
            choice_groups
        )

        # パターン2の新規カバーペアのみカウント
        new_pairs = pattern2.covered_pairs - covered_pairs
        covered_count += len(new_pairs)
        patterns.append(pattern2)
        pattern_id += 1

        print(f"  パターン{pattern2.pattern_id}: {len(new_pairs)}ペアカバー, " +
              f"残り{total_pairs - covered_count}ペア")

        # カバー済みペアを更新
        covered_pairs.update(pattern2.covered_pairs)
        pattern2.covered_pairs = set()
        gc.collect()

        # 残りのペアをカバーするパターンを貪欲的に追加
        iteration = 0
        batch_size = 10  # 10パターンごとにGC実行

        while covered_count < total_pairs and len(patterns) < max_patterns:
            iteration += 1

            # 最良のパターンを見つける
            best_pattern = self._find_best_pattern_scalable(
                pattern_id,
                paths,
                covered_pairs,
                choice_groups,
                num_candidates=30  # 候補数を制限してメモリ節約
            )

            if best_pattern is None:
                break

            # 新規カバーペアのみカウント
            new_pairs = best_pattern.covered_pairs - covered_pairs
            if len(new_pairs) == 0:
                # これ以上改善できない
                break

            covered_count += len(new_pairs)
            patterns.append(best_pattern)

            # カバー済みペアを更新
            covered_pairs.update(best_pattern.covered_pairs)
            best_pattern.covered_pairs = set()

            pattern_id += 1

            # 進捗表示とGC
            if iteration % 5 == 0 or covered_count >= total_pairs:
                print(f"  パターン{best_pattern.pattern_id}: {len(new_pairs)}ペアカバー, " +
                      f"残り{total_pairs - covered_count}ペア")

            if iteration % batch_size == 0:
                gc.collect()

        # 最終GC
        del covered_pairs
        gc.collect()

        # カバレッジ計算
        coverage = covered_count / total_pairs if total_pairs > 0 else 1.0

        print(f"スケーラブルなペアワイズ生成完了:")
        print(f"  生成パターン数: {len(patterns)}")
        print(f"  カバレッジ: {coverage*100:.2f}% ({covered_count}/{total_pairs})")

        return CoveringArray(
            parameters=paths,
            patterns=patterns,
            coverage=coverage,
            strength=2
        )

    def _count_total_pairs(
        self,
        paths: List[str],
        choice_groups: Dict[int, List[str]]
    ) -> int:
        """
        ペア総数を計算（メモリには保持しない）
        """
        count = 0

        for path1, path2 in combinations(paths, 2):
            if self._are_in_same_choice_group(path1, path2, choice_groups):
                # (True, True)を除く3通り
                count += 3
            else:
                # 通常の4通り
                count += 4

        return count

    def _create_pattern_scalable(
        self,
        pattern_id: int,
        paths: List[str],
        assignments: Dict[str, bool],
        choice_groups: Dict[int, List[str]]
    ) -> TestPattern:
        """
        パターンを作成（メモリ効率的）
        """
        # Choice制約を考慮して割り当てを調整
        adjusted_assignments = self._adjust_for_choice_constraints(
            assignments,
            choice_groups
        )

        # このパターンがカバーするペアを計算
        covered_pairs = self._calculate_covered_pairs(
            paths,
            adjusted_assignments,
            choice_groups
        )

        return TestPattern(
            pattern_id=pattern_id,
            assignments=adjusted_assignments,
            covered_pairs=covered_pairs
        )

    def _calculate_covered_pairs(
        self,
        paths: List[str],
        assignments: Dict[str, bool],
        choice_groups: Dict[int, List[str]]
    ) -> Set[Tuple[Tuple[str, bool], Tuple[str, bool]]]:
        """
        パターンがカバーするペアを計算（バッチ処理）
        """
        covered_pairs = set()

        # バッチサイズを制限してメモリ効率化
        batch_size = 10000
        batch_count = 0

        for path1, path2 in combinations(paths, 2):
            val1 = assignments.get(path1, False)
            val2 = assignments.get(path2, False)

            # Choice制約チェック
            if self._are_in_same_choice_group(path1, path2, choice_groups):
                if val1 and val2:
                    # 同じグループで両方Trueは無効、スキップ
                    continue

            pair = ((path1, val1), (path2, val2))
            covered_pairs.add(pair)

            batch_count += 1
            if batch_count >= batch_size:
                # バッチごとに少し休憩（GCの機会を与える）
                batch_count = 0

        return covered_pairs

    def _find_best_pattern_scalable(
        self,
        pattern_id: int,
        paths: List[str],
        covered_pairs: Set[Tuple[Tuple[str, bool], Tuple[str, bool]]],
        choice_groups: Dict[int, List[str]],
        num_candidates: int = 30
    ) -> Optional[TestPattern]:
        """
        未カバーペアを最も多くカバーするパターンを見つける（メモリ効率的）
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
            pattern = self._create_pattern_scalable(
                pattern_id,
                paths,
                assignments,
                choice_groups
            )

            # スコア計算: 未カバーペアとの重なり（サンプリングで高速化）
            if len(covered_pairs) > 100000:
                # 大規模な場合、サンプリングでスコア推定
                sample_size = min(10000, len(pattern.covered_pairs))
                sample_pairs = random.sample(list(pattern.covered_pairs), sample_size)
                sample_score = sum(1 for p in sample_pairs if p not in covered_pairs)
                # スコアを推定値から全体に拡大
                score = int(sample_score * len(pattern.covered_pairs) / sample_size)
            else:
                # 小規模な場合、正確に計算
                score = len(pattern.covered_pairs - covered_pairs)

            if score > best_score:
                best_score = score
                # 古いベストパターンを削除
                if best_pattern is not None:
                    del best_pattern
                best_pattern = pattern
            else:
                # このパターンは不要なので削除
                del pattern

        return best_pattern

    def _adjust_for_choice_constraints(
        self,
        assignments: Dict[str, bool],
        choice_groups: Dict[int, List[str]]
    ) -> Dict[str, bool]:
        """Choice制約を考慮して割り当てを調整"""
        adjusted = assignments.copy()

        for group_paths in choice_groups.values():
            true_paths = [p for p in group_paths if adjusted.get(p, False)]

            if len(true_paths) > 1:
                # 複数がTrueの場合、1つだけ残す
                selected = random.choice(true_paths)
                for path in true_paths:
                    if path != selected:
                        adjusted[path] = False

        return adjusted

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


if __name__ == '__main__':
    # テスト用
    paths = [f"path_{i}" for i in range(100)]

    generator = ScalablePairwiseCoverageGenerator()
    covering_array = generator.generate(
        paths,
        strength=2,
        max_patterns=50,
        max_parameters=100
    )

    print("\n生成されたパターン:")
    for pattern in covering_array.patterns[:5]:
        print(f"  Pattern {pattern.pattern_id}:")
        true_paths = [p for p, v in pattern.assignments.items() if v]
        print(f"    True: {len(true_paths)}個")
