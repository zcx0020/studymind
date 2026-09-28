"""parser/ingest.py —— PDF 入库流水线（API 后台任务入口）
上传 → 多策略解析(含 OCR 兜底) → 分块 → 向量化 → LLM 抽取 → 图谱入库 → 溯源映射
失败时: 把具体原因写入 documents.error_message，并以友好文案抛给前端
"""
import hashlib

from app.services import taskman
from app.services.parser.pdf import parse_pdf, chunk_document
from app.services.parser.extract import extract_from_chunks
from app.services.quiz.generate import pregenerate_questions


def ingest_pdf(t: taskman.TaskState, payload: dict) -> dict:
    doc_id, file_path = payload["doc_id"], payload["file_path"]
    ocr_max_pages = payload.get("ocr_max_pages")       # None = 扫描版全本 OCR
    pg = payload["pg_factory"]()
    neo, chroma, embedder = payload["neo"], payload["chroma"], payload["embedder"]
    try:
        # ① 解析（文本层多策略 → OCR 兜底），OCR 阶段带逐页进度
        t.stage = "解析 PDF（多策略）"
        t.progress = 5

        def progress_cb(n, total, stage):
            if total:
                t.stage = stage
                t.progress = 5 + int(75 * n / total)

        sections, page_count, meta = parse_pdf(
            file_path, ocr_max_pages=ocr_max_pages, progress_cb=progress_cb)
        if not sections:
            raise RuntimeError("未能从 PDF 中解析出任何章节内容")

        # ② chunk 入库 PG + 向量化入 Chroma
        t.stage = "文本分块 + 向量化"
        t.progress = max(t.progress, 40)
        parents, children = chunk_document(sections)
        parent_ids = {}
        with pg.cursor() as cur:
            for p in parents:
                cur.execute("""INSERT INTO chunks
                               (document_id, section_path, page, chunk_type, content, content_hash)
                               VALUES (%s,%s,%s,'text',%s,%s) RETURNING id""",
                            (doc_id, p["section_path"], p["page"], p["content"],
                             hashlib.md5(p["content"].encode()).hexdigest()))
                parent_ids[id(p)] = cur.fetchone()[0]
            child_rows = []
            for c in children:
                cur.execute("""INSERT INTO chunks
                               (document_id, section_path, page, chunk_type,
                                content, content_hash, parent_id)
                               VALUES (%s,%s,%s,'text',%s,%s,%s) RETURNING id""",
                            (doc_id, c["section_path"], c["page"], c["content"],
                             hashlib.md5(c["content"].encode()).hexdigest(),
                             parent_ids[id(c["parent"])]))
                child_rows.append((cur.fetchone()[0], c["content"]))
            pg.commit()
        col = chroma.get_or_create_collection(f"doc_{doc_id}")
        for i in range(0, len(child_rows), 50):            # 分批嵌入，超大教材友好
            batch = child_rows[i:i + 50]
            col.add(
                ids=[f"c{cid}" for cid, _ in batch],
                documents=[ct for _, ct in batch],
                embeddings=[embedder.encode(ct).tolist() for _, ct in batch],
                metadatas=[{"doc_id": doc_id, "kp_name": ""} for _ in batch],
            )

        # ③ LLM 抽取知识点（受控本体）
        t.stage = "LLM 抽取知识点与关系"
        t.progress = max(t.progress, 60)
        sk = extract_from_chunks(children)

        # ④ 知识点入库 + 溯源映射 + 状态更新
        t.stage = "写入知识图谱"
        t.progress = max(t.progress, 85)
        with pg.cursor() as cur:
            kp_ids = {}
            for e in sk.entities:
                cur.execute("""INSERT INTO knowledge_points
                               (document_id, name, kp_type, definition)
                               VALUES (%s,%s,%s,%s)
                               ON CONFLICT (document_id, name) DO UPDATE
                               SET definition = EXCLUDED.definition,
                                   kp_type = EXCLUDED.kp_type
                               RETURNING id""",
                            (doc_id, e.name, e.type, e.definition))
                kp_ids[e.name] = cur.fetchone()[0]
            for cid, ct in child_rows:
                for name, kp_id in kp_ids.items():
                    if name in ct:
                        cur.execute("""INSERT INTO chunk_knowledge
                                       (chunk_id, knowledge_point_id)
                                       VALUES (%s,%s) ON CONFLICT DO NOTHING""",
                                    (cid, kp_id))
            cur.execute("""UPDATE documents SET parse_status='done', page_count=%s,
                           error_message=NULL WHERE id=%s""", (page_count, doc_id))
            pg.commit()

        with neo.session() as s:
            for e in sk.entities:
                s.run(f"""MERGE (n:{e.type} {{name: $name}})
                          SET n.definition = $def, n.doc_id = $doc,
                              n.importance = $imp, n.difficulty = $dif,
                              n.source_type = 'pdf'""",
                      {"name": e.name, "def": e.definition, "doc": doc_id,
                       "imp": e.importance, "dif": e.difficulty})
            for r in sk.relations:
                s.run(f"""MATCH (a {{name: $src}}), (b {{name: $dst}})
                          MERGE (a)-[rel:{r.type}]->(b)
                          SET rel.source_type = 'pdf'""",
                      {"src": r.source, "dst": r.target})

        # ⑤ 预生成练习题：入库时顺带把题出好，"开始学习"秒开（失败不阻塞）
        t.stage = "预生成练习题"
        t.progress = max(t.progress, 90)
        pregen = {"kps": 0, "questions_ready": 0}
        try:
            pregen = pregenerate_questions(pg, chroma, embedder, doc_id,
                                           user_id=payload.get("user_id", 1))
        except Exception:
            pass

        return {"doc_id": doc_id, "pages": page_count, "sections": len(sections),
                "chunks": len(child_rows), "entities": len(sk.entities),
                "relations": len(sk.relations), "pregen": pregen, "meta": meta}
    except Exception as e:
        msg = str(e) or type(e).__name__
        with pg.cursor() as cur:
            cur.execute("""UPDATE documents SET parse_status='failed', error_message=%s
                           WHERE id=%s""", (msg[:500], doc_id))
            pg.commit()
        # 抛出带具体原因的友好错误（taskman 会把 error 传给前端展示）
        raise RuntimeError(msg) from e
    finally:
        pg.close()
