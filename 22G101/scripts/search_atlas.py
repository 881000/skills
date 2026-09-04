#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
混凝土结构施工图查询脚本（22G101 / 23G101 系列图集）

功能：
  1. 检索模式（默认）：在文字版图集中按关键词定位页码，返回原文与图集内部页码。
  2. 页码换算（--map）：把扫描版图集（23G101-11）的内部页码换算为 PDF 页码，免去逐页翻图。
  3. 渲染模式（--render / --toc）：把指定 PDF 页渲染为 PNG，供扫描版图集或查看构造图时视觉读取。

图集数据位置：assets/ 下的 4 个官方 PDF。
依赖：pymupdf（import pymupdf，兼容 import fitz 旧别名）。

用法示例：
  # 在全部图集中检索“锚固长度”
  python search_atlas.py --keywords "锚固长度"

  # 只在 22G101-1 中检索多个关键词
  python search_atlas.py --keywords "梁柱节点" "箍筋加密区" --atlas 22G101-1

  # 扫描版图集：先看章节首页映射，再把内部页码 2-3 换算成 PDF 页码
  python search_atlas.py --map 23G101-11
  python search_atlas.py --map 23G101-11:2-3

  # 渲染换算得到的 PDF 页（如 2-3 → PDF 38），读取原文
  python search_atlas.py --render "23G101-11:38"

  # 渲染 23G101-11 的目录页（定位问题条目）
  python search_atlas.py --toc 23G101-11

  # 渲染某页大图用于查看构造详图
  python search_atlas.py --render "22G101-1:35"
"""

import argparse
import json
import os
import re
import sys

try:
    import pymupdf  # PyMuPDF 1.24+
except ImportError:  # pragma: no cover
    try:
        import fitz as pymupdf
    except ImportError:
        sys.exit("缺少依赖：请先安装 pymupdf（pip install pymupdf）")

# ---------------------------------------------------------------------------
# 图集元信息
# ---------------------------------------------------------------------------
ATLAS = {
    "22G101-1": {
        "file": "22G101-1现浇混凝土框架、剪力墙、梁、板.pdf",
        "title": "现浇混凝土框架、剪力墙、梁、板（平法制图规则和构造详图）",
        "kind": "text",   # 有文字层，可关键词检索
        "toc_pages": "7-9",
    },
    "22G101-2": {
        "file": "22G101-2现浇混凝土板式楼梯.pdf",
        "title": "现浇混凝土板式楼梯（平法制图规则和构造详图）",
        "kind": "text",
        "toc_pages": "7-9",
    },
    "22G101-3": {
        "file": "22G101-3独立基础、条形基础、筏形基础、桩基础.pdf",
        "title": "独立基础、条形基础、筏形基础、桩基础（平法制图规则和构造详图）",
        "kind": "text",
        "toc_pages": "7-9",
    },
    "23G101-11": {
        "file": "23G101-11 G101系列图集常见问题答疑图解.pdf",
        "title": "G101系列图集常见问题答疑图解",
        "kind": "text",  # 双层 PDF（扫描图像+隐藏文字层），可 txt 快查
        "toc_pages": "4-6",
    },
}


def resolve_assets_dir(assets_dir):
    """定位 assets 目录：优先 --assets-dir，其次脚本相对路径。"""
    if assets_dir:
        return assets_dir
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(here, "..", "assets")
    cand = os.path.abspath(cand)
    if os.path.isdir(cand):
        return cand
    return None


def build_file_map(assets_dir):
    """返回 {图集号: {path, meta}}；图集文件缺失时跳过并提示。"""
    result = {}
    for key, meta in ATLAS.items():
        path = os.path.join(assets_dir, meta["file"])
        if os.path.isfile(path):
            result[key] = {"path": path, "meta": meta}
        else:
            print(f"[提示] 未找到图集文件：{meta['file']}（{path}）", file=sys.stderr)
    return result


# ---------------------------------------------------------------------------
# 页码与文本
# ---------------------------------------------------------------------------
def extract_internal_page_label(text):
    """尝试从页脚提取图集内部页码，形如 '2-35'、'1-6'、'7-1' 等。

    优先匹配 '页 X-Y' 锚点（图集页脚固定栏）；兜底只在页面末尾区域
    （后 300 字符）寻找独立的 'X-Y'，避免误抓目录中的条目页码。
    """
    m = re.search(r"页\s*([0-9]+\s*-\s*[0-9]+)", text)
    if m:
        return re.sub(r"\s+", "", m.group(1))
    tail = text[-300:]
    m = re.search(r"(?:^|[^0-9])([0-9]+\s*-\s*[0-9]+)(?:[^0-9]|$)", tail)
    if m:
        return re.sub(r"\s+", "", m.group(1))
    return None


def clean_page_text(raw):
    """清洗文字层文本：
    - 去空行、行首行尾空白
    - 合并被拆成单字的竖向页眉栏噪声（如 '总\\n则\\n剪\\n力\\n墙'），
      仅用于展示；引用原文时仍以原始逐字内容为准。
    返回 (clean_text, 原始文本长度)。
    """
    lines = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s:
            continue
        # 过滤极短的竖向栏噪声（1~2 个孤立字，且非数字/符号）
        if len(s) <= 2 and not re.search(r"[0-9a-zA-Z%±φΦ×（）()]", s):
            continue
        lines.append(s)
    return "\n".join(lines)


def search_pdf(path, keywords, limit, context_chars):
    """在文字版图集中检索关键词，返回命中的页码列表。"""
    hits = []
    doc = pymupdf.open(path)
    kw = [k.strip() for k in keywords if k.strip()]
    for i in range(doc.page_count):
        raw = doc[i].get_text()
        if not raw:
            continue
        found = [k for k in kw if k in raw]
        if not found:
            continue
        clean = clean_page_text(raw)
        # 在清洗文本中定位首个命中位置作为上下文起点
        pos = -1
        for k in kw:
            p = clean.find(k)
            if p >= 0 and (pos < 0 or p < pos):
                pos = p
        start = max(0, pos - context_chars // 2)
        ctx = clean[start:start + context_chars]
        hits.append({
            "pdf_page": i + 1,
            "internal_page": extract_internal_page_label(raw) or "—",
            "keywords_hit": found,
            "hit_count": len(found),
            "context": ctx,
            "text_len": len(clean),
        })
    doc.close()
    # 按命中关键词数量降序，页码升序
    hits.sort(key=lambda h: (-h["hit_count"], h["pdf_page"]))
    return hits[:limit]


# ---------------------------------------------------------------------------
# txt 快查（references/*.txt，秒级检索）
# txt 由源 PDF 文字层预先导出，每页以 "--- PDF页N ---" 分隔。
# 优先用 txt 检索可避免每次打开 9MB PDF 逐页扫描，显著提速。
# ---------------------------------------------------------------------------
def resolve_references_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.abspath(os.path.join(here, "..", "references"))
    return cand if os.path.isdir(cand) else None


def load_txt_pages(atlas_key):
    """读取 references/{atlas_key}.txt，返回 [(pdf_page, raw_text), ...]；不存在返回 None。"""
    ref_dir = resolve_references_dir()
    if not ref_dir:
        return None
    fp = os.path.join(ref_dir, f"{atlas_key}.txt")
    if not os.path.isfile(fp):
        return None
    with open(fp, "r", encoding="utf-8") as f:
        text = f.read()
    parts = re.split(r"^--- PDF页(\d+) ---\s*$", text, flags=re.M)
    pages = []
    for i in range(1, len(parts) - 1, 2):
        pages.append((int(parts[i]), parts[i + 1]))
    return pages


def search_txt(pages, keywords, limit, context_chars):
    """在 txt 页中检索关键词（命中数降序、页码升序），返回与 search_pdf 同结构结果。"""
    kw = [k.strip() for k in keywords if k.strip()]
    hits = []
    for pdf_page, raw in pages:
        found = [k for k in kw if k in raw]
        if not found:
            continue
        clean = clean_page_text(raw)
        pos = -1
        for k in kw:
            p = clean.find(k)
            if p >= 0 and (pos < 0 or p < pos):
                pos = p
        start = max(0, pos - context_chars // 2)
        ctx = clean[start:start + context_chars]
        hits.append({
            "pdf_page": pdf_page,
            "internal_page": extract_internal_page_label(raw) or "—",
            "keywords_hit": found,
            "hit_count": len(found),
            "context": ctx,
            "text_len": len(clean),
            "source": "txt快查",
        })
    hits.sort(key=lambda h: (-h["hit_count"], h["pdf_page"]))
    return hits[:limit]


def render_pages(path, pages, out_dir, zoom):
    """渲染指定 PDF 页（1 起）为 PNG，返回保存的文件路径列表。"""
    os.makedirs(out_dir, exist_ok=True)
    doc = pymupdf.open(path)
    saved = []
    base = os.path.splitext(os.path.basename(path))[0][:9]
    for pg in pages:
        if pg < 1 or pg > doc.page_count:
            print(f"[警告] {base} 页码越界：{pg}（共 {doc.page_count} 页）", file=sys.stderr)
            continue
        pix = doc[pg - 1].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        out = os.path.join(out_dir, f"{base}_p{pg:03d}.png")
        pix.save(out)
        saved.append(out)
    doc.close()
    return saved


# ---------------------------------------------------------------------------
# 扫描版图集的「内部页码 → PDF 页码」映射
# 23G101-11 无文字层，内部页号（如 2-3）与 PDF 页码按章节起点换算：
#   内部页 "C-P" 对应 PDF 页码 = start[C] + (P - 1)
# ---------------------------------------------------------------------------
PAGEMAP = {
    "23G101-11": {  # 章节首页内部页码 -> 该页所在 PDF 页码（1 起）
        "1-1": 13,
        "2-1": 36,
        "3-1": 55,
        "4-1": 71,
        "5-1": 97,
        "6-1": 106,
        "7-1": 137,
        "8-1": 139,
    },
}


def internal_to_pdf_page(atlas_key, internal_page):
    """把扫描版图集的内部页码（如 2-3）换算为 PDF 页码；无法换算返回 None。"""
    starts = PAGEMAP.get(atlas_key)
    if not starts:
        return None
    m = re.fullmatch(r"([0-9]+)-([0-9]+)", internal_page.strip())
    if not m:
        return None
    chap, page = int(m.group(1)), int(m.group(2))
    base = starts.get(f"{chap}-1")
    if base is None:
        return None
    return base + (page - 1)


def parse_page_spec(spec, toc):
    """把页码规格解析为 (atlas_key, pages列表)。

    - --render '图集号:页码'：页码可为单个/逗号列表/范围
    - --toc 图集号：按该图集已知目录页范围渲染
    - --render '图集号:页码' --toc：渲染该图集目录页
    """
    if spec is None and toc is None:
        return None
    if isinstance(toc, str):
        key = toc.strip()
        if key not in ATLAS:
            raise SystemExit(f"未知图集号：{key}，可选 {list(ATLAS)}")
        return key, parse_pages(ATLAS[key]["toc_pages"])
    if spec is None:
        raise SystemExit("--toc 需要指定图集号：--toc 22G101-1")
    if ":" in spec:
        key, pagespec = spec.split(":", 1)
    else:
        key, pagespec = spec, None
    key = key.strip()
    if key not in ATLAS:
        raise SystemExit(f"未知图集号：{key}，可选 {list(ATLAS)}")
    if toc is True:
        pagespec = ATLAS[key]["toc_pages"]
    pages = parse_pages(pagespec)
    return key, pages


def parse_pages(pagespec):
    """把 '35'、'4-10'、'3,5,7' 解析为页码列表。"""
    pages = []
    if pagespec:
        for part in pagespec.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                pages.extend(range(int(a), int(b) + 1))
            elif part:
                pages.append(int(part))
    return pages


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="混凝土结构施工图（22G101/23G101）图集检索与渲染")
    ap.add_argument("--keywords", nargs="+", help="检索关键词（支持多个，按命中数排序）")
    ap.add_argument("--atlas", nargs="+", default=list(ATLAS),
                    help="限定图集号，如 22G101-1 22G101-2（默认全部）")
    ap.add_argument("--assets-dir", default=None, help="assets 目录（默认脚本上级目录）")
    ap.add_argument("--out-dir", default="_atlas_out", help="渲染 PNG 输出目录")
    ap.add_argument("--render", default=None,
                    help="渲染模式：'图集号:页码'，页码支持 35 / 4-10 / 3,5,7")
    ap.add_argument("--toc", nargs="?", const=True, default=None,
                    help="渲染指定图集的目录页。可单独用 --toc 图集号，或 --render 图集号:页码 --toc")
    ap.add_argument("--map", default=None,
                    help="扫描版图集内部页码换算：'图集号:内部页码'，如 23G101-11:2-3；"
                         "或只给 '23G101-11' 列出全部章节起点")
    ap.add_argument("--zoom", type=float, default=2.0, help="渲染倍率（默认 2.0）")
    ap.add_argument("--limit", type=int, default=8, help="每本图集最多返回的命中页数（默认 8）")
    ap.add_argument("--context", type=int, default=400, help="每个命中的上下文截取字符数（默认 400）")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = ap.parse_args()

    assets_dir = resolve_assets_dir(args.assets_dir)
    if not assets_dir:
        raise SystemExit("未找到 assets 目录，请用 --assets-dir 指定")
    files = build_file_map(assets_dir)
    if not files:
        raise SystemExit("assets 下未找到任何图集 PDF")

    # ---- 页码换算模式（扫描版图集内部页码 → PDF 页码）----
    if args.map:
        if ":" in args.map:
            key, internal = args.map.split(":", 1)
            page = internal_to_pdf_page(key.strip(), internal)
            if page is None:
                raise SystemExit(
                    f"无法换算 {args.map}：请用格式 '图集号:内部页码'（如 23G101-11:2-3），"
                    f"或先用 --map {key} 查看章节起点")
            if args.json:
                print(json.dumps({"atlas": key.strip(), "internal_page": internal,
                                  "pdf_page": page}, ensure_ascii=False))
            else:
                print(f"{key.strip()} 内部页码 {internal} → PDF 第 {page} 页")
            return
        key = args.map.strip()
        starts = PAGEMAP.get(key)
        if not starts:
            raise SystemExit(f"暂无 {key} 的页码映射；仅支持：{list(PAGEMAP)}")
        if args.json:
            print(json.dumps({"atlas": key, "chapter_starts": starts}, ensure_ascii=False))
        else:
            print(f"{key} 章节首页映射（内部页码 → PDF 页码）：")
            for internal in sorted(starts, key=lambda s: int(s.split('-')[0])):
                print(f"  {internal} → PDF 第 {starts[internal]} 页")
        return

    # ---- 渲染模式 ----
    if args.render or args.toc:
        key, pages = parse_page_spec(args.render, args.toc)
        if key is None:
            raise SystemExit("渲染模式需要 --render '图集号:页码' 或 --toc 图集号")
        if key not in files:
            raise SystemExit(f"未找到图集 {key} 的文件")
        saved = render_pages(files[key]["path"], pages, args.out_dir, args.zoom)
        if args.json:
            print(json.dumps({"rendered": saved}, ensure_ascii=False))
        else:
            print(f"已渲染 {key} 共 {len(saved)} 页：")
            for s in saved:
                print("  " + s)
        return

    # ---- 检索模式 ----
    if not args.keywords:
        raise SystemExit("请提供 --keywords 检索关键词")
    results = {}
    for key in args.atlas:
        key = key.strip()
        if key not in files:
            continue
        meta = files[key]["meta"]
        if meta["kind"] == "scanned":
            results[key] = {
                "kind": "scanned",
                "note": "扫描版图集，无文字层，无法关键词检索。请先 --render 目录页视觉定位，再渲染目标页读取。",
                "toc_pages": meta["toc_pages"],
            }
            continue
        # 优先 txt 快查（references/*.txt），缺失时回退 PDF 扫描
        txt_pages = load_txt_pages(key)
        if txt_pages is not None:
            hits = search_txt(txt_pages, args.keywords, args.limit, args.context)
        else:
            hits = search_pdf(files[key]["path"], args.keywords, args.limit, args.context)
        results[key] = {"kind": "text", "hits": hits}

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    for key, res in results.items():
        print("=" * 60)
        print(f"【{key}】{ATLAS[key]['title']}")
        if res["kind"] == "scanned":
            print("  " + res["note"])
            print("  目录页（PDF 页码）：" + res["toc_pages"])
            continue
        if not res["hits"]:
            print("  未检索到关键词命中。可尝试同义词、图集内部术语，或查看目录页定位。")
            continue
        for h in res["hits"]:
            src = "（" + h.get("source", "PDF扫描") + "）" if h.get("source") else ""
            print(f"  - 命中页：PDF 第 {h['pdf_page']} 页{src} | 图集内部页码：{h['internal_page']} | 命中关键词：{'、'.join(h['keywords_hit'])}")
            ctx = h["context"].replace("\n", " ")
            print(f"    原文片段：{ctx}...")


if __name__ == "__main__":
    main()
