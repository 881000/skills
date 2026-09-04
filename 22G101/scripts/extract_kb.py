#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_kb.py —— 从 assets/ 下的文字版图集 PDF 重建 references/*.txt 全文索引。

用途：一次性维护用。txt 是关键词快查索引（秒级），由 PDF 文字层导出，
每页以 "--- PDF页N ---" 分隔；渲染原图仍走 assets/ 的源 PDF。
一般无需运行，仅在源 PDF 更新或索引缺失时执行。

用法：
    python scripts/extract_kb.py            # 重建全部文字版图集的 txt
    python scripts/extract_kb.py --atlas 22G101-2   # 只重建指定分册

依赖：pymupdf
"""
import argparse
import os
import sys

try:
    import pymupdf
except ImportError:  # pragma: no cover
    try:
        import fitz as pymupdf
    except ImportError:
        sys.exit("缺少依赖：请先安装 pymupdf（pip install pymupdf）")

TEXT_ATLAS = {
    "22G101-1": "22G101-1现浇混凝土框架、剪力墙、梁、板.pdf",
    "22G101-2": "22G101-2现浇混凝土板式楼梯.pdf",
    "22G101-3": "22G101-3独立基础、条形基础、筏形基础、桩基础.pdf",
    "23G101-11": "23G101-11 G101系列图集常见问题答疑图解.pdf",
}


def main():
    ap = argparse.ArgumentParser(description="从文字版图集 PDF 重建 references/*.txt 全文索引")
    ap.add_argument("--atlas", default=None, help="只重建指定分册（如 22G101-1），默认全部")
    ap.add_argument("--assets-dir", default=None, help="assets 目录（默认脚本上级目录）")
    ap.add_argument("--ref-dir", default=None, help="references 输出目录（默认脚本上级目录）")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    assets_dir = args.assets_dir or os.path.abspath(os.path.join(here, "..", "assets"))
    ref_dir = args.ref_dir or os.path.abspath(os.path.join(here, "..", "references"))
    os.makedirs(ref_dir, exist_ok=True)

    targets = [args.atlas] if args.atlas else list(TEXT_ATLAS)
    for key in targets:
        if key not in TEXT_ATLAS:
            print(f"[跳过] {key} 不是文字版图集（可用：{list(TEXT_ATLAS)}）")
            continue
        pdf_path = os.path.join(assets_dir, TEXT_ATLAS[key])
        if not os.path.isfile(pdf_path):
            print(f"[跳过] 未找到源 PDF：{pdf_path}")
            continue
        doc = pymupdf.open(pdf_path)
        total = doc.page_count
        out_path = os.path.join(ref_dir, f"{key}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            for i in range(total):
                f.write(f"--- PDF页{i + 1} ---\n")
                f.write(doc[i].get_text())
        doc.close()
        print(f"[完成] {key}.txt（{total} 页）→ {out_path}")


if __name__ == "__main__":
    main()
