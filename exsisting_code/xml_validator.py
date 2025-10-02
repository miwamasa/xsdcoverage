#!/usr/bin/env python3
"""
XMLバリデーションツール

XSDスキーマに対してXMLファイルをバリデーションし、結果をレポートします。
"""

import sys
import os
import argparse
from lxml import etree
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """バリデーション結果"""
    xml_file: str
    is_valid: bool
    error_message: Optional[str] = None
    error_details: Optional[List[str]] = None


class XMLValidator:
    """XMLバリデーションクラス"""

    def __init__(self, xsd_path: str):
        """
        Args:
            xsd_path: XSDスキーマファイルのパス
        """
        self.xsd_path = xsd_path
        self.schema = self._load_schema()

    def _load_schema(self) -> etree.XMLSchema:
        """XSDスキーマを読み込む"""
        try:
            schema_doc = etree.parse(self.xsd_path)
            return etree.XMLSchema(schema_doc)
        except Exception as e:
            print(f"エラー: XSDスキーマの読み込みに失敗しました: {e}", file=sys.stderr)
            sys.exit(1)

    def validate_file(self, xml_path: str) -> ValidationResult:
        """
        XMLファイルをバリデーション

        Args:
            xml_path: XMLファイルのパス

        Returns:
            ValidationResult
        """
        try:
            xml_doc = etree.parse(xml_path)
            is_valid = self.schema.validate(xml_doc)

            if is_valid:
                return ValidationResult(
                    xml_file=xml_path,
                    is_valid=True
                )
            else:
                # エラー詳細を取得
                error_log = self.schema.error_log
                error_details = []
                for error in error_log:
                    error_details.append(
                        f"  Line {error.line}: {error.message}"
                    )

                return ValidationResult(
                    xml_file=xml_path,
                    is_valid=False,
                    error_message=str(error_log),
                    error_details=error_details
                )

        except etree.XMLSyntaxError as e:
            return ValidationResult(
                xml_file=xml_path,
                is_valid=False,
                error_message=f"XML構文エラー: {e}",
                error_details=[f"  {e}"]
            )
        except Exception as e:
            return ValidationResult(
                xml_file=xml_path,
                is_valid=False,
                error_message=f"予期しないエラー: {e}",
                error_details=[f"  {e}"]
            )

    def validate_files(self, xml_paths: List[str]) -> List[ValidationResult]:
        """
        複数のXMLファイルをバリデーション

        Args:
            xml_paths: XMLファイルパスのリスト

        Returns:
            ValidationResultのリスト
        """
        results = []
        for xml_path in xml_paths:
            result = self.validate_file(xml_path)
            results.append(result)
        return results


def print_summary(results: List[ValidationResult]):
    """バリデーション結果のサマリーを表示"""
    total = len(results)
    valid_count = sum(1 for r in results if r.is_valid)
    invalid_count = total - valid_count

    print("\n" + "=" * 80)
    print("バリデーション結果サマリー")
    print("=" * 80)
    print(f"総XMLファイル数: {total}")
    print(f"✓ Valid:   {valid_count} ({valid_count/total*100:.1f}%)" if total > 0 else "✓ Valid:   0")
    print(f"✗ Invalid: {invalid_count} ({invalid_count/total*100:.1f}%)" if total > 0 else "✗ Invalid: 0")
    print()


def print_detailed_results(results: List[ValidationResult], show_valid: bool = False):
    """詳細なバリデーション結果を表示"""
    print("=" * 80)
    print("詳細結果")
    print("=" * 80)
    print()

    # Valid なファイル
    if show_valid:
        valid_results = [r for r in results if r.is_valid]
        if valid_results:
            print(f"【Valid なXMLファイル ({len(valid_results)}個)】")
            for result in valid_results:
                print(f"  ✓ {result.xml_file}")
            print()

    # Invalid なファイル
    invalid_results = [r for r in results if not r.is_valid]
    if invalid_results:
        print(f"【Invalid なXMLファイル ({len(invalid_results)}個)】")
        for result in invalid_results:
            print(f"  ✗ {result.xml_file}")
            if result.error_details:
                for detail in result.error_details:
                    print(f"    {detail}")
            print()
    else:
        print("すべてのXMLファイルがValidです！")
        print()


def save_report(results: List[ValidationResult], output_path: str):
    """バリデーション結果をファイルに保存"""
    total = len(results)
    valid_count = sum(1 for r in results if r.is_valid)
    invalid_count = total - valid_count

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("XMLバリデーション結果レポート\n")
        f.write("=" * 80 + "\n\n")

        # サマリー
        f.write("【サマリー】\n")
        f.write(f"総XMLファイル数: {total}\n")
        f.write(f"✓ Valid:   {valid_count} ({valid_count/total*100:.1f}%)\n" if total > 0 else "✓ Valid:   0\n")
        f.write(f"✗ Invalid: {invalid_count} ({invalid_count/total*100:.1f}%)\n" if total > 0 else "✗ Invalid: 0\n")
        f.write("\n")

        # Valid なファイル
        valid_results = [r for r in results if r.is_valid]
        if valid_results:
            f.write(f"【Valid なXMLファイル ({len(valid_results)}個)】\n")
            for result in valid_results:
                f.write(f"  ✓ {result.xml_file}\n")
            f.write("\n")

        # Invalid なファイル
        invalid_results = [r for r in results if not r.is_valid]
        if invalid_results:
            f.write(f"【Invalid なXMLファイル ({len(invalid_results)}個)】\n")
            for result in invalid_results:
                f.write(f"  ✗ {result.xml_file}\n")
                if result.error_details:
                    for detail in result.error_details:
                        f.write(f"    {detail}\n")
                f.write("\n")

        f.write("=" * 80 + "\n")

    print(f"レポートを {output_path} に保存しました")


def main():
    parser = argparse.ArgumentParser(
        description='XMLバリデーションツール - XSDスキーマに対してXMLファイルをバリデーション',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 単一XMLファイルをバリデーション
  python xml_validator.py schema.xsd data.xml

  # 複数XMLファイルをバリデーション
  python xml_validator.py schema.xsd data1.xml data2.xml data3.xml

  # ワイルドカード使用
  python xml_validator.py schema.xsd generated/*.xml

  # 結果をファイルに保存
  python xml_validator.py schema.xsd generated/*.xml -o validation_report.txt

  # Valid なファイルも表示
  python xml_validator.py schema.xsd generated/*.xml --show-valid
        """
    )

    parser.add_argument(
        'xsd_file',
        help='XSDスキーマファイルのパス'
    )
    parser.add_argument(
        'xml_files',
        nargs='+',
        help='バリデーションするXMLファイル（複数指定可能）'
    )
    parser.add_argument(
        '-o', '--output',
        help='結果を保存するファイルパス（指定しない場合は標準出力のみ）'
    )
    parser.add_argument(
        '--show-valid',
        action='store_true',
        help='Valid なファイルも詳細表示する'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='エラーのみ表示（サマリーと invalid なファイルのみ）'
    )

    args = parser.parse_args()

    # XSDファイルの存在確認
    if not os.path.exists(args.xsd_file):
        print(f"エラー: XSDファイルが見つかりません: {args.xsd_file}", file=sys.stderr)
        sys.exit(1)

    # XMLファイルの存在確認
    xml_files = []
    for xml_file in args.xml_files:
        if os.path.exists(xml_file):
            xml_files.append(xml_file)
        else:
            print(f"警告: XMLファイルが見つかりません（スキップ）: {xml_file}", file=sys.stderr)

    if not xml_files:
        print("エラー: 有効なXMLファイルがありません", file=sys.stderr)
        sys.exit(1)

    # バリデーション実行
    print(f"XSDスキーマ: {args.xsd_file}")
    print(f"XMLファイル数: {len(xml_files)}")
    print()
    print("バリデーション実行中...")

    validator = XMLValidator(args.xsd_file)
    results = validator.validate_files(xml_files)

    # 結果表示
    if not args.quiet:
        print_summary(results)
        print_detailed_results(results, show_valid=args.show_valid)
    else:
        print_summary(results)
        # エラーのみ表示
        invalid_results = [r for r in results if not r.is_valid]
        if invalid_results:
            print("【Invalid なXMLファイル】")
            for result in invalid_results:
                print(f"  ✗ {result.xml_file}")
                if result.error_details:
                    for detail in result.error_details:
                        print(f"    {detail}")
            print()

    # ファイルに保存
    if args.output:
        save_report(results, args.output)

    # 終了コード
    invalid_count = sum(1 for r in results if not r.is_valid)
    sys.exit(0 if invalid_count == 0 else 1)


if __name__ == '__main__':
    main()
