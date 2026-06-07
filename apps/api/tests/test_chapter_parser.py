"""单元测试 - 章节识别（中/英文/Markdown）、段落编号

测试ChapterParser的12种章节模式正则和编码检测功能。
"""

import pytest
from app.services.chapter_parser import ChapterParser


# ===== 测试用例 =====


class TestChineseChapterPattern:
    """测试中文数字章节模式"""

    def setup_method(self):
        self.parser = ChapterParser()

    def test_chinese_number_chapter(self):
        """第X章 格式"""
        text = """第一章 初遇

清晨的阳光透过窗帘缝隙照进房间。

第二章 相识

他们在公司相遇，彼此对视一眼。

第三章 冲突

矛盾开始显现，两人发生了争执。"""

        chapters = self.parser.parse(text)
        assert len(chapters) == 3
        assert chapters[0]["title"] == "初遇"
        assert chapters[1]["title"] == "相识"
        assert chapters[2]["title"] == "冲突"

    def test_chinese_number_chapter_with_colon(self):
        """第X章：格式（带冒号）"""
        text = """第一章：命运的开始

故事从这里开始。

第二章：意外的相遇

一切发生得那么突然。"""

        chapters = self.parser.parse(text)
        assert len(chapters) == 2
        assert "命运的开始" in chapters[0]["title"]
        assert "意外的相遇" in chapters[1]["title"]

    def test_chinese_number_chapter_large(self):
        """大章节号（如第十二章）"""
        text = """第十二章 重要的决定

他们终于做出了决定。

第十三章 新的开始

一切重新开始。

第二十章 最终的对决

决战时刻来临。"""

        chapters = self.parser.parse(text)
        assert len(chapters) == 3

    def test_chinese_number_chapter_mixed(self):
        """混合阿拉伯数字和中文数字"""
        text = """第1章 开篇

这是第一章的内容。

第2章 发展

故事进一步发展。

第3章 结局

最终的结局。"""

        chapters = self.parser.parse(text)
        assert len(chapters) >= 2


class TestChineseSectionPattern:
    """测试中文节模式"""

    def setup_method(self):
        self.parser = ChapterParser()

    def test_chinese_section(self):
        """第X节格式"""
        text = """第一节 引言

这是引言部分。

第二节 分析

分析开始。

第三节 结论

得出结论。"""

        chapters = self.parser.parse(text)
        assert len(chapters) == 3


class TestEnglishChapterPattern:
    """测试英文章节模式"""

    def setup_method(self):
        self.parser = ChapterParser()

    def test_english_chapter_lowercase(self):
        """Chapter X格式（小写）"""
        text = """Chapter 1 The Beginning

The story starts here.

Chapter 2 The Journey

The adventure begins.

Chapter 3 The End

Everything concludes."""

        chapters = self.parser.parse(text)
        assert len(chapters) == 3
        assert "Chapter 1" in chapters[0]["title"]
        assert "Chapter 2" in chapters[1]["title"]

    def test_english_chapter_uppercase(self):
        """CHAPTER X格式（大写）"""
        text = """CHAPTER 1 INTRODUCTION

This is the introduction.

CHAPTER 2 MAIN STORY

The main story begins.

CHAPTER 3 CONCLUSION

The story ends."""

        chapters = self.parser.parse(text)
        assert len(chapters) == 3
        assert "CHAPTER 1" in chapters[0]["title"]


class TestMarkdownHeadingPattern:
    """测试Markdown标题模式"""

    def setup_method(self):
        self.parser = ChapterParser()

    def test_markdown_h1_heading(self):
        """# 标题格式"""
        text = """# 第一章

这是第一章的内容。

# 第二章

这是第二章的内容。

# 第三章

这是第三章的内容。"""

        chapters = self.parser.parse(text)
        assert len(chapters) == 3

    def test_markdown_h2_heading(self):
        """## 标题格式"""
        text = """## 开篇

这是开篇。

## 发展

故事发展。

## 结局

故事结局。"""

        chapters = self.parser.parse(text)
        assert len(chapters) >= 2


class TestBracketTitlePattern:
    """测试括号标题模式"""

    def setup_method(self):
        self.parser = ChapterParser()

    def test_bracket_title(self):
        """【XXX】格式"""
        text = """【序章】

这是序章内容。

【第一章：初遇】

这是第一章。

【尾声】

这是尾声。"""

        chapters = self.parser.parse(text)
        assert len(chapters) == 3


class TestVolumeChapterPattern:
    """测试卷-章结构模式"""

    def setup_method(self):
        self.parser = ChapterParser()

    def test_volume_chapter_structure(self):
        """卷X第Y章格式"""
        text = """卷一 第一章

内容开始。

卷一 第二章

继续内容。

卷二 第一章

新卷开始。"""

        chapters = self.parser.parse(text)
        assert len(chapters) >= 2


class TestNumericChapterPattern:
    """测试纯数字编号模式"""

    def setup_method(self):
        self.parser = ChapterParser()

    def test_numeric_chapter(self):
        """数字编号格式"""
        text = """1. 开篇

这是开篇内容。

2. 发展

故事发展。

3. 结局

故事结局。"""

        chapters = self.parser.parse(text)
        assert len(chapters) >= 2


class TestBlankLineSeparator:
    """测试空行分隔模式"""

    def setup_method(self):
        self.parser = ChapterParser()

    def test_blank_line_separator(self):
        """≥2空行分隔"""
        text = """第一段内容，讲述故事的开始。


第二段内容，故事发展。


第三段内容，故事结局。"""

        chapters = self.parser.parse(text)
        assert len(chapters) >= 2

    def test_no_pattern_fallback(self):
        """没有任何章节标记时的回退"""
        text = """这是一段没有章节标记的文本。
内容很丰富，但没有任何章节标题。

这是另一段内容。
同样没有章节标记。"""

        chapters = self.parser.parse(text)
        assert len(chapters) >= 1


class TestParagraphIndexing:
    """测试段落编号功能"""

    def setup_method(self):
        self.parser = ChapterParser()

    def test_paragraph_splitting(self):
        """段落分割"""
        text = """第一章 测试

第一段内容。

第二段内容，继续叙述。

第三段，最后的描述。"""

        chapters = self.parser.parse(text)
        assert len(chapters) >= 1
        paragraphs = chapters[0].get("paragraphs", [])
        assert len(paragraphs) >= 1

    def test_paragraph_preservation(self):
        """段落内容不丢失"""
        text = """第一章 测试

这是一段很长的内容，包含了多个句子。
每个句子都有其意义。
段落中的所有内容都应该被保留。"""

        chapters = self.parser.parse(text)
        all_text = " ".join([
            p for ch in chapters
            for p in ch.get("paragraphs", [])
        ])
        assert "内容" in all_text
        assert "句子" in all_text
        assert "保留" in all_text


class TestEncodingDetection:
    """测试编码检测功能"""

    def setup_method(self):
        self.parser = ChapterParser()

    def test_utf8_encoding(self):
        """UTF-8编码检测"""
        content = "这是UTF-8编码的中文文本".encode("utf-8")
        result = self.parser.detect_and_decode(content)
        assert "中文文本" in result
        assert self.parser.last_detected_encoding == "utf-8"

    def test_gbk_encoding(self):
        """GBK编码检测"""
        content = "这是GBK编码的中文文本".encode("gbk")
        result = self.parser.detect_and_decode(content)
        assert "中文" in result
        assert self.parser.last_detected_encoding in ["gbk", "gb18030"]

    def test_gb2312_encoding(self):
        """GB2312编码检测"""
        content = "这是GB2312编码的文本".encode("gb2312")
        result = self.parser.detect_and_decode(content)
        assert "文本" in result

    def test_mixed_encoding_fallback(self):
        """编码检测兜底"""
        # 使用一些奇怪的字节
        content = b"\xff\xfe\x00\x00"
        result = self.parser.detect_and_decode(content)
        assert isinstance(result, str)


class TestChineseNumberConversion:
    """测试中文数字转换"""

    def setup_method(self):
        self.parser = ChapterParser()

    def test_simple_chinese_number(self):
        """简单中文数字"""
        assert self.parser.chinese_to_int("一") == 1
        assert self.parser.chinese_to_int("三") == 3
        assert self.parser.chinese_to_int("十") == 10

    def test_complex_chinese_number(self):
        """复合中文数字"""
        assert self.parser.chinese_to_int("十一") == 11
        assert self.parser.chinese_to_int("二十三") == 23
        assert self.parser.chinese_to_int("一百") == 100

    def test_arabic_in_chinese(self):
        """混合阿拉伯数字"""
        assert self.parser.chinese_to_int("5") == 5
        assert self.parser.chinese_to_int("12") == 12

    def test_empty_input(self):
        """空输入"""
        assert self.parser.chinese_to_int("") == 0