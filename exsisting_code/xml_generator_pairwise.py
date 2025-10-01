#!/usr/bin/env python3
"""
ペアワイズXML生成ツール

組合せテストの理論に基づき、すべてのオプション項目のペア（2-way組合せ）を
カバーする最小のXMLテストデータセットを生成する。

【アルゴリズムの概要】
1. XSDからオプション項目（minOccurs="0"要素、optional属性、choice要素）を抽出
2. ペアワイズカバーリング配列を生成（Greedyアルゴリズム）
3. 各テストパターンからXMLを構築
4. 生成されたXMLファイルを保存

詳細は spec/pairwise_algorithm.md を参照
"""

import sys
import os
import argparse
from lxml import etree
from optional_extractor import OptionalElementExtractor
from pairwise_generator import PairwiseCoverageGenerator
from pairwise_xml_builder import PairwiseXMLBuilder


def main():
    parser = argparse.ArgumentParser(
        description='ペアワイズXML生成ツール - 組合せテストに基づくテストデータ生成'
    )
    parser.add_argument(
        'xsd_file',
        help='XSDスキーマファイルのパス'
    )
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='出力ディレクトリ'
    )
    parser.add_argument(
        '--max-depth',
        type=int,
        default=10,
        help='XSD解析の最大再帰深度（デフォルト: 10）'
    )
    parser.add_argument(
        '--max-patterns',
        type=int,
        default=50,
        help='最大パターン数（デフォルト: 50）'
    )
    parser.add_argument(
        '--namespace',
        action='append',
        help='名前空間の追加（形式: PREFIX=URI）。複数指定可能'
    )
    parser.add_argument(
        '--random-seed',
        type=int,
        default=42,
        help='乱数シード（デフォルト: 42）'
    )

    args = parser.parse_args()

    # 名前空間マップの構築
    namespace_map = {}
    if args.namespace:
        for ns_spec in args.namespace:
            if '=' in ns_spec:
                prefix, uri = ns_spec.split('=', 1)
                namespace_map[prefix] = uri
            else:
                # プレフィックスなしの場合はデフォルト名前空間
                namespace_map['ns'] = ns_spec

    print("================================================================================")
    print("ペアワイズXML生成ツール")
    print("================================================================================")
    print(f"XSDファイル: {args.xsd_file}")
    print(f"出力ディレクトリ: {args.output}")
    print(f"最大深度: {args.max_depth}")
    print(f"最大パターン数: {args.max_patterns}")
    print()

    # 出力ディレクトリの作成
    os.makedirs(args.output, exist_ok=True)

    # Step 1: オプション項目を抽出
    print("Step 1: オプション項目を抽出中...")
    extractor = OptionalElementExtractor(args.xsd_file)
    optional_items = extractor.extract(
        max_depth=args.max_depth,
        include_unbounded=True
    )

    print(f"  オプション要素: {len(extractor.get_optional_elements())}個")
    print(f"  オプション属性: {len(extractor.get_optional_attributes())}個")
    print(f"  合計: {len(optional_items)}個")

    choice_groups = extractor.get_choice_groups()
    if choice_groups:
        print(f"  Choiceグループ: {len(choice_groups)}組")

    print()

    # Step 2: ペアワイズカバーリング配列を生成
    print("Step 2: ペアワイズカバーリング配列を生成中...")
    optional_paths = [item.path for item in optional_items]

    generator = PairwiseCoverageGenerator(
        algorithm="greedy",
        random_seed=args.random_seed
    )

    covering_array = generator.generate(
        optional_paths=optional_paths,
        strength=2,
        max_patterns=args.max_patterns,
        choice_groups=choice_groups
    )

    print(f"  生成されたパターン数: {len(covering_array.patterns)}")
    print(f"  ペアカバレッジ: {covering_array.coverage*100:.2f}%")
    print()

    # Step 3: 各パターンからXMLを構築
    print("Step 3: パターンからXMLを構築中...")
    builder = PairwiseXMLBuilder(
        xsd_path=args.xsd_file,
        max_depth=args.max_depth,
        namespace_map=namespace_map
    )

    generated_files = []

    for pattern in covering_array.patterns:
        try:
            xml_elem = builder.build_xml(pattern)

            # XMLを文字列化
            xml_str = etree.tostring(
                xml_elem,
                pretty_print=True,
                xml_declaration=True,
                encoding='utf-8'
            ).decode('utf-8')

            # ファイル名を生成
            filename = f"pairwise_test_{pattern.pattern_id:03d}.xml"
            filepath = os.path.join(args.output, filename)

            # ファイルに保存
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(xml_str)

            generated_files.append(filepath)

            # 進捗表示
            if (pattern.pattern_id + 1) % 10 == 0 or pattern.pattern_id == len(covering_array.patterns) - 1:
                print(f"  {pattern.pattern_id + 1}/{len(covering_array.patterns)} ファイル生成完了")

        except Exception as e:
            print(f"  警告: パターン{pattern.pattern_id}のXML生成に失敗: {e}")
            continue

    print()

    # 完了サマリー
    print("================================================================================")
    print("生成完了")
    print("================================================================================")
    print(f"生成されたXMLファイル数: {len(generated_files)}")
    print(f"ペアカバレッジ: {covering_array.coverage*100:.2f}%")
    print()
    print("次のステップ:")
    print("  1. カバレッジ検証:")
    print(f"     python xsd_coverage.py {args.xsd_file} {args.output}/*.xml")
    print("  2. 既存生成アルゴリズムとの比較:")
    print("     貪欲法やSMTソルバーとの比較を実施してください")
    print("================================================================================")


if __name__ == '__main__':
    main()
