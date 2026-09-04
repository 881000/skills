# -*- coding: utf-8 -*-
"""从 22G101 三册源 PDF 导出指定页为高清 PNG 图片，用于向用户提供图集原文图片（图纸/表格原样）。

用法:
    python pdf_page_to_image.py --volume 1|2|3 --pages 68         # 单页
    python pdf_page_to_image.py --volume 1 --pages 68-70         # 连续范围
    python pdf_page_to_image.py --volume 3 --pages 104,105,110   # 多页
    python pdf_page_to_image.py --volume 2 --pages 17 --dpi 200  # 指定清晰度

参数:
    --volume   分册：1=22G101-1 框架/剪力墙/梁/板，2=22G101-2 板式楼梯，3=22G101-3 基础
    --pages    页码，支持单页、范围(如 68-70)、逗号组合(如 68,70,72)；均为 PDF 物理页号
    --dpi      导出清晰度，默认 150（图纸细节较多可加大到 200-300）
    --out      输出目录，默认 <技能目录>/output/

输出:
    每页一张 PNG，命名如 22G101-1_p068.png；页序与 --pages 输入一致。
"""
import argparse, os, re
import pymupdf

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(SKILL_DIR, "output")

VOLUME_PATHS = {
    "1": r"E:\下载\22G101规范图集\22G101-1现浇混凝土框架、剪力墙、梁、板.pdf",
    "2": r"E:\下载\22G101规范图集\22G101-2现浇混凝土板式楼梯.pdf",
    "3": r"E:\下载\22G101规范图集\22G101-3独立基础、条形基础、筏形基础、桩基础.pdf",
}
VOLUME_TAG = {"1": "22G101-1", "2": "22G101-2", "3": "22G101-3"}


def parse_pages(spec):
    """解析页码：'68' / '68-70' / '68,70,72' 等组合。"""
    pages = []
    for part in spec.split(","):
        part = part.strip()
        m = re.match(r"^(\d+)-(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                a, b = b, a
            pages.extend(range(a, b + 1))
        elif part.isdigit():
            pages.append(int(part))
        else:
            raise ValueError(f"无法解析页码: {part!r}")
    return pages


def main():
    ap = argparse.ArgumentParser(description="导出 22G101 图集指定页为原文图片")
    ap.add_argument("--volume", required=True, choices=["1", "2", "3"], help="分册号")
    ap.add_argument("--pages", required=True, help="PDF 页码，如 68 / 68-70 / 68,70,72")
    ap.add_argument("--dpi", type=int, default=150, help="清晰度 DPI，默认 150")
    ap.add_argument("--out", default=DEFAULT_OUT, help="输出目录")
    args = ap.parse_args()

    pdf = VOLUME_PATHS[args.volume]
    if not os.path.exists(pdf):
        print(f"[错误] 源 PDF 不存在：{pdf}")
        return 1
    pages = parse_pages(args.pages)
    if not pages:
        print("[错误] 未解析到有效页码")
        return 1

    os.makedirs(args.out, exist_ok=True)
    doc = pymupdf.open(pdf)
    if max(pages) > doc.page_count:
        print(f"[错误] 页码超出范围：共 {doc.page_count} 页，但请求到第 {max(pages)} 页")
        doc.close()
        return 1

    zoom = args.dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    tag = VOLUME_TAG[args.volume]
    results = []
    for p in pages:
        page = doc[p - 1]
        pix = page.get_pixmap(matrix=mat)
        fp = os.path.join(args.out, f"{tag}_p{p:03d}.png")
        pix.save(fp)
        results.append(fp)
        print(f"[OK] {tag} 第{p}页 -> {fp}（{pix.width}x{pix.height}px，{args.dpi}dpi）")
    doc.close()
    print(f"\n共导出 {len(results)} 张原文图片到：{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
