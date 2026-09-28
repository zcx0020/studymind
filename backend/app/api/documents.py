"""api/documents.py —— 教材列表 + PDF 上传（增强项入口）+ 删除/重试"""
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api import deps
from app.config import settings
from app.services import taskman
from app.services.llm import get_embedder
from app.services.parser.ingest import ingest_pdf

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def list_documents(user_id: int = 1, pg=Depends(deps.get_pg)):
    with pg.cursor() as cur:
        cur.execute("""SELECT d.id, d.title, d.source_type, d.parse_status, d.created_at,
                              d.error_message,
                              (SELECT COUNT(*) FROM knowledge_points kp
                               WHERE kp.document_id = d.id) AS kp_count
                       FROM documents d
                       WHERE d.user_id=%s ORDER BY d.id DESC""", (user_id,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return {"items": rows}


def _purge_doc_data(pg, doc_id: int, keep_document: bool = False):
    """清理教材关联数据：PG（按外键依赖顺序）+ Neo4j + Chroma。
    keep_document=True 时保留 documents 行（用于"重试"前清残留）"""
    with pg.cursor() as cur:
        cur.execute("""DELETE FROM quiz_records WHERE question_id IN
                       (SELECT id FROM questions WHERE document_id=%s)""", (doc_id,))
        cur.execute("DELETE FROM questions WHERE document_id=%s", (doc_id,))
        cur.execute("""DELETE FROM plan_items WHERE plan_id IN
                       (SELECT id FROM study_plans WHERE document_id=%s)""", (doc_id,))
        cur.execute("DELETE FROM study_plans WHERE document_id=%s", (doc_id,))
        cur.execute("""DELETE FROM mastery_states WHERE knowledge_point_id IN
                       (SELECT id FROM knowledge_points WHERE document_id=%s)""", (doc_id,))
        cur.execute("""DELETE FROM diagnosis_reports WHERE weak_kp_id IN
                       (SELECT id FROM knowledge_points WHERE document_id=%s)""", (doc_id,))
        cur.execute("""DELETE FROM chunk_knowledge WHERE chunk_id IN
                       (SELECT id FROM chunks WHERE document_id=%s)""", (doc_id,))
        cur.execute("DELETE FROM knowledge_points WHERE document_id=%s", (doc_id,))
        cur.execute("DELETE FROM chunks WHERE document_id=%s", (doc_id,))
        if not keep_document:
            cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
        pg.commit()
    with deps.get_neo4j().session() as s:
        s.run("MATCH (n) WHERE n.doc_id = $doc DETACH DELETE n", doc=doc_id)
    try:
        deps.get_chroma().delete_collection(f"doc_{doc_id}")
    except Exception:
        pass


def _remove_file(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


@router.delete("/{doc_id}")
def delete_document(doc_id: int, pg=Depends(deps.get_pg)):
    """删除教材及其全部关联数据（计划/题目/答题记录/图谱/向量/文件）"""
    with pg.cursor() as cur:
        cur.execute("SELECT file_path FROM documents WHERE id=%s", (doc_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(404, "教材不存在")
    _purge_doc_data(pg, doc_id, keep_document=False)
    _remove_file(row[0])
    return {"deleted": doc_id}


@router.post("/{doc_id}/retry")
def retry_document(doc_id: int):
    """解析失败的 PDF 重新解析：清理残留 → 重置状态 → 重新跑流水线"""
    pg = deps.new_pg()
    try:
        with pg.cursor() as cur:
            cur.execute("""SELECT file_path FROM documents
                           WHERE id=%s AND source_type='pdf'""", (doc_id,))
            row = cur.fetchone()
        if row is None:
            raise HTTPException(404, "教材不存在或不是 PDF 类型")
        file_path = row[0]
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(400, "原始文件已丢失，请重新上传")
        _purge_doc_data(pg, doc_id, keep_document=True)
        with pg.cursor() as cur:
            cur.execute("""UPDATE documents SET parse_status='parsing',
                           error_message=NULL WHERE id=%s""", (doc_id,))
            pg.commit()
    finally:
        pg.close()
    payload = {"doc_id": doc_id, "file_path": file_path, "ocr_max_pages": None,
               "pg_factory": deps.new_pg, "neo": deps.get_neo4j(),
               "chroma": deps.get_chroma(), "embedder": get_embedder()}
    t = taskman.run_task("pdf_ingest", ingest_pdf, payload)
    return {"task_id": t.id, "doc_id": doc_id}


@router.post("/upload")
async def upload(file: UploadFile = File(...), user_id: int = Form(1),
                 ocr_max_pages: int | None = Form(None)):
    """上传教材 PDF → 异步解析入库（轮询 /api/tasks/{task_id} 拿进度）
    ocr_max_pages: 扫描版教材 OCR 页数上限（None=全本，约 1.5~2s/页）"""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")
    os.makedirs(settings.upload_dir, exist_ok=True)
    save_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.pdf")
    with open(save_path, "wb") as f:
        f.write(await file.read())

    pg = deps.new_pg()
    try:
        with pg.cursor() as cur:
            cur.execute("""INSERT INTO documents
                           (user_id, title, file_path, source_type, parse_status)
                           VALUES (%s,%s,%s,'pdf','parsing') RETURNING id""",
                        (user_id, file.filename, save_path))
            doc_id = cur.fetchone()[0]
            pg.commit()
    finally:
        pg.close()

    payload = {"doc_id": doc_id, "file_path": save_path, "ocr_max_pages": ocr_max_pages,
               "pg_factory": deps.new_pg, "neo": deps.get_neo4j(),
               "chroma": deps.get_chroma(), "embedder": get_embedder()}
    t = taskman.run_task("pdf_ingest", ingest_pdf, payload)
    return {"task_id": t.id, "doc_id": doc_id}
