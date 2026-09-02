# -*- coding: utf-8 -*-
"""从《建筑施工手册（第六版）》PDF 提取全文，按章节切分为知识库文件。"""
import json, os, re, sys, time
import pymupdf

PDF_PATH = r"E:\下载\建筑施工手册（第六版）全册.pdf"
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_DIR = os.path.join(SKILL_DIR, "references")
TOC_JSON = os.path.join(REF_DIR, "_toc_raw.json")

os.makedirs(REF_DIR, exist_ok=True)

def clean(text):
    # 去掉页眉页脚常见重复页码行等噪声（保留正文）
    return text

def main():
    doc = pymupdf.open(PDF_PATH)
    with open(TOC_JSON, "r", encoding="utf-8") as f:
        toc = json.load(f)

    # L1 章节边界（1-based PDF 页码）
    l1 = [t for t in toc if t[0] == 1]
    chapters = [t for t in l1 if re.match(r"^\d+\s", t[1])]  # 只取编号章节
    # 章节起止
    ranges = []
    for i, ch in enumerate(chapters):
        start = ch[2]
        end = (chapters[i+1][2] - 1) if i + 1 < len(chapters) else doc.page_count
        ranges.append((ch[1], start, end))

    # 前言部分 1 ~ 第一章之前
    front_start = 1
    front_end = chapters[0][2] - 1
    ranges.insert(0, ("0 封面与前言", front_start, front_end))

    total_start = time.time()
    for name, s, e in ranges:
        t0 = time.time()
        parts = []
        for p in range(s - 1, e):  # 0-based
            try:
                t = doc[p].get_text()
            except Exception as ex:
                t = f"[提取失败 page={p+1}: {ex}]"
            if t:
                parts.append(f"--- PDF页{p+1} ---\n" + t)
        content = "\n".join(parts)
        safe = re.sub(r'[\\/:*?"<>|]', "_", name)
        fp = os.path.join(REF_DIR, safe + ".txt")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(f"# {name}\n# 来源：《建筑施工手册（第六版）》PDF页{s}-{e}\n\n" + content)
        print(f"[OK] {name} 页{s}-{e} ({e-s+1}页) 文本{len(content)}字 耗时{time.time()-t0:.1f}s", flush=True)
    print(f"全部完成，总耗时 {time.time()-total_start:.1f}s", flush=True)

if __name__ == "__main__":
    main()
