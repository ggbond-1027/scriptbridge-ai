r"""章节解析服务 - 支持12种章节模式正则

解析模式：
1. 第[一二三四五六七八九十百千万0-9]+章
2. 第[一二三四五六七八九十百千万0-9]+节
3. Chapter\s+\d+
4. CHAPTER\s+\d+
5. Markdown标题 # 或 ##
6. 【.*】格式
7. 卷-章结构
8. 纯数字编号
9. 空行分隔（≥2空行）
10. Vol\.结构
11. Part/Episode结构
12. 自定义分隔符（===、***等）

编码检测：UTF-8/GBK/GB2312，自动转换
"""

from typing import Any, Dict, List, Optional, Tuple
import re
import logging

logger = logging.getLogger(__name__)


class ChapterParser:
    """章节解析器 - 支持12种章节模式识别"""

    # 12种章节模式正则
    CHAPTER_PATTERNS: List[Tuple[str, re.Pattern]] = [
        # 1. 中文数字章节：第X章
        ("chinese_chapter", re.compile(
            r'^第[一二三四五六七八九十百千万零〇\d]+章\s*[：:]*\s*(.*)$',
            re.MULTILINE
        )),
        # 2. 中文数字节：第X节
        ("chinese_section", re.compile(
            r'^第[一二三四五六七八九十百千万零〇\d]+节\s*[：:]*\s*(.*)$',
            re.MULTILINE
        )),
        # 3. Chapter X (英文小写)
        ("english_chapter_lower", re.compile(
            r'^Chapter\s+(\d+)\s*[.:]*\s*(.*)$',
            re.MULTILINE
        )),
        # 4. CHAPTER X (英文大写)
        ("english_chapter_upper", re.compile(
            r'^CHAPTER\s+(\d+)\s*[.:]*\s*(.*)$',
            re.MULTILINE
        )),
        # 5. Markdown标题 # 或 ##
        ("markdown_heading", re.compile(
            r'^#{1,3}\s+(.+)$',
            re.MULTILINE
        )),
        # 6. 【.*】格式（括号标题）
        ("bracket_title", re.compile(
            r'^【(.+)】\s*$',
            re.MULTILINE
        )),
        # 7. 卷-章结构：卷X 第Y章
        ("volume_chapter", re.compile(
            r'^卷[一二三四五六七八九十百千万\d]+\s*第[一二三四五六七八九十百千万\d]+章\s*[：:]*\s*(.*)$',
            re.MULTILINE
        )),
        # 8. 纯数字编号（独立行）
        ("numeric_chapter", re.compile(
            r'^(\d+)\.\s+(.+)$',
            re.MULTILINE
        )),
        # 9. 空行分隔（≥2空行视为分界）- 在解析时处理
        ("blank_line_separator", None),
        # 10. Vol.结构
        ("vol_structure", re.compile(
            r'^Vol\.?\s*(\d+)\s*[.:]*\s*(.*)$',
            re.MULTILINE | re.IGNORECASE
        )),
        # 11. Part/Episode结构
        ("part_episode", re.compile(
            r'^(?:Part|Episode|Ep)\.?\s*(\d+)\s*[.:]*\s*(.*)$',
            re.MULTILINE | re.IGNORECASE
        )),
        # 12. 自定义分隔符（===、***、---等）
        ("custom_separator", re.compile(
            r'^={3,}\s*$|^-{3,}\s*$|^\*{3,}\s*$',
            re.MULTILINE
        )),
    ]

    # 中文数字映射
    CHINESE_NUM_MAP = {
        '零': 0, '〇': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '百': 100, '千': 1000, '万': 10000,
    }

    def __init__(self):
        self.last_detected_encoding: str = "utf-8"
        self.last_detected_patterns: List[str] = []

    def parse(self, source_text: str) -> List[Dict[str, Any]]:
        """
        解析小说文本，识别章节结构

        Args:
            source_text: 小说全文

        Returns:
            章节列表，每个章节包含：order, title, source_title, paragraphs
        """
        if not source_text or not source_text.strip():
            return []

        # 检测文本中存在的章节模式
        detected = self._detect_patterns(source_text)
        self.last_detected_patterns = detected

        # 根据检测到的模式选择解析策略
        if not detected:
            # 没有检测到任何章节标记，使用空行分隔模式
            return self._parse_by_blank_lines(source_text)

        # 使用检测到的最强模式进行解析
        chapters = self._parse_with_pattern(source_text, detected[0])

        # 如果主要模式解析结果太少，尝试混合模式
        if len(chapters) <= 1 and len(detected) > 1:
            chapters = self._parse_mixed(source_text, detected)

        return chapters

    def detect_and_decode(self, content_bytes: bytes) -> str:
        """
        自动检测编码并解码为UTF-8字符串

        支持检测: UTF-8, GBK, GB2312, GB18030, Big5, Latin-1
        """
        # 优先尝试UTF-8
        try:
            text = content_bytes.decode("utf-8")
            # 验证解码是否合理（检查是否有乱码字符）
            if self._is_valid_text(text):
                self.last_detected_encoding = "utf-8"
                return text
        except UnicodeDecodeError:
            pass

        # 尝试chardet自动检测
        try:
            import chardet
            result = chardet.detect(content_bytes)
            detected_encoding = result.get("encoding", "utf-8")
            confidence = result.get("confidence", 0)

            if confidence > 0.7:
                try:
                    text = content_bytes.decode(detected_encoding)
                    if self._is_valid_text(text):
                        self.last_detected_encoding = detected_encoding
                        return text
                except (UnicodeDecodeError, LookupError):
                    pass
        except ImportError:
            logger.warning("chardet未安装，将使用手动编码检测")

        # 手动尝试常见中文编码
        encodings_to_try = ["gbk", "gb18030", "gb2312", "big5", "latin-1"]
        for encoding in encodings_to_try:
            try:
                text = content_bytes.decode(encoding)
                if self._is_valid_text(text):
                    self.last_detected_encoding = encoding
                    return text
            except (UnicodeDecodeError, LookupError):
                continue

        # 最后兜底：使用utf-8 with error handling
        self.last_detected_encoding = "utf-8"
        return content_bytes.decode("utf-8", errors="replace")

    def _is_valid_text(self, text: str) -> bool:
        """检查解码后的文本是否合理（不是乱码）"""
        if not text:
            return False

        # 检查是否有过多的控制字符（乱码特征）
        control_count = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t')
        if control_count > len(text) * 0.01:  # 控制字符超过1%
            return False

        # 检查是否有中文或英文字符（有效文本特征）
        has_cjk = any('\u4e00' <= c <= '\u9fff' for c in text[:500])
        has_ascii = any('a' <= c <= 'z' or 'A' <= c <= 'Z' for c in text[:500])

        return has_cjk or has_ascii

    def _detect_patterns(self, source_text: str) -> List[str]:
        """检测文本中存在的章节模式"""
        detected = []

        for pattern_name, pattern in self.CHAPTER_PATTERNS:
            if pattern is None:
                continue  # 空行分隔模式在后面单独检测

            matches = pattern.findall(source_text)
            if len(matches) >= 2:  # 至少出现2次才认为是章节标记模式
                detected.append(pattern_name)

        # 检查空行分隔：如果有很多连续空行（≥2空行出现≥2次）
        blank_sections = re.split(r'\n{3,}', source_text)
        if len(blank_sections) >= 3:
            detected.append("blank_line_separator")

        return detected

    def _parse_with_pattern(
        self, source_text: str, pattern_name: str
    ) -> List[Dict[str, Any]]:
        """使用指定模式解析章节"""

        pattern_entry = None
        for name, pattern in self.CHAPTER_PATTERNS:
            if name == pattern_name:
                pattern_entry = (name, pattern)
                break

        if not pattern_entry or pattern_entry[1] is None:
            return self._parse_by_blank_lines(source_text)

        pattern = pattern_entry[1]
        chapters = []

        # 找到所有章节标题的行号和内容
        lines = source_text.split('\n')
        chapter_starts: List[Tuple[int, str, str]] = []  # (line_idx, title, source_title)

        for idx, line in enumerate(lines):
            match = pattern.match(line.strip())
            if match:
                groups = match.groups()
                title = self._extract_title(pattern_name, groups)
                source_title = line.strip()
                chapter_starts.append((idx, title, source_title))

        if not chapter_starts:
            return self._parse_by_blank_lines(source_text)

        # 根据标题位置切割章节内容
        for i, (start_idx, title, source_title) in enumerate(chapter_starts):
            if i < len(chapter_starts) - 1:
                end_idx = chapter_starts[i + 1][0]
            else:
                end_idx = len(lines)

            # 提取章节内容（排除标题行）
            chapter_lines = lines[start_idx + 1:end_idx]
            paragraphs = self._split_paragraphs(chapter_lines)

            chapters.append({
                "order": i + 1,
                "title": title,
                "source_title": source_title,
                "paragraphs": paragraphs,
            })

        # 如果第一个标题之前有内容，作为"前言"或"序章"
        if chapter_starts[0][0] > 0:
            preamble_lines = lines[:chapter_starts[0][0]]
            preamble_paragraphs = self._split_paragraphs(preamble_lines)
            if preamble_paragraphs:
                chapters.insert(0, {
                    "order": 0,
                    "title": "序章/前言",
                    "source_title": "",
                    "paragraphs": preamble_paragraphs,
                })
                # 调整后续章节的order
                for i, ch in enumerate(chapters[1:], 1):
                    ch["order"] = i

        return chapters

    def _parse_by_blank_lines(self, source_text: str) -> List[Dict[str, Any]]:
        """使用空行分隔（≥2空行）解析章节"""
        sections = re.split(r'\n{3,}', source_text.strip())

        chapters = []
        for i, section in enumerate(sections):
            if not section.strip():
                continue

            paragraphs = self._split_paragraphs(section.split('\n'))

            # 尝试从第一行提取标题
            first_line = section.strip().split('\n')[0].strip()
            title = first_line if len(first_line) < 50 else f"第{i+1}部分"

            chapters.append({
                "order": i + 1,
                "title": title,
                "source_title": first_line,
                "paragraphs": paragraphs,
            })

        return chapters

    def _parse_mixed(
        self, source_text: str, detected_patterns: List[str]
    ) -> List[Dict[str, Any]]:
        """混合模式解析：当单一模式不够时组合多种模式"""

        # 合并所有检测到的模式的匹配位置
        lines = source_text.split('\n')
        all_breaks: List[Tuple[int, str]] = []

        for pattern_name in detected_patterns:
            pattern_entry = None
            for name, pattern in self.CHAPTER_PATTERNS:
                if name == pattern_name:
                    pattern_entry = (name, pattern)
                    break

            if not pattern_entry or pattern_entry[1] is None:
                continue

            pattern = pattern_entry[1]
            for idx, line in enumerate(lines):
                if pattern.match(line.strip()):
                    all_breaks.append((idx, line.strip()))

        # 按行号排序并去重
        all_breaks.sort(key=lambda x: x[0])
        unique_breaks = []
        seen = set()
        for idx, title in all_breaks:
            if idx not in seen:
                seen.add(idx)
                unique_breaks.append((idx, title))

        # 生成章节
        chapters = []
        for i, (start_idx, title) in enumerate(unique_breaks):
            if i < len(unique_breaks) - 1:
                end_idx = unique_breaks[i + 1][0]
            else:
                end_idx = len(lines)

            chapter_lines = lines[start_idx + 1:end_idx]
            paragraphs = self._split_paragraphs(chapter_lines)

            chapters.append({
                "order": i + 1,
                "title": title[:50],  # 截断过长标题
                "source_title": title,
                "paragraphs": paragraphs,
            })

        return chapters if len(chapters) > 1 else self._parse_by_blank_lines(source_text)

    def _split_paragraphs(self, lines: List[str]) -> List[str]:
        """将行列表分割为段落列表"""
        paragraphs = []
        current_paragraph = []

        for line in lines:
            stripped = line.strip()
            if stripped:
                current_paragraph.append(stripped)
            else:
                if current_paragraph:
                    paragraphs.append(" ".join(current_paragraph))
                    current_paragraph = []

        if current_paragraph:
            paragraphs.append(" ".join(current_paragraph))

        # 过滤过短的段落（可能是空行残留）
        return [p for p in paragraphs if len(p.strip()) > 0]

    def _extract_title(self, pattern_name: str, groups: tuple) -> str:
        """从正则匹配结果中提取章节标题"""
        if not groups:
            return "未命名章节"

        if pattern_name == "chinese_chapter":
            # 第X章 标题
            if len(groups) >= 1:
                title = groups[0].strip() if groups[0] else ""
                return title or "未命名章节"

        elif pattern_name == "chinese_section":
            if len(groups) >= 1:
                title = groups[0].strip() if groups[0] else ""
                return title or "未命名章节"

        elif pattern_name in ("english_chapter_lower", "english_chapter_upper"):
            # Chapter X: 标题
            prefix = "CHAPTER" if pattern_name == "english_chapter_upper" else "Chapter"
            if len(groups) >= 2:
                chapter_num = groups[0]
                title = groups[1].strip() if groups[1] else ""
                return f"{prefix} {chapter_num}" + (f": {title}" if title else "")
            elif len(groups) >= 1:
                return f"{prefix} {groups[0]}"

        elif pattern_name == "markdown_heading":
            return groups[0].strip() if groups[0] else "未命名章节"

        elif pattern_name == "bracket_title":
            return groups[0].strip() if groups[0] else "未命名章节"

        elif pattern_name == "volume_chapter":
            return groups[0].strip() if groups[0] else "未命名章节"

        elif pattern_name == "numeric_chapter":
            if len(groups) >= 2:
                return f"{groups[0]}. {groups[1].strip()}"
            return groups[0].strip() if groups[0] else "未命名章节"

        elif pattern_name in ("vol_structure", "part_episode"):
            if len(groups) >= 2:
                return f"Vol {groups[0]}" + (f": {groups[1].strip()}" if groups[1] else "")
            elif len(groups) >= 1:
                return f"Vol {groups[0]}"

        return "未命名章节"

    def chinese_to_int(self, chinese_num: str) -> int:
        """
        将中文数字转换为整数

        支持格式：
        - 简单：一、二、三...十
        - 组合：十一、二十三、一百零五
        """
        if not chinese_num:
            return 0

        # 如果包含阿拉伯数字，直接提取
        if any(c.isdigit() for c in chinese_num):
            digits = ''.join(c for c in chinese_num if c.isdigit())
            return int(digits) if digits else 0

        result = 0
        temp = 0

        for char in chinese_num:
            if char in self.CHINESE_NUM_MAP:
                value = self.CHINESE_NUM_MAP[char]

                if value >= 10:
                    if temp == 0:
                        temp = 1
                    result += temp * value
                    temp = 0
                else:
                    temp = value

        result += temp
        return result
