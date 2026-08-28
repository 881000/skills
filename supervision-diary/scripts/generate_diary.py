#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监理日志生成器
基于模板生成监理日志docx文件，具备内容优化表达、智能摘要精简、
段落编号、行距控制、首行缩进等专业排版功能。
"""

import argparse
import os
import sys
import datetime
import re
from copy import deepcopy
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


WEEKDAY_NAMES = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']

# 四大板块排版限制配置
SECTION_LIMITS = {
    'construction': {'max_chars': 600, 'max_lines': 18, 'label': '当日施工进展情况'},
    'supervision':  {'max_chars': 260, 'max_lines': 6,  'label': '当日监理工作情况'},
    'problem':      {'max_chars': 160, 'max_lines': 4,  'label': '当日存在的问题及处理情况'},
    'other':        {'max_chars': 120, 'max_lines': 3,  'label': '其他有关事项'},
}

# 排版参数（用于物理行数估算）
CELL_WIDTH_TWIPS = 9888       # 内容单元格总宽度（15列合计）
CELL_MARGIN_TWIPS = 240       # 单元格左右内边距合计（保守估算，确保不超页）
FONT_SIZE_PT = 10.5            # 五号字
CHAR_WIDTH_PT = FONT_SIZE_PT   # 中文字符宽度约等于字号
FIRST_LINE_INDENT_CHARS = 2    # 首行缩进2字符
NUMBER_PREFIX_CHARS = 2         # 编号"1、"占2字符

# 各板块关键词（用于摘要时判断句子重要性）
SECTION_KEYWORDS = {
    'construction': [
        '浇筑', '绑扎', '安装', '拆除', '开挖', '回填', '完成', '进行', '正在',
        '楼', '层', '段', '区', '轴', '方量', 'm³', '立方', '工程量', '进度',
        '钢筋', '模板', '混凝土', '砌体', '抹灰', '防水', '保温', '装饰', '装修',
        '水电', '预埋', '管线', '脚手架', '支撑', '养护', '放线', '测量',
    ],
    'supervision': [
        '巡视', '检查', '旁站', '验收', '审核', '审查', '签署', '签发',
        '会议', '例会', '协调', '要求', '整改', '合格', '符合', '不符合',
        '质量', '安全', '进度', '投资', '合同', '资料', '报审', '报验',
        '坍落度', '试块', '取样', '检测', '复核', '见证',
    ],
    'problem': [
        '问题', '隐患', '不符合', '不合格', '整改', '责令', '要求', '复查',
        '合格', '验收', '通知', '停工', '返工', '纠正', '预防', '处理',
        '安全', '质量', '规范', '方案', '设计', '标准',
    ],
    'other': [
        '建设单位', '设计单位', '勘察单位', '施工单位', '监理单位',
        '检查', '指导', '调研', '会议', '通知', '文件', '来访', '接待',
    ],
}


def parse_date(date_str):
    """解析日期字符串，支持多种格式，返回 datetime.date 对象。"""
    if not date_str:
        return None
    date_str = date_str.strip()
    formats = ['%Y年%m月%d日', '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y%m%d']
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    match = re.search(r'(\d{4})\D*(\d{1,2})\D*(\d{1,2})', date_str)
    if match:
        try:
            year, month, day = map(int, match.groups())
            return datetime.date(year, month, day)
        except (ValueError, TypeError):
            pass
    return None


def get_weekday(date_str):
    """根据日期字符串返回中文星期几。"""
    dt = parse_date(date_str)
    if dt is None:
        return ''
    return WEEKDAY_NAMES[dt.weekday()]


def get_template_path():
    """获取模板文件路径。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, '..', 'assets', '监理日志.docx')
    return os.path.normpath(template_path)


def get_chars_per_line():
    """计算内容单元格每行可放多少个中文字符。"""
    available_width_pt = (CELL_WIDTH_TWIPS - CELL_MARGIN_TWIPS) / 20.0
    return int(available_width_pt / CHAR_WIDTH_PT)


def estimate_physical_lines(paragraphs_text):
    """
    估算编号段落列表在单元格中占据的物理行数（考虑自动换行）。
    
    Args:
        paragraphs_text: 段落文本列表（不含编号前缀，如["3号楼浇筑...", "钢筋绑扎..."]）
    
    Returns:
        总物理行数
    """
    chars_per_line = get_chars_per_line()
    first_line_chars = chars_per_line - FIRST_LINE_INDENT_CHARS - NUMBER_PREFIX_CHARS
    follow_line_chars = chars_per_line
    
    total_lines = 0
    for text in paragraphs_text:
        text_len = len(text)
        if text_len <= first_line_chars:
            total_lines += 1
        else:
            remaining = text_len - first_line_chars
            total_lines += 1 + (remaining + follow_line_chars - 1) // follow_line_chars
    
    return total_lines


def split_sentences(text):
    """将文本按句号、分号、问号、感叹号分割为句子列表。"""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # 先按换行分割，再按句末标点分割
    sentences = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        # 按中文句末标点分割（保留标点）
        parts = re.split(r'(?<=[。；！？])', line)
        for p in parts:
            p = p.strip()
            if p:
                sentences.append(p)
    return sentences


def score_sentence(sentence, category):
    """计算句子的重要性分数，包含关键词越多分数越高。"""
    score = 0
    keywords = SECTION_KEYWORDS.get(category, [])
    for kw in keywords:
        if kw in sentence:
            score += 1
    # 包含数字（工程量、时间、编号等）的句子更重要
    if re.search(r'\d+', sentence):
        score += 1
    # 较长的句子通常包含更多信息
    if len(sentence) > 20:
        score += 1
    return score


def compress_sentence(sentence):
    """对单个句子进行轻度压缩，去除冗余修饰词，保留关键信息。"""
    # 去除常见冗余表述
    redundants = [
        '的话', '的话呢', '的话吧', '的话啊',
        '其实', '实际上', '事实上', '基本上', '大致上',
        '可以说是', '可以说', '应该是', '可能是',
        '非常', '十分', '相当', '比较', '较为',
        '及时地', '有效地', '顺利地', '成功地',
        '进行了', '开展了', '实施了', '落实了',
    ]
    for r in redundants:
        sentence = sentence.replace(r, '')
    # 合并连续空格
    sentence = re.sub(r'\s+', ' ', sentence)
    return sentence.strip()


def summarize_content(text, category):
    """
    智能摘要精简：在不丢失关键信息的前提下，将内容压缩到板块字数限制内。
    
    策略：
    1. 按句子分割
    2. 计算每句重要性分数
    3. 优先保留高分句子
    4. 对保留的长句子进行轻度压缩
    5. 最后确保总字数不超限
    """
    if not text or not text.strip():
        return ''
    
    limits = SECTION_LIMITS[category]
    max_chars = limits['max_chars']
    
    # 如果原始内容已在限制内，直接返回
    if len(text) <= max_chars:
        return text
    
    sentences = split_sentences(text)
    if not sentences:
        return text[:max_chars]
    
    # 计算每句分数
    scored = [(score_sentence(s, category), i, s) for i, s in enumerate(sentences)]
    
    # 按分数降序选择句子，直到接近字数限制
    scored_sorted = sorted(scored, key=lambda x: (-x[0], x[1]))
    
    selected = []
    total_chars = 0
    for score, idx, sentence in scored_sorted:
        if total_chars + len(sentence) <= max_chars:
            selected.append((idx, sentence))
            total_chars += len(sentence)
        elif total_chars < max_chars * 0.7 and score > 0:
            # 还有较多空间时，即使单句超限也尝试压缩后加入
            compressed = compress_sentence(sentence)
            if total_chars + len(compressed) <= max_chars:
                selected.append((idx, compressed))
                total_chars += len(compressed)
    
    # 按原始顺序排列
    selected.sort(key=lambda x: x[0])
    result = ''.join(s for _, s in selected)
    
    # 如果仍超限，对结果逐句压缩
    if len(result) > max_chars:
        result_sentences = split_sentences(result)
        compressed_all = [compress_sentence(s) for s in result_sentences]
        result = ''.join(compressed_all)
    
    # 最终截断保护（保留句末标点）
    if len(result) > max_chars:
        result = result[:max_chars-1] + '。'
    
    return result


def optimize_and_number(text, category):
    """
    对输入文本进行优化表达、智能摘要、按段落编号，并控制物理行数不超过最大行数。
    
    流程：原始文本 → 优化表达 → 智能摘要 → 去除旧编号 → 物理行数控制（迭代压缩） → 重新编号
    """
    if not text or not text.strip():
        return ''
    
    limits = SECTION_LIMITS[category]
    max_lines = limits['max_lines']
    
    # 先做表达优化
    text = optimize_expression(text, category)
    
    # 智能摘要精简（应用字数限制）
    text = summarize_content(text, category)
    
    # 按句子分割
    raw_items = split_sentences(text)
    if not raw_items:
        raw_items = [text.strip()]
    
    # 去除已有的编号前缀
    cleaned_items = []
    for item in raw_items:
        item = re.sub(r'^\s*[\(（]?\d+[\)）、\.]\s*', '', item)
        item = re.sub(r'^\s*[一二三四五六七八九十]+、\s*', '', item)
        item = item.strip()
        if item:
            if not item.endswith(('。', '；', '！', '？')):
                item += '。'
            cleaned_items.append(item)
    
    if not cleaned_items:
        return text.strip()
    
    # 物理行数控制：迭代压缩直到不超过max_lines
    # 策略1：合并相邻短句子（阈值逐步放宽，避免过度合并）
    for merge_threshold in [25, 40, 55, 75, 100]:
        if estimate_physical_lines(cleaned_items) <= max_lines:
            break
        merged = []
        i = 0
        while i < len(cleaned_items):
            current = cleaned_items[i]
            # 仅当当前句子较短且与下一句合并后不超过100字时才合并
            if (len(current) < merge_threshold and i + 1 < len(cleaned_items)
                    and len(current) + len(cleaned_items[i+1]) <= 100):
                current = current + cleaned_items[i+1]
                i += 2
            else:
                i += 1
            merged.append(current)
        cleaned_items = merged
    
    # 策略2：对长句子进行轻度压缩（去除冗余修饰词）
    if estimate_physical_lines(cleaned_items) > max_lines:
        cleaned_items = [compress_sentence(s) for s in cleaned_items]
    
    # 策略3：再次合并短句子（压缩后可能变短）
    if estimate_physical_lines(cleaned_items) > max_lines:
        merged = []
        i = 0
        while i < len(cleaned_items):
            current = cleaned_items[i]
            if (len(current) < 50 and i + 1 < len(cleaned_items)
                    and len(current) + len(cleaned_items[i+1]) <= 120):
                current = current + cleaned_items[i+1]
                i += 2
            else:
                i += 1
            merged.append(current)
        cleaned_items = merged
    
    # 策略4：如果仍超限，删除重要性分数最低的句子（最多删除1/4，且至少保留2句）
    if estimate_physical_lines(cleaned_items) > max_lines and len(cleaned_items) > 2:
        max_delete = max(1, len(cleaned_items) // 4)
        deleted = 0
        while (estimate_physical_lines(cleaned_items) > max_lines 
               and deleted < max_delete 
               and len(cleaned_items) > 2):
            # 找分数最低的句子删除
            scored = [(score_sentence(s, category), i) for i, s in enumerate(cleaned_items)]
            scored_sorted = sorted(scored, key=lambda x: (x[0], x[1]))
            del_idx = scored_sorted[0][1]
            cleaned_items.pop(del_idx)
            deleted += 1
    
    # 最终截断保护：如果仍超限，截断最后一个句子
    if estimate_physical_lines(cleaned_items) > max_lines and cleaned_items:
        chars_per_line = get_chars_per_line()
        # 计算允许的最大总字符数（粗略估算）
        max_total_chars = max_lines * chars_per_line - FIRST_LINE_INDENT_CHARS * len(cleaned_items) - NUMBER_PREFIX_CHARS * len(cleaned_items)
        current_total = sum(len(s) for s in cleaned_items)
        if current_total > max_total_chars:
            # 从最后一个句子开始截断
            excess = current_total - max_total_chars
            last = cleaned_items[-1]
            if len(last) > excess + 1:
                cleaned_items[-1] = last[:len(last)-excess-1] + '。'
            else:
                cleaned_items.pop()
    
    # 重新编号
    optimized = [f'{i}、{item}' for i, item in enumerate(cleaned_items, 1)]
    return '\n'.join(optimized)


def optimize_expression(text, category):
    """根据内容类别优化表达，使语言更专业规范。"""
    if category == 'construction':
        text = text.replace('做了', '完成')
        text = text.replace('搞了', '实施')
        text = text.replace('弄了', '完成')
        text = text.replace('开始', '已开始')
        text = text.replace('在做', '正在进行')
        text = text.replace('浇混凝土', '浇筑混凝土')
        text = text.replace('扎钢筋', '绑扎钢筋')
        text = text.replace('支模', '安装模板')
        text = text.replace('拆模', '拆除模板')
        text = text.replace('挖土', '土方开挖')
        text = text.replace('回填', '土方回填')
    elif category == 'supervision':
        text = text.replace('看了', '巡视检查')
        text = text.replace('查了', '检查')
        text = text.replace('验收了', '组织验收')
        text = text.replace('旁站了', '旁站监理')
        text = text.replace('说了', '口头指示')
        text = text.replace('要求整改', '要求施工单位整改')
        text = text.replace('要求停工', '要求施工单位停工')
        text = text.replace('要求返工', '要求施工单位返工')
        text = text.replace('开会', '召开会议')
        text = text.replace('签字', '签署')
    elif category == 'problem':
        text = text.replace('有问题', '存在问题')
        text = text.replace('不合格', '不符合要求')
        text = text.replace('让改', '责令整改')
        text = text.replace('要求改', '要求整改')
        text = text.replace('已改', '已整改完成')
        text = text.replace('整改了', '已整改完成')
        text = text.replace('罚款', '按合同约定处理')
    return text


def set_paragraph_format(paragraph, line_spacing_pt=16, first_line_indent_chars=2):
    """
    设置段落格式：固定行距和首行缩进。
    
    Args:
        paragraph: 段落XML元素 (w:p)
        line_spacing_pt: 行距（磅），默认16磅
        first_line_indent_chars: 首行缩进字符数，默认2字符
    """
    # 获取或创建段落属性
    pPr = paragraph.find(qn('w:pPr'))
    if pPr is None:
        pPr = OxmlElement('w:pPr')
        paragraph.insert(0, pPr)
    
    # 设置行距：固定值 line_spacing_pt 磅
    # line 值 = 磅数 × 20（单位为二十分之一磅）
    # lineRule="exact" 表示固定值
    spacing = pPr.find(qn('w:spacing'))
    if spacing is None:
        spacing = OxmlElement('w:spacing')
        pPr.append(spacing)
    spacing.set(qn('w:line'), str(int(line_spacing_pt * 20)))
    spacing.set(qn('w:lineRule'), 'exact')
    
    # 设置首行缩进：first_line_indent_chars 字符
    # firstLineChars 值 = 字符数 × 100（单位为百分之一字符）
    ind = pPr.find(qn('w:ind'))
    if ind is None:
        ind = OxmlElement('w:ind')
        pPr.append(ind)
    ind.set(qn('w:firstLineChars'), str(int(first_line_indent_chars * 100)))
    # 同时设置 firstLine（以二十分之一磅为单位），兼容旧版阅读器
    # 假设一个中文字符约22磅（小四号字），这里用一个合理的估算
    ind.set(qn('w:firstLine'), str(int(first_line_indent_chars * 22 * 20)))


def set_cell_text_formatted(cell, text, line_spacing_pt=16, first_line_indent_chars=2):
    """
    设置单元格文本，应用专业排版格式（固定行距、首行缩进）。
    
    Args:
        cell: 单元格XML元素
        text: 文本内容（多行用\n分隔）
        line_spacing_pt: 行距（磅），默认16磅
        first_line_indent_chars: 首行缩进字符数，默认2字符
    """
    # 清除现有段落内容，但保留第一个段落
    paragraphs = cell.findall(qn('w:p'))
    if not paragraphs:
        return
    
    first_p = paragraphs[0]
    for p in paragraphs[1:]:
        p.getparent().remove(p)
    
    # 获取第一个run的格式作为模板
    template_rPr = None
    runs = first_p.findall(qn('w:r'))
    if runs:
        rPr = runs[0].find(qn('w:rPr'))
        if rPr is not None:
            template_rPr = deepcopy(rPr)
    
    # 清除第一个段落的所有run
    for r in first_p.findall(qn('w:r')):
        first_p.remove(r)
    
    # 按行添加文本，每行一个段落
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if i > 0:
            new_p = OxmlElement('w:p')
            cell.append(new_p)
            target_p = new_p
        else:
            target_p = first_p
        
        # 设置段落格式（固定行距、首行缩进）
        set_paragraph_format(target_p, line_spacing_pt, first_line_indent_chars)
        
        # 创建run并添加文本
        new_r = OxmlElement('w:r')
        if template_rPr is not None:
            new_r.append(deepcopy(template_rPr))
        t = OxmlElement('w:t')
        t.text = line
        t.set(qn('xml:space'), 'preserve')
        new_r.append(t)
        target_p.append(new_r)


def set_cell_text(cell, text):
    """设置单元格文本（简单模式，不应用排版格式，用于表头、日期等短字段）。"""
    paragraphs = cell.findall(qn('w:p'))
    if not paragraphs:
        return
    first_p = paragraphs[0]
    for p in paragraphs[1:]:
        p.getparent().remove(p)
    template_rPr = None
    runs = first_p.findall(qn('w:r'))
    if runs:
        rPr = runs[0].find(qn('w:rPr'))
        if rPr is not None:
            template_rPr = deepcopy(rPr)
    for r in first_p.findall(qn('w:r')):
        first_p.remove(r)
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if i > 0:
            new_p = deepcopy(first_p)
            for r in new_p.findall(qn('w:r')):
                new_p.remove(r)
            cell.append(new_p)
            target_p = new_p
        else:
            target_p = first_p
        new_r = target_p.makeelement(qn('w:r'), {})
        if template_rPr is not None:
            new_r.append(deepcopy(template_rPr))
        t = new_r.makeelement(qn('w:t'), {})
        t.text = line
        t.set(qn('xml:space'), 'preserve')
        new_r.append(t)
        target_p.append(new_r)


def generate_diary(output_path, project_name='', date='', weather_am='', weather_pm='',
                   temp_high='', temp_low='', temp_avg='',
                   construction='', supervision='', problem='', other='',
                   diary_no_year='', diary_no_seq='', supervisor='', chief=''):
    """
    生成监理日志文件（基于15列新版模板，含专业排版控制）。
    """
    template_path = get_template_path()
    if not os.path.exists(template_path):
        raise FileNotFoundError(f'模板文件不存在: {template_path}')
    
    doc = Document(template_path)
    table = doc.tables[0]
    
    # 优化表达、智能摘要、编号核心内容
    construction_opt = optimize_and_number(construction, 'construction')
    supervision_opt = optimize_and_number(supervision, 'supervision')
    problem_opt = optimize_and_number(problem, 'problem')
    # 其他有关事项也做摘要精简，但不编号
    other_summary = summarize_content(other.strip(), 'other') if other else ''
    
    trs = table._tbl.tr_lst
    
    # 行1: 工程名称、编号
    if len(trs) > 1:
        tcs = trs[1].tc_lst
        if project_name and len(tcs) >= 2:
            set_cell_text(tcs[1], project_name)
        if diary_no_year and len(tcs) >= 4:
            set_cell_text(tcs[3], diary_no_year)
        if diary_no_seq and len(tcs) >= 6:
            set_cell_text(tcs[5], diary_no_seq)
    
    # 行2-3: 日期、星期、天气、气温
    if len(trs) > 3:
        tcs2 = trs[2].tc_lst
        tcs3 = trs[3].tc_lst
        if date and len(tcs2) >= 2:
            set_cell_text(tcs2[1], date)
        weekday = get_weekday(date)
        if weekday and len(tcs3) >= 2:
            set_cell_text(tcs3[1], weekday)
        if weather_am and len(tcs2) >= 5:
            set_cell_text(tcs2[4], weather_am)
        if weather_pm and len(tcs3) >= 5:
            set_cell_text(tcs3[4], weather_pm)
        if temp_high and len(tcs2) >= 7:
            set_cell_text(tcs2[6], f'最高{temp_high}℃')
        if temp_low and len(tcs3) >= 7:
            set_cell_text(tcs3[6], f'最低{temp_low}℃')
        if temp_avg and len(tcs3) >= 8:
            set_cell_text(tcs3[7], f'{temp_avg}℃')
    
    # 四大业务板块：应用专业排版（固定行距16磅、首行缩进2字符）
    # 行5: 当日施工进展情况
    if len(trs) > 5 and construction_opt:
        set_cell_text_formatted(trs[5].tc_lst[0], construction_opt,
                                 line_spacing_pt=16, first_line_indent_chars=2)
    # 行7: 当日监理工作情况
    if len(trs) > 7 and supervision_opt:
        set_cell_text_formatted(trs[7].tc_lst[0], supervision_opt,
                                 line_spacing_pt=16, first_line_indent_chars=2)
    # 行9: 当日存在的问题及处理情况
    if len(trs) > 9 and problem_opt:
        set_cell_text_formatted(trs[9].tc_lst[0], problem_opt,
                                 line_spacing_pt=16, first_line_indent_chars=2)
    # 行11: 其他有关事项
    if len(trs) > 11 and other_summary:
        set_cell_text_formatted(trs[11].tc_lst[0], other_summary,
                                 line_spacing_pt=16, first_line_indent_chars=2)
    
    # 行12: 签字
    if len(trs) > 12:
        tcs12 = trs[12].tc_lst
        if supervisor and len(tcs12) >= 2:
            set_cell_text(tcs12[1], supervisor)
        if chief and len(tcs12) >= 4:
            set_cell_text(tcs12[3], chief)
    
    # 保存
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    doc.save(output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description='监理日志生成器（含专业排版控制）')
    parser.add_argument('-o', '--output', required=True, help='输出文件路径')
    parser.add_argument('--project', default='', help='工程名称')
    parser.add_argument('--date', default='', help='日期')
    parser.add_argument('--weather-am', default='', help='上午天气')
    parser.add_argument('--weather-pm', default='', help='下午天气')
    parser.add_argument('--temp-high', default='', help='最高气温')
    parser.add_argument('--temp-low', default='', help='最低气温')
    parser.add_argument('--temp-avg', default='', help='平均温度')
    parser.add_argument('--construction', default='', help='当日施工进展情况（≤600字自动摘要）')
    parser.add_argument('--supervision', default='', help='当日监理工作情况（≤260字自动摘要）')
    parser.add_argument('--problem', default='', help='当日存在的问题及处理情况（≤160字自动摘要）')
    parser.add_argument('--other', default='', help='其他有关事项（≤120字自动摘要）')
    parser.add_argument('--diary-no-year', default='', help='监理日志编号-年份')
    parser.add_argument('--diary-no-seq', default='', help='监理日志编号-序号')
    parser.add_argument('--supervisor', default='', help='监理人员签字')
    parser.add_argument('--chief', default='', help='总监或总代签阅')
    parser.add_argument('--construction-file', default='', help='从文件读取当日施工进展情况')
    parser.add_argument('--supervision-file', default='', help='从文件读取当日监理工作情况')
    parser.add_argument('--problem-file', default='', help='从文件读取当日存在的问题及处理情况')
    
    args = parser.parse_args()
    
    construction = args.construction
    supervision = args.supervision
    problem = args.problem
    
    if args.construction_file and os.path.exists(args.construction_file):
        with open(args.construction_file, 'r', encoding='utf-8') as f:
            construction = f.read()
    if args.supervision_file and os.path.exists(args.supervision_file):
        with open(args.supervision_file, 'r', encoding='utf-8') as f:
            supervision = f.read()
    if args.problem_file and os.path.exists(args.problem_file):
        with open(args.problem_file, 'r', encoding='utf-8') as f:
            problem = f.read()
    
    output = generate_diary(
        output_path=args.output,
        project_name=args.project,
        date=args.date,
        weather_am=args.weather_am,
        weather_pm=args.weather_pm,
        temp_high=args.temp_high,
        temp_low=args.temp_low,
        temp_avg=args.temp_avg,
        construction=construction,
        supervision=supervision,
        problem=problem,
        other=args.other,
        diary_no_year=args.diary_no_year,
        diary_no_seq=args.diary_no_seq,
        supervisor=args.supervisor,
        chief=args.chief
    )
    
    print(f'✅ 监理日志已生成: {output}')


if __name__ == '__main__':
    main()
