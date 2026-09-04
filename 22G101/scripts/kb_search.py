# -*- coding: utf-8 -*-
"""《22G101 混凝土结构施工图》知识库关键词检索脚本。

用法:
    python kb_search.py 关键词 [关键词2 ...] [--volume 分册号] [--ctx 上下文行数] [--limit N]

示例:
    python kb_search.py 锚固长度
    python kb_search.py 剪力墙 水平分布钢筋 --volume 1
    python kb_search.py 楼梯 平面注写 --volume 2
    python kb_search.py 独立基础 底板配筋 --volume 3

说明:
    - 在 references/ 下三个分册文本中检索。
    - 多关键词默认按「同一 PDF 页同时包含全部关键词」匹配（AND 语义），可用 --any 切换为或。
    - 命中输出标注分册、PDF 页号与上下文，便于回源 PDF 核对原文。
"""
import argparse, glob, os, re, sys

REF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references")
PAGE_RE = re.compile(r"^--- PDF页(\d+) ---$")

# 分册号 -> 文件名匹配片段
VOLUME_MAP = {
    "1": "22G101-1",
    "2": "22G101-2",
    "3": "22G101-3",
}


def load_files(volume_filter=None):
    files = sorted(glob.glob(os.path.join(REF_DIR, "*.txt")))
    out = []
    for fp in files:
        name = os.path.basename(fp)
        if name.startswith("_"):
            continue
        if volume_filter:
            seg = VOLUME_MAP.get(volume_filter, volume_filter)
            if seg in name:
                out.append(fp)
        else:
            out.append(fp)
    return out


def split_pages(fp):
    """把文件按 '--- PDF页N ---' 切分为 [(page_no_or_None, [lines]), ...]"""
    with open(fp, "r", encoding="utf-8") as f:
        lines = f.read().split("\n")
    pages = []
    cur_page = None
    cur = []
    for ln in lines:
        m = PAGE_RE.match(ln.strip())
        if m:
            if cur:
                pages.append((cur_page, cur))
            cur_page = int(m.group(1))
            cur = []
        elif cur_page is not None:
            cur.append(ln)
    if cur:
        pages.append((cur_page, cur))
    return pages


def search_file(fp, terms, ctx_lines, any_mode):
    pages = split_pages(fp)
    results = []
    for page_no, lines in pages:
        hit_lines = [i for i, ln in enumerate(lines) if any(t in ln for t in terms)]
        if not hit_lines:
            continue
        if not any_mode:
            page_text = "\n".join(lines)
            if not all(t in page_text for t in terms):
                continue
        i = hit_lines[0]
        start = max(0, i - ctx_lines)
        end = min(len(lines), i + ctx_lines + 1)
        results.append((page_no, lines[start:end]))
    return results


def main():
    ap = argparse.ArgumentParser(description="22G101 混凝土结构施工图知识库检索")
    ap.add_argument("terms", nargs="+", help="检索关键词")
    ap.add_argument("--volume", help="限定分册（1/2/3）")
    ap.add_argument("--ctx", type=int, default=3, help="上下文行数（默认3）")
    ap.add_argument("--limit", type=int, default=5, help="每册最多输出条数（默认5）")
    ap.add_argument("--any", action="store_true", help="多关键词用或（任一命中即算）")
    args = ap.parse_args()

    files = load_files(args.volume)
    if not files:
        print("未找到匹配分册文件。可用分册: 1 / 2 / 3")
        sys.exit(1)

    total = 0
    for fp in files:
        res = search_file(fp, args.terms, args.ctx, args.any)
        if not res:
            continue
        print(f"\n===== {os.path.basename(fp)} （命中 {len(res)} 处）=====")
        for page_no, snippet in res[:args.limit]:
            print(f"  [PDF页{page_no}]")
            for s in snippet:
                s = s.strip()
                if s:
                    print("    " + s)
        total += len(res)
    print(f"\n共命中 {total} 处。可加 --volume 限定分册，或 --any 切换为模糊命中。")


if __name__ == "__main__":
    main()
