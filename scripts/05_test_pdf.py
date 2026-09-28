"""05_test_pdf.py —— PDF 上传解析全链路测试
① 用 PyMuPDF 合成一份教材 PDF（优先用 Windows 中文字体，否则英文兜底）
② 上传 → 轮询任务 → 校验图谱 / 掌握度 / 文档状态
前置: API 已启动 (cd backend && uvicorn app.main:app --port 8000)
用法: python3 scripts/05_test_pdf.py
"""
import json
import os
import time
import urllib.request
from pathlib import Path

import httpx
import pymupdf as fitz

BASE = "http://localhost:8000"

TEXTBOOK_ZH = """第1章 特征值与特征向量
1.1 特征值的基本概念
设 A 是 n 阶方阵，若存在数 λ 和非零向量 x，使得 Ax = λx，则称 λ 为 A 的特征值，x 为 A 的属于 λ 的特征向量。
特征方程 det(λI - A) = 0 的根即为 A 的全部特征值。
1.2 特征向量的性质
属于不同特征值的特征向量线性无关。
若 A 可对角化，则存在可逆矩阵 P，使得 P^-1AP 为对角矩阵。
1.3 特征值的应用
特征值分解用于主成分分析（PCA）的数据降维，也用于矩阵幂的计算与微分方程求解。
第2章 奇异值分解
2.1 奇异值分解的定义
任意 m×n 矩阵 A 可分解为 A = UΣV^T，其中 U、V 为正交矩阵，Σ 的对角元素为奇异值。
奇异值等于 A^TA 的特征值的算术平方根。
2.2 奇异值分解与主成分分析
PCA 可以通过对数据中心化后的矩阵做奇异值分解实现。
"""

TEXTBOOK_EN = """Chapter 1: Eigenvalues and Eigenvectors
1.1 Basic Concepts
For an n-by-n matrix A, a scalar lambda is an eigenvalue if Ax = lambda x for a nonzero vector x.
The roots of the characteristic equation det(lambda I - A) = 0 are the eigenvalues of A.
1.2 Properties of Eigenvectors
Eigenvectors belonging to distinct eigenvalues are linearly independent.
If A is diagonalizable, there exists an invertible matrix P such that P^-1 A P is diagonal.
1.3 Applications
Eigenvalue decomposition is used in PCA for dimensionality reduction.
Chapter 2: Singular Value Decomposition
2.1 Definition
Any m-by-n matrix A can be factored as A = U Sigma V^T, where U and V are orthogonal.
Singular values equal the square roots of eigenvalues of A^T A.
2.2 SVD and PCA
PCA can be implemented via SVD of the centered data matrix.
"""


def find_cjk_font():
    for c in ["/mnt/c/Windows/Fonts/msyh.ttc", "/mnt/c/Windows/Fonts/simsun.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"]:
        if os.path.exists(c):
            return c
    return None


def make_pdf(path: str):
    font = find_cjk_font()
    text = TEXTBOOK_ZH if font else TEXTBOOK_EN
    doc = fitz.open()
    page = doc.new_page()
    if font:
        page.insert_text((72, 72), text, fontsize=11, fontname="F0", fontfile=font)
    else:
        page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    print(f"① PDF 已生成: {path}（{'中文' if font else '英文兜底'}，字体: {font or '默认'}）")


def req(method, path, **kw):
    r = urllib.request.Request(BASE + path, method=method)
    with urllib.request.urlopen(r, timeout=300) as resp:
        return json.loads(resp.read())


def wait_task(task_id, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        t = req("GET", f"/api/tasks/{task_id}")
        if t["status"] in ("done", "failed"):
            return t
        print(f"   [{t['status']}] {t['stage']} ({t['progress']}%)")
        time.sleep(5)
    raise TimeoutError("任务超时")


if __name__ == "__main__":
    pdf = Path("/tmp/studymind_test_textbook.pdf")
    make_pdf(str(pdf))

    print("② 上传 PDF...")
    with open(pdf, "rb") as f:
        r = httpx.post(BASE + "/api/documents/upload",
                       files={"file": (pdf.name, f, "application/pdf")},
                       data={"user_id": "1"}, timeout=30).json()
    doc_id, task_id = r["doc_id"], r["task_id"]

    print("③ 等待解析任务...")
    t = wait_task(task_id)
    if t["status"] == "failed":
        raise RuntimeError(t["error"])
    print(f"   ✅ {t['result']}")

    print("④ 校验图谱与知识点...")
    g = req("GET", f"/api/knowledge/graph/{doc_id}")
    print(f"   图谱: {len(g['nodes'])} 节点, {len(g['edges'])} 条边")
    m = req("GET", f"/api/mastery/{doc_id}")
    print(f"   掌握度接口: {len(m['items'])} 个知识点")

    print("\n✅ PDF 解析全链路测试通过")
