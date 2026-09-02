# -*- coding: utf-8 -*-
"""从 TOC JSON 生成知识库章节索引 INDEX.md。"""
import json, os, re

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_DIR = os.path.join(SKILL_DIR, "references")
TOC_JSON = os.path.join(REF_DIR, "_toc_raw.json")

with open(TOC_JSON, "r", encoding="utf-8") as f:
    toc = json.load(f)

# 仅保留从第一个编号章节开始的正文目录（跳过封面/前言/目录页）
start_idx = None
for i, t in enumerate(toc):
    if t[0] == 1 and re.match(r"^\d+\s", t[1]):
        start_idx = i
        break
body = toc[start_idx:]

lines = []
lines.append("# 《建筑施工手册（第六版）》知识库索引\n")
lines.append("> 全书共 41 章。本知识库按章节切分为 `NN_章节名.txt` 文本文件（见同目录）。")
lines.append("> 检索时优先用下方章节结构定位到相关章节文件，再在对应文件中用关键词定位。\n")

for t in body:
    lvl, title, page = t[0], t[1], t[2]
    indent = "  " * (lvl - 1)
    # 用 PDF 页号标记
    lines.append(f"{indent}- **{title}** （PDF页{page}）")

content = "\n".join(lines) + "\n"
out = os.path.join(REF_DIR, "INDEX.md")
with open(out, "w", encoding="utf-8") as f:
    f.write(content)
print("INDEX.md 写入:", out, "行数:", len(lines))
