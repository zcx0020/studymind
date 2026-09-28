"""knowledge/persist.py —— 骨架入库：PostgreSQL(业务) + Neo4j(图谱) + Chroma(向量)
写入顺序固定 PG → Neo4j → Chroma；幂等设计：按 name MERGE / 同名 collection 重建
"""
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

from .schemas import KnowledgeSkeleton


def persist_skeleton(user_id: int, subject: str, topic: str,
                     sk: KnowledgeSkeleton, pg_conn, neo4j_driver: GraphDatabase.driver,
                     embedder: SentenceTransformer, chroma_client) -> dict:
    """把骨架写进三库，返回统计信息。幂等：同名 MERGE，不产生重复。"""
    title = f"{subject} · {topic}"

    # ═══ ① PostgreSQL：documents + knowledge_points + chunks ═══
    with pg_conn.cursor() as cur:
        cur.execute("""INSERT INTO documents (user_id, title, source_type, parse_status)
                       VALUES (%s, %s, 'llm_generated', 'done') RETURNING id""",
                    (user_id, title))
        doc_id = cur.fetchone()[0]

        chunk_rows = []
        for e in sk.entities:
            cur.execute("""INSERT INTO knowledge_points
                           (document_id, name, kp_type, definition, section_path)
                           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                        (doc_id, e.name, e.type, e.definition, topic))
            kp_id = cur.fetchone()[0]
            # 知识点定义本身作为 chunk —— "无教材也能 RAG"的关键
            chunk_text = f"# {e.name}\n{e.definition}"
            cur.execute("""INSERT INTO chunks (document_id, chunk_type, content, section_path)
                           VALUES (%s, 'text', %s, %s) RETURNING id""",
                        (doc_id, chunk_text, topic))
            chunk_rows.append((cur.fetchone()[0], kp_id, e.name, chunk_text))
        pg_conn.commit()

    # ═══ ② Neo4j：实体节点 + 关系边（同名 MERGE，可与后续教材图谱自动衔接） ═══
    with neo4j_driver.session() as s:
        for e in sk.entities:
            s.run(f"""MERGE (n:{e.type} {{name: $name}})
                      SET n.definition = $def, n.doc_id = $doc,
                          n.importance = $imp, n.difficulty = $dif,
                          n.source_type = 'llm_generated'""",
                  {"name": e.name, "def": e.definition, "doc": doc_id,
                   "imp": e.importance, "dif": e.difficulty})
        for r in sk.relations:
            s.run(f"""MATCH (a {{name: $src}}), (b {{name: $dst}})
                      MERGE (a)-[rel:{r.type}]->(b)
                      SET rel.reason = $reason, rel.source_type = 'llm_generated'""",
                  src=r.source, dst=r.target, reason=r.reason)

    # ═══ ③ Chroma：知识点定义向量化入库（一本教材 = 一个 collection） ═══
    col = chroma_client.get_or_create_collection(f"doc_{doc_id}")
    col.add(
        ids=[f"c{row[0]}" for row in chunk_rows],
        documents=[row[3] for row in chunk_rows],
        embeddings=[embedder.encode(row[3]).tolist() for row in chunk_rows],
        metadatas=[{"doc_id": doc_id, "kp_id": row[1], "kp_name": row[2]}
                   for row in chunk_rows],
    )

    return {"doc_id": doc_id, "entities": len(sk.entities),
            "relations": len(sk.relations)}
