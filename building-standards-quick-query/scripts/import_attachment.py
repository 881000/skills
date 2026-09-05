#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_attachment.py —— 把用户上传的规范/规程 PDF 导入「建筑标准速查」技能，
作为内置图集之外的补充查询来源。

导入内容：
  1. 复制 PDF → specs/<原文件名>（同名自动加序号）
  2. 生成全文索引 → references/specs/<编号>.txt（与图集索引同格式，毫秒级快查）
  3. 登记元信息 → specs/manifest.json（编号、标题、原文件名、页数、文字层类型、导入日期）

编号规则：
  - 优先从文件名提取规范编号（如 JGJ18-2012、GB/T 50081-2019 → GB-T50081-2019）；
  - 无规范编号时自动分配 SP-1、SP-2 …；
  - 也可用 --id 手动指定。

用法：
    python scripts/import_attachment.py "E:/下载/JGJ18-2012钢筋焊接及验收规程.pdf"
    python scripts/import_attachment.py "<pdf>" --title "钢筋焊接及验收规程 JGJ18-2012"
    python scripts/import_attachment.py "<pdf>" --id JGJ18-2012 --force   # 指定编号并允许覆盖

依赖：pymupdf
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys

try:
    import pymupdf
except ImportError:  # pragma: no cover
    try:
        import fitz as pymupdf
    except ImportError:
        sys.exit("缺少依赖：请先安装 pymupdf（pip install pymupdf）")

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.abspath(os.path.join(HERE, ".."))
ATTACH_DIR = os.path.join(SKILL_ROOT, "specs")
REF_ATTACH_DIR = os.path.join(SKILL_ROOT, "references", "specs")
MANIFEST = os.path.join(ATTACH_DIR, "manifest.json")


def load_manifest():
    if not os.path.isfile(MANIFEST):
        return {}
    try:
        with open(MANIFEST, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        sys.exit(f"manifest.json 读取失败：{e}")


def save_manifest(data):
    os.makedirs(ATTACH_DIR, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def detect_kind(doc):
    """统计有文字层的页占比，>=50% 记为 text（可关键词检索），否则 scanned（仅可渲染）。"""
    with_text = sum(1 for i in range(doc.page_count) if doc[i].get_text().strip())
    ratio = with_text / doc.page_count if doc.page_count else 0
    return "text" if ratio >= 0.5 else "scanned"


def extract_spec_id(filename):
    """从文件名提取规范编号（如 JGJ18-2012、GB/T 50081-2019），提取不到返回 None。

    编号中的斜杠安全化为连字符、空格去除（Windows 文件名与 CLI 参数兼容）。
    """
    m = re.search(r"(?<![0-9A-Z])[A-Z]{1,6}(?:/[A-Z]{0,3})?\s*\d{1,5}(?:-\d{4})?", filename)
    if not m:
        return None
    return re.sub(r"\s+", "", re.sub(r"/", "-", m.group(0)))


def next_id(manifest):
    nums = []
    for k in manifest:
        m = re.match(r"^SP-(\d+)$", k)
        if m:
            nums.append(int(m.group(1)))
    return f"SP-{max(nums) + 1 if nums else 1}"


def main():
    ap = argparse.ArgumentParser(description="导入用户上传的规范/规程 PDF 到技能（编号如 JGJ18-2012）")
    ap.add_argument("pdf", help="要导入的 PDF 路径")
    ap.add_argument("--id", default=None, help="规范编号（默认从文件名提取，如 JGJ18-2012；无编号时自动 SP-N）")
    ap.add_argument("--title", default=None, help="规范标题（默认取 PDF 元数据或文件名）")
    ap.add_argument("--force", action="store_true", help="编号已存在时覆盖")
    args = ap.parse_args()

    if not os.path.isfile(args.pdf):
        sys.exit(f"未找到 PDF：{args.pdf}")
    if not args.pdf.lower().endswith(".pdf"):
        sys.exit("仅支持 PDF 文件")

    doc = pymupdf.open(args.pdf)
    pages = doc.page_count
    kind = detect_kind(doc)
    meta_title = (doc.metadata.get("title") or "").strip()
    doc.close()

    original = os.path.basename(args.pdf)
    manifest = load_manifest()

    # 同名文件重复导入检测
    existing_key = next((k for k, v in manifest.items()
                         if v.get("original_name") == original), None)
    if existing_key and not args.force:
        print(f"[提示] {original} 已导入为 {existing_key}（标题："
              f"{manifest[existing_key].get('title')}）。如需覆盖请加 --force。")
        return

    att_id = args.id or extract_spec_id(original) or next_id(manifest)
    if att_id in manifest and not args.force:
        sys.exit(f"编号 {att_id} 已存在（{manifest[att_id].get('original_name')}）。"
                 f"请换编号或加 --force。")
    if existing_key and existing_key != att_id:
        sys.exit(f"该文件已登记为 {existing_key}，不能用编号 {att_id} 覆盖"
                 f"（同一文件只能对应一个编号）。如需替换内容请用 --id {existing_key} --force。")

    # 复制 PDF（同名冲突时加序号）
    dest = os.path.join(ATTACH_DIR, original)
    if os.path.exists(dest) and not args.force:
        stem, ext = os.path.splitext(original)
        n = 2
        while os.path.exists(dest):
            dest = os.path.join(ATTACH_DIR, f"{stem}({n}){ext}")
            n += 1
    os.makedirs(ATTACH_DIR, exist_ok=True)
    shutil.copy2(args.pdf, dest)

    # 生成全文索引（与图集索引同格式：每页以 --- PDF页N --- 分隔）
    os.makedirs(REF_ATTACH_DIR, exist_ok=True)
    idx_path = os.path.join(REF_ATTACH_DIR, f"{att_id}.txt")
    doc = pymupdf.open(dest)
    with open(idx_path, "w", encoding="utf-8") as f:
        for i in range(doc.page_count):
            f.write(f"--- PDF页{i + 1} ---\n")
            f.write(doc[i].get_text())
    doc.close()

    title = args.title or (meta_title if meta_title else os.path.splitext(original)[0])
    manifest[att_id] = {
        "file": os.path.basename(dest),
        "original_name": original,
        "title": title,
        "pages": pages,
        "kind": kind,
        "imported_at": datetime.date.today().isoformat(),
    }
    save_manifest(manifest)

    print(f"[完成] 已导入规范 {att_id}：{title}")
    print(f"  PDF：{dest}")
    print(f"  索引：{idx_path}（{pages} 页，{kind} 类型）")
    print("后续用法：")
    print(f"  python scripts/search_atlas.py --keywords \"钢筋焊接\" --spec {att_id}")
    print(f"  python scripts/search_atlas.py --render \"{att_id}:5\" --out-dir ./out")


if __name__ == "__main__":
    main()
