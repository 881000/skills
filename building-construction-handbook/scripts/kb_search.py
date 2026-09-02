# -*- coding: utf-8 -*-
"""《建筑施工手册》知识库关键词检索脚本。

用法:
    python kb_search.py 关键词 [关键词2 ...] [--chapter 章号或章节名] [--ctx 上下文行数] [--limit N]

示例:
    python kb_search.py 钢筋锚固
    python kb_search.py 抗渗等级 --chapter 31
    python kb_search.py 盘扣式 脚手架 --ctx 3

说明:
    - 在 references/ 下分章文本文件中检索（跳过 INDEX.md / _toc_raw.json）。
    - 多关键词默认按「同一页同时包含全部关键词」匹配（AND 语义），可用 --any 切换为或。
    - 命中输出标注章节文件、PDF 页号与上下文，便于回源核对。
"""
import argparse, glob, os, re, sys

REF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references")
PAGE_RE = re.compile(r"^--- PDF页(\d+) ---$")

def load_files(chapter_filter=None):
    files = sorted(glob.glob(os.path.join(REF_DIR, "*.txt")))
    out = []
    for fp in files:
        name = os.path.basename(fp)
        if name.startswith("_"):
            continue
        if chapter_filter:
            num = re.match(r"(\d+)", name)
            if (num and num.group(1) == chapter_filter) or (chapter_filter in name):
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
            # 所有关键词必须都出现在本页
            page_text = "\n".join(lines)
            if not all(t in page_text for t in terms):
                continue
        # 取首个命中行附近上下文
        i = hit_lines[0]
        start = max(0, i - ctx_lines)
        end = min(len(lines), i + ctx_lines + 1)
        results.append((page_no, lines[start:end]))
    return results

def main():
    ap = argparse.ArgumentParser(description="建筑施工手册知识库检索")
    ap.add_argument("terms", nargs="+", help="检索关键词")
    ap.add_argument("--chapter", help="限定章节（章号或章节名片段）")
    ap.add_argument("--ctx", type=int, default=3, help="上下文行数（默认3）")
    ap.add_argument("--limit", type=int, default=5, help="每章最多输出条数（默认5）")
    ap.add_argument("--any", action="store_true", help="多关键词用或（任一命中即算）")
    args = ap.parse_args()

    files = load_files(args.chapter)
    if not files:
        print("未找到匹配章节文件。可用章节: " + ", ".join(
            re.sub(r"\.txt$", "", os.path.basename(x)) for x in glob.glob(os.path.join(REF_DIR, "*.txt"))))
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
    print(f"\n共命中 {total} 处。可加 --chapter 限定章节，或 --any 切换为模糊命中。")

if __name__ == "__main__":
    main()
