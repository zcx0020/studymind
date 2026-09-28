"""parser/pdf.py —— PDF 解析：多策略链 + 扫描版 OCR 兜底

策略链（前一个失败/无文本自动切换下一个）:
  1. PyMuPDF (pymupdf): 最快，支持书签（TOC 用于组织章节结构）
  2. pdfplumber: 表格友好
  3. pypdf: 兼容性好
  无文本层（扫描版教材）→ Tesseract OCR（chi_sim 中文）逐页识别

书签(TOC)优先级最高: 有书签按书签切章节；无书签用标题启发式。
所有失败抛出带具体原因的 RuntimeError（前端直接展示给用户）。
"""
import re
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import pymupdf as fitz

MAX_PDF_SIZE = 300 * 1024 * 1024    # 300MB 上限，超过给出明确提示
OCR_DPI = 150                        # OCR 渲染分辨率（质量/速度平衡点）

HEADING_RE = re.compile(
    r"^(第[一二三四五六七八九十\d]+[章节篇]|[一二三四五六七八九十]+、"
    r"|（[一二三四五六七八九十]+）|\d+(\.\d+){0,2}\s)")


def parse_pdf(path: str, ocr_max_pages: Optional[int] = None,
              progress_cb: Optional[Callable[[int, int, str], None]] = None
              ) -> Tuple[List[dict], int, dict]:
    """解析 PDF → 章节列表。
    返回 (sections, page_count, meta)；meta = {strategy, has_toc, ocr, ocr_pages}
    """
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"文件不存在: {p.name}")
    size = p.stat().st_size
    if size > MAX_PDF_SIZE:
        raise RuntimeError(
            f"文件过大（{size // 1024 // 1024}MB），超过 {MAX_PDF_SIZE // 1024 // 1024}MB 上限，请拆分后上传")
    if size == 0:
        raise RuntimeError("文件为空，可能上传不完整")

    # ── 预检：打开 + 加密检查 + 书签 ──
    try:
        doc = fitz.open(path)
    except Exception as e:
        raise RuntimeError(f"PDF 文件无法打开（可能已损坏或格式异常）: {type(e).__name__}") from e
    try:
        if doc.needs_pass:
            raise RuntimeError("PDF 已加密，请提供无密码版本")
        page_count = doc.page_count
        if page_count == 0:
            raise RuntimeError("PDF 内容为空（0 页）")
        toc = doc.get_toc()
    finally:
        doc.close()

    # ── 策略 1：PyMuPDF 文本层 ──
    try:
        doc = fitz.open(path)
        try:
            texts = []
            for i in range(page_count):
                try:
                    texts.append(doc[i].get_text().strip())
                except Exception:
                    texts.append("")
        finally:
            doc.close()
        if sum(len(t) for t in texts) > 0:
            sections = build_sections(toc, texts, page_count)
            if sections:
                return sections, page_count, {"strategy": "fitz", "has_toc": bool(toc), "ocr": False}
    except RuntimeError:
        raise
    except Exception:
        pass

    # ── 策略 2：pdfplumber ──
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            texts = [(pg.extract_text() or "").strip() for pg in pdf.pages]
        if sum(len(t) for t in texts) > 0:
            sections = build_sections(toc, texts, page_count)
            if sections:
                return sections, page_count, {"strategy": "pdfplumber", "has_toc": bool(toc), "ocr": False}
    except RuntimeError:
        raise
    except Exception:
        pass

    # ── 策略 3：pypdf ──
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise RuntimeError("PDF 已加密，请提供无密码版本")
        texts = [(pg.extract_text() or "").strip() for pg in reader.pages]
        if sum(len(t) for t in texts) > 0:
            sections = build_sections(toc, texts, page_count)
            if sections:
                return sections, page_count, {"strategy": "pypdf", "has_toc": bool(toc), "ocr": False}
    except RuntimeError:
        raise
    except Exception:
        pass

    # ── 策略 4：无文本层（扫描版）→ OCR ──
    try:
        sections, ocr_pages = _ocr_pages(path, toc, page_count, ocr_max_pages, progress_cb)
        return sections, page_count, {
            "strategy": "ocr", "has_toc": bool(toc), "ocr": True, "ocr_pages": ocr_pages}
    except FileNotFoundError:
        raise RuntimeError("该 PDF 无文本层（扫描版），且服务器未安装 OCR 组件（tesseract + chi_sim），暂无法解析")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"OCR 识别失败: {type(e).__name__}: {e}") from e


# ══════════════ 章节构建 ══════════════

def build_sections(toc, texts: List[str], page_count: int) -> List[dict]:
    """按书签(TOC)组织章节；无书签/书签失效 → 标题启发式"""
    if toc:
        entries = []
        for lv, title, pg in toc:
            title = (title or "").strip()
            if title and 1 <= pg <= page_count:
                entries.append((lv, title, pg - 1))    # TOC 页码是 1-based
        if entries:
            sections = []
            for idx, (lv, title, start) in enumerate(entries):
                end = entries[idx + 1][2] if idx + 1 < len(entries) else page_count
                text = "\n".join(t for t in texts[start:end] if t).strip()
                if text:
                    sections.append({"level": lv, "title": title, "text": text, "page": start + 1})
            if sections:
                return sections
    return _sections_by_heuristic(texts, page_count)


def _sections_by_heuristic(texts: List[str], page_count: int) -> List[dict]:
    """无书签：按标题正则逐行切分章节"""
    sections: List[dict] = []
    cur = None
    for pi, text in enumerate(texts):
        for line in text.splitlines():
            line = line.strip()
            if not line or re.fullmatch(r"\d+", line):
                continue
            if HEADING_RE.match(line) and len(line) <= 40:
                title = HEADING_RE.sub("", line).strip() or line
                level = 1 if re.match(r"^第[一二三四五六七八九十\d]+[章篇]", line) else 2
                cur = {"level": level, "title": title, "text": "", "page": pi + 1}
                sections.append(cur)
            else:
                if cur is None:
                    cur = {"level": 1, "title": "", "text": "", "page": pi + 1}
                    sections.append(cur)
                cur["text"] += line + "\n"
    return [s for s in sections if s["text"].strip()]


# ══════════════ OCR ══════════════

def _ocr_pages(path: str, toc, page_count: int, max_pages: Optional[int],
               progress_cb: Optional[Callable[[int, int, str], None]]) -> Tuple[List[dict], int]:
    """Tesseract 中文 OCR 逐页识别（150dpi 渲染，约 1.5~2s/页）"""
    import pytesseract
    from PIL import Image

    pages = list(range(page_count))
    if max_pages and max_pages < page_count:
        pages = pages[:max_pages]

    texts = [""] * page_count
    doc = fitz.open(path)
    try:
        for n, i in enumerate(pages):
            if progress_cb:
                progress_cb(n + 1, len(pages), f"OCR 识别第 {n + 1}/{len(pages)} 页")
            with tempfile.TemporaryDirectory() as tmp:
                png = str(Path(tmp) / "page.png")
                doc[i].get_pixmap(dpi=OCR_DPI).save(png)
                texts[i] = pytesseract.image_to_string(Image.open(png), lang="chi_sim").strip()
    finally:
        doc.close()

    if not any(texts):
        raise RuntimeError("OCR 未能识别出任何文字（图片质量过低或内容为手写体）")
    return build_sections(toc, texts, page_count), len(pages)


# ══════════════ 分块 ══════════════

def _split_text(text: str, size: int = 700, overlap: int = 100) -> List[str]:
    """定长切分，优先在句末/行末断开"""
    if len(text) <= size:
        return [text]
    pieces, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            for sep in "。\n；;！？":
                idx = text.rfind(sep, start + size // 2, end)
                if idx > 0:
                    end = idx + 1
                    break
        pieces.append(text[start:end])
        start = max(end - overlap, start + 1)
    return pieces


def chunk_document(sections: List[dict]) -> Tuple[List[dict], List[dict]]:
    """章节 → 父子chunk。父=完整章节，子=检索块（指向父）"""
    parents, children = [], []
    for sec in sections:
        parent = {"section_path": sec["title"] or "正文", "content": sec["text"].strip(),
                  "page": sec.get("page", 0)}
        parents.append(parent)
        for piece in _split_text(parent["content"]):
            children.append({"section_path": sec["title"] or "正文", "content": piece,
                             "page": sec.get("page", 0), "parent": parent})
    return parents, children
