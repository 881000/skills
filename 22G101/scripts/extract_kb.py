# -*- coding: utf-8 -*-
"""从《22G101 混凝土结构施工图平面整体表示方法制图规则和构造详图》三册 PDF 提取全文，
按分册切分为知识库文本文件（每页以 `--- PDF页N ---` 分隔），供精确检索与原文引用。

一次性维护用脚本，一般无需执行。运行后重新生成 references/ 下的三册文本与 INDEX.md 素材。
"""
import os, re, time
import pymupdf

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_DIR = os.path.join(SKILL_DIR, "references")

# 分册 -> (源 PDF 路径, 输出文件名, 图集号)
VOLUMES = [
    ("22G101-1", r"E:\下载\22G101规范图集\22G101-1现浇混凝土框架、剪力墙、梁、板.pdf",
     "22G101-1 框架、剪力墙、梁、板.txt"),
    ("22G101-2", r"E:\下载\22G101规范图集\22G101-2现浇混凝土板式楼梯.pdf",
     "22G101-2 板式楼梯.txt"),
    ("22G101-3", r"E:\下载\22G101规范图集\22G101-3独立基础、条形基础、筏形基础、桩基础.pdf",
     "22G101-3 独立基础、条形基础、筏形基础、桩基础.txt"),
]

os.makedirs(REF_DIR, exist_ok=True)


def main():
    total_t0 = time.time()
    for code, pdf_path, out_name in VOLUMES:
        t0 = time.time()
        doc = pymupdf.open(pdf_path)
        parts = []
        total_chars = 0
        for p in range(doc.page_count):
            try:
                t = doc[p].get_text("text")
            except Exception as ex:
                t = f"[提取失败 page={p+1}: {ex}]"
            if t and t.strip():
                parts.append(f"--- PDF页{p+1} ---\n" + t)
                total_chars += len(t)
        content = "\n".join(parts)
        fp = os.path.join(REF_DIR, out_name)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(f"# {out_name}\n# 来源：《22G101 混凝土结构施工图平面整体表示方法制图规则和构造详图》{code}\n# 源文件：{pdf_path}\n\n" + content)
        print(f"[OK] {code} {doc.page_count}页 文本{total_chars}字 -> {out_name} 耗时{time.time()-t0:.1f}s", flush=True)
        doc.close()
    print(f"全部完成，总耗时 {time.time()-total_t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
