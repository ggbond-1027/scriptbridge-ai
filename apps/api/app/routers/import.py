"""小说导入 API - 导入小说文本、章节检测"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request, Query
import io

from app.services.chapter_parser import ChapterParser

router = APIRouter()


# 内存存储
_import_store: Dict[str, Dict[str, Any]] = {}


@router.post("/upload", summary="上传小说文件")
async def upload_novel(
    file: UploadFile = File(..., description="小说文本文件（支持TXT格式）"),
    project_id: Optional[str] = Form(default=None, description="关联项目ID"),
    encoding: Optional[str] = Form(default=None, description="指定编码（自动检测则留空）"),
):
    """上传小说文件，自动进行编码检测和章节识别"""

    # 读取文件内容
    content_bytes = await file.read()

    # 编码检测与转换
    parser = ChapterParser()
    if encoding:
        try:
            source_text = content_bytes.decode(encoding)
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail=f"无法使用编码 {encoding} 解码文件")
    else:
        source_text = parser.detect_and_decode(content_bytes)

    # 章节识别
    chapters = parser.parse(source_text)

    # 存储导入数据
    import_id = file.filename or "upload"
    import_data = {
        "import_id": import_id,
        "project_id": project_id,
        "filename": file.filename,
        "encoding": parser.last_detected_encoding,
        "source_text": source_text,
        "source_text_length": len(source_text),
        "chapter_count": len(chapters),
        "chapters": chapters,
    }

    _import_store[import_id] = import_data

    return {
        "import_id": import_id,
        "filename": file.filename,
        "encoding": parser.last_detected_encoding,
        "source_text_length": len(source_text),
        "chapter_count": len(chapters),
        "chapters_preview": [
            {
                "title": ch.get("title", ""),
                "order": ch.get("order", idx + 1),
                "paragraph_count": len(ch.get("paragraphs", [])),
                "preview": ch.get("paragraphs", [""])[0][:100] if ch.get("paragraphs") else "",
            }
            for idx, ch in enumerate(chapters[:10])  # 只返回前10章预览
        ],
    }


@router.post("/text", summary="导入小说文本")
async def import_text(
    source_text: str = Form(..., description="小说文本内容"),
    project_id: Optional[str] = Form(default=None, description="关联项目ID"),
    title: Optional[str] = Form(default="未命名小说", description="小说标题"),
):
    """直接传入小说文本内容进行导入和章节识别"""

    parser = ChapterParser()
    chapters = parser.parse(source_text)

    import_id = f"text_{len(_import_store) + 1}"
    import_data = {
        "import_id": import_id,
        "project_id": project_id,
        "filename": None,
        "title": title,
        "encoding": "utf-8",
        "source_text": source_text,
        "source_text_length": len(source_text),
        "chapter_count": len(chapters),
        "chapters": chapters,
    }

    _import_store[import_id] = import_data

    return {
        "import_id": import_id,
        "title": title,
        "source_text_length": len(source_text),
        "chapter_count": len(chapters),
        "chapters_preview": [
            {
                "title": ch.get("title", ""),
                "order": ch.get("order", idx + 1),
                "paragraph_count": len(ch.get("paragraphs", [])),
                "preview": ch.get("paragraphs", [""])[0][:100] if ch.get("paragraphs") else "",
            }
            for idx, ch in enumerate(chapters[:10])
        ],
    }


@router.get("/detect-chapters", summary="检测章节结构")
async def detect_chapters(
    source_text: str = Query(..., description="小说文本内容"),
):
    """检测小说文本中的章节结构（不导入，仅检测）"""
    parser = ChapterParser()
    chapters = parser.parse(source_text)

    return {
        "chapter_count": len(chapters),
        "chapters": [
            {
                "title": ch.get("title", ""),
                "order": ch.get("order", idx + 1),
                "paragraph_count": len(ch.get("paragraphs", [])),
                "first_paragraph_preview": ch.get("paragraphs", [""])[0][:200] if ch.get("paragraphs") else "",
            }
            for idx, ch in enumerate(chapters)
        ],
        "detected_patterns": parser.last_detected_patterns,
    }


@router.get("/detect-encoding", summary="检测文件编码")
async def detect_encoding(
    file: UploadFile = File(..., description="需要检测编码的文件"),
):
    """检测上传文件的编码格式"""
    content_bytes = await file.read()
    parser = ChapterParser()
    source_text = parser.detect_and_decode(content_bytes)

    return {
        "detected_encoding": parser.last_detected_encoding,
        "file_size": len(content_bytes),
        "decoded_text_preview": source_text[:500],
    }


@router.get("/history/{import_id}", summary="获取导入历史")
async def get_import_history(import_id: str):
    """获取指定导入的详细信息"""
    import_data = _import_store.get(import_id)
    if not import_data:
        raise HTTPException(status_code=404, detail=f"导入记录 {import_id} 不存在")

    return {
        "import_id": import_data["import_id"],
        "filename": import_data["filename"],
        "encoding": import_data["encoding"],
        "source_text_length": import_data["source_text_length"],
        "chapter_count": import_data["chapter_count"],
        "chapters": import_data["chapters"],
    }


@router.delete("/history/{import_id}", summary="删除导入记录")
async def delete_import_history(import_id: str):
    """删除指定导入记录"""
    if import_id not in _import_store:
        raise HTTPException(status_code=404, detail=f"导入记录 {import_id} 不存在")

    _import_store.pop(import_id)
    return {"message": f"导入记录 {import_id} 已删除"}