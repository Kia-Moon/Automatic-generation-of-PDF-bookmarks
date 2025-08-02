# 文件名: bookmark_processor.py
# 这是你原始脚本的改造版本，专注于处理内存中的数据

import fitz  # PyMuPDF库
import io    # 用于在内存中操作字节流

# check_title_match 函数和你原来的一样，无需改动
def check_title_match(line_info, config):
    """检查单行文本是否符合任何级别的标题规则"""
    text = line_info['text']

    ex_conf = config.get('exclusion', {})
    if len(text) > ex_conf.get('max_line_length', 999): return None
    if any(char in text for char in ex_conf.get('exclude_chars', [])): return None
    if line_info['y0'] < ex_conf.get('min_y_coord', 0): return None
    if line_info['y0'] > ex_conf.get('max_y_coord', 9999): return None

    for level_name, rules in sorted(config.items()):
        if not level_name.startswith('level'): continue

        level = int(level_name.replace('level', ''))

        is_rule_active = any([rules.get('regex'), rules.get('font_contains'), rules.get('font_size'),
                              rules.get('is_bold') is not None, rules.get('indent_range')])
        if not is_rule_active: continue

        match_regex = rules.get('regex') is None or rules['regex'].match(text)
        match_font = not rules.get('font_contains') or any(f in line_info['font'] for f in rules['font_contains'])

        size_rule = rules.get('font_size', 0)
        match_size = False
        if not size_rule:
            match_size = True
        elif isinstance(size_rule, (list, tuple)):
            if size_rule[0] <= line_info['size'] <= size_rule[1]:
                match_size = True
        elif isinstance(size_rule, (int, float)):
            if line_info['size'] >= size_rule:
                match_size = True

        match_bold = rules.get('is_bold') is None or (line_info['is_bold'] == rules['is_bold'])

        indent_rule = rules.get('indent_range')
        match_indent = indent_rule is None or \
                       (isinstance(indent_rule, (list, tuple)) and \
                        indent_rule[0] <= line_info['x0'] <= indent_rule[1])

        if all([match_regex, match_font, match_size, match_bold, match_indent]):
            return [level, text, line_info['page_num'] + 1]

    return None

# 这是被改造的核心函数
def process_pdf_in_memory(uploaded_file, config, streamlit_status_ui):
    """
    在内存中处理上传的PDF文件。
    :param uploaded_file: Streamlit上传的文件对象。
    :param config: 从网页前端动态生成的配置字典。
    :param streamlit_status_ui: Streamlit的占位符，用于实时更新状态。
    :return: 一个元组 (包含处理后PDF的BytesIO流, 书签数量)
    """
    try:
        # 从内存中读取上传的文件流
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    except Exception as e:
        # 如果出错，直接抛出异常，让前端处理
        raise ValueError(f"无法打开或解析PDF文件。错误: {e}")

    toc = []
    total_pages = len(doc)

    for page_num in range(total_pages):
        # 通过UI组件实时更新处理进度
        progress_percent = (page_num + 1) / total_pages
        streamlit_status_ui.progress(progress_percent, text=f"正在扫描第 {page_num + 1}/{total_pages} 页...")

        page = doc.load_page(page_num)
        page_dict = page.get_text("dict", flags=fitz.TEXTFLAGS_SEARCH)

        lines_info = []
        for block in sorted(page_dict['blocks'], key=lambda b: b['bbox'][1]):
            if block['type'] == 0:
                for line in sorted(block['lines'], key=lambda l: l['bbox'][1]):
                    line_text = "".join([span['text'] for span in line['spans']]).strip()
                    if not line_text: continue
                    first_span = line['spans'][0]
                    lines_info.append({
                        'text': line_text, 'font': first_span['font'],
                        'size': round(first_span['size'], 2),
                        'is_bold': 'bold' in first_span['font'].lower(),
                        'x0': line['bbox'][0], 'y0': line['bbox'][1], 'page_num': page_num
                    })

        for line_info in lines_info:
            match = check_title_match(line_info, config)
            if match:
                toc.append(match)

    if not toc:
        doc.close()
        # 对于Web应用，最好也抛出异常，让前端知道发生了什么
        raise ValueError("处理完成，但未根据您的规则找到任何可生成的书签。")

    # 关键改动：不再保存到文件，而是保存到内存
    doc.set_toc(toc)
    pdf_buffer = io.BytesIO()
    doc.save(pdf_buffer, garbage=4, deflate=True, clean=True)
    doc.close()
    pdf_buffer.seek(0) # 将指针移回字节流的开头

    return pdf_buffer, len(toc)