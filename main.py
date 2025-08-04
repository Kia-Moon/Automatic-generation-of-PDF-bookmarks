import streamlit as st
import re
from shuqian import process_pdf_in_memory  # 从我们改造的脚本中导入核心函数

# --- 页面基本配置 ---
st.set_page_config(
    page_title="PDF书签自动生成工具",
    page_icon="🔖",
    layout="wide"
)

st.title("🔖 PDF书签自动生成工具")
st.write("一个通用的、高度可配置的PDF书签自动化在线工具。上传您的PDF，在左侧配置规则，然后一键生成带书签的新PDF！")
st.markdown("---")


# --- 使用侧边栏来放置所有配置项 ---
with st.sidebar:
    st.header("⚙️ 在此配置规则")

    # --- 正则表达式参考 ---
    with st.expander("常见正则表达式参考", expanded=False):
        st.code("""
# 匹配 "第一章", "第二十章" 等:
^\\s*第[一二三四五六七八九十百]+章\\s*\\S+
# 匹配 “第1章”、“第10章”等:
^\\s*第\\s*\\d+\\s*章.*
# 匹配 "一、...", "十二、...":
^\\s*[一二三四五六七八九十百]+、\\s*\\S+
# 匹配 "1.1", "2.3.4":
^\\s*(\\d+\\.)+\\d*\\s*\\S+
        """, language="python")

    # --- 动态生成配置 ---
    # 使用会话状态来保存用户的配置
    if 'level_count' not in st.session_state:
        st.session_state.level_count = 2

    st.write("定义书签层级：")
    col1, col2 = st.columns(2)
    if col1.button("➕ 增加一级"):
        st.session_state.level_count += 1
    if col2.button("➖ 减少一级") and st.session_state.level_count > 1:
        st.session_state.level_count -= 1

    # 根据层级数量动态创建配置UI
    dynamic_config = {}
    for i in range(1, st.session_state.level_count + 1):
        with st.expander(f"📖 Level {i} 规则", expanded=(i <= 2)):
            st.write(f"--- {i}级标题规则 ---")
            regex_str = st.text_input(f"内容(Regex) L{i}", value=r"", key=f"regex_{i}", help="留空则不检查此项")
            font_size_mode = st.radio(f"字体大小模式 L{i}", ["不检查", "大于等于(弱)", "区间(强)"], key=f"fsmode_{i}", horizontal=True)

            font_size_value = None
            if font_size_mode == "大于等于(弱)":
                font_size_value = st.number_input(f"字体大小 ≥ L{i}", value=15.0, step=0.1, key=f"fs_weak_{i}")
            elif font_size_mode == "区间(强)":
                fs_cols = st.columns(2)
                min_fs = fs_cols[0].number_input(f"最小字号 L{i}", value=13.9, step=0.1, key=f"fs_min_{i}")
                max_fs = fs_cols[1].number_input(f"最大字号 L{i}", value=14.1, step=0.1, key=f"fs_max_{i}")
                font_size_value = [min_fs, max_fs]

            is_bold = st.selectbox(f"是否粗体 L{i}", [None, True, False], format_func=lambda x: {None:"不检查", True:"是", False:"否"}[x], key=f"bold_{i}")

            use_indent = st.checkbox(f"检查缩进 L{i}", key=f"indent_check_{i}")
            indent_range_value = None
            if use_indent:
                ind_cols = st.columns(2)
                min_ind = ind_cols[0].number_input(f"最小缩进 L{i}", value=50, key=f"ind_min_{i}")
                max_ind = ind_cols[1].number_input(f"最大缩进 L{i}", value=100, key=f"ind_max_{i}")
                indent_range_value = [min_ind, max_ind]

            # 收集配置
            dynamic_config[f'level{i}'] = {
                'regex': re.compile(regex_str) if regex_str else None,
                'font_contains': [], # 为简化UI，此项暂时不提供
                'font_size': font_size_value,
                'is_bold': is_bold,
                'indent_range': indent_range_value
            }

    with st.expander("全局排除规则", expanded=True):
        max_len = st.number_input("标题最大字数", value=40)
        exclude_chars_str = st.text_input("排除包含以下字符的行(直接添加无需空格)", value="¿")
        min_y = st.number_input("排除页眉(Y坐标小于)", value=50)
        max_y = st.number_input("排除页脚(Y坐标大于)", value=800)
        dynamic_config['exclusion'] = {
            'max_line_length': max_len,
            'exclude_chars': list(exclude_chars_str),
            'min_y_coord': min_y,
            'max_y_coord': max_y
        }

# --- 主界面 ---
uploaded_file = st.file_uploader(
    "1. 上传您的PDF文件",
    type="pdf"
)

if uploaded_file is not None:
    st.success(f"文件 '{uploaded_file.name}' 上传成功！")

    if st.button("🚀 2. 开始生成书签", use_container_width=True):
        # 创建一个状态占位符
        status_ui = st.empty()
        try:
            with st.spinner("正在初始化处理..."):
                # 调用改造后的核心函数
                processed_pdf_buffer, bookmark_count = process_pdf_in_memory(uploaded_file, dynamic_config, status_ui)

            st.success(f"🎉 处理完成！成功生成了 {bookmark_count} 个书签。")

            # 提供下载按钮
            st.download_button(
                label="📥 3. 下载带书签的PDF文件",
                data=processed_pdf_buffer,
                file_name=f"带书签_{uploaded_file.name}",
                mime="application/pdf",
                use_container_width=True
            )
        except ValueError as e:
            # 优雅地处理我们自己抛出的错误
            st.error(f"处理失败：{e}")

            # 特别处理你附录中提到的层级错误
            if "hierarchy level" in str(e).lower():
                 st.info("""**提示：** 这个错误通常意味着PDF的第一个书签不是一级标题。这可能是因为书籍的“前言”、“序言”等部分的标题出现在了第一个一级标题（如“第一章”）之前。
                 \n**解决方法：**
                 \n1. 检查您为`Level 1`设置的规则是否能正确匹配到“第一章”这类标题。
                 \n2. 如果需要为“前言”等创建书签，请确保它们的规则也设置为`Level 1`。""")