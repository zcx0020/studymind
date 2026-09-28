# StudyMind —— 基于大模型的个性化 AI 学习助手

《云计算与大数据实践》课程设计 · 朱晨馨、游星宇（23 人工智能 1 班）

核心能力：无教材也可用（LLM 直接生成知识体系），有教材更精准（上传资料后图谱个性化升级）。
学习闭环：知识库 → 知识图谱 → 学习计划 → 智能出题 → 答题 → 掌握度更新 →（M6）动态调整。

## 快速开始

```bash
# 1. 启动基础设施（PostgreSQL + Neo4j + Redis，首次启动自动建表并创建演示用户 id=1）
docker compose up -d

# 2. 安装 Python 依赖（首次约需几分钟，BGE-M3 模型较大）
pip install -r requirements.txt

# 3. 冒烟测试：验证 DeepSeek API 可用（零依赖，可先跑这个）
python3 scripts/01_smoke_test.py

# 4. 端到端演示：知识库 → 学习计划 → 今日题目 → 答题 → 掌握度更新
python3 scripts/02_demo_no_pdf.py

# 5. M6 创新点演示：答错 → GraphRAG 诊断 → 计划动态调整 → 难度自适应出题
python3 scripts/03_demo_adaptive.py

# 6. 启动 API 服务（前端对接入口）
cd backend && uvicorn app.main:app --reload --port 8000
#    接口文档: http://localhost:8000/docs
#    接口测试: python3 scripts/04_test_api.py

# 7. 启动前端（另开终端，/api 自动代理到 8000）
cd frontend && npm install && npm run dev
#    浏览器打开: http://localhost:5173
```

## 目录结构

```
studymind/
├── backend/app/
│   ├── config.py                 # 全局配置（读 .env，全项目密钥唯一入口）
│   ├── main.py                   # FastAPI 入口（uvicorn app.main:app）
│   ├── api/                      # REST 接口层（前端契约，/docs 自动文档）
│   └── services/
│       ├── llm.py                # LLM 工厂 + 嵌入模型单例（换模型只改 .env）
│       ├── taskman.py            # 轻量任务管理器（进度轮询）
│       ├── knowledge/            # 无教材知识库：主题 → 骨架 → 三库入库
│       ├── plan/                 # 学习计划：拓扑排序(算法) + LLM 文案(双引擎)
│       ├── quiz/                 # 答题闭环：今日出题 / 判分 / Elo 掌握度
│       ├── diagnostic/           # M6 动态调整引擎：诊断 → 计划重排 → 掌握跳过
│       ├── parser/               # PDF 解析管线（PyMuPDF，可换 MinerU）
│       └── rag/                  # 混合检索 / 自适应出题 / GraphRAG 诊断
├── frontend/                     # Vue3 + TS + Element Plus
│   └── src/
│       ├── views/                # 知识库 / 图谱(G6) / 计划 / 答题 / 看板(ECharts)
│       ├── api.ts                # 接口封装（含任务轮询）
│       └── colors.ts             # 可视化色板（已通过色盲安全校验）
├── scripts/
│   ├── init_db.sql               # 核心表结构（docker 首次启动自动执行）
│   ├── 01_smoke_test.py          # API 冒烟测试（零依赖）
│   ├── 02_demo_no_pdf.py         # 端到端演示（M1~M5 垂直切片）
│   ├── 03_demo_adaptive.py       # M6 演示（答错→诊断→动态调整闭环）
│   ├── 04_test_api.py            # REST API 端到端测试（零依赖）
│   └── 05_test_pdf.py            # PDF 上传解析全链路测试
├── docker-compose.yml
├── requirements.txt
├── .env / .env.example / .gitignore
└── README.md
```

## 安全须知

- `.env` 含真实 API 密钥，已被 `.gitignore` 排除，**禁止提交 git、禁止发群/截图外传**
- 业务代码一律通过 `app/config.py` 读取密钥，任何模块不得硬编码
- 若密钥意外泄露，到 DeepSeek 控制台立即重置并更新 `.env`

## 当前进度

- ✅ 无教材模式：主题 → 知识骨架 → PG/Neo4j/Chroma 三库入库
- ✅ 学习计划：拓扑排序 + 容量装箱 + LLM 文案（含环降级容错）
- ✅ 答题闭环：今日任务 → 出题（Elo 难度匹配+质量门禁）→ 判分 → Elo 落库
- ✅ M6 动态调整：答错 → GraphRAG 诊断 → 计划重排（插入补学/复习/提前）→ 难度自适应出题 → 掌握跳过
- ✅ FastAPI 接口层：知识库/图谱/计划/答题/掌握度/任务轮询，全部实测通过
- ✅ 前端：五个页面（知识库/图谱/计划/答题/看板），构建通过、代理联调通过
- ✅ PDF 解析增强：上传 → PyMuPDF 版面解析 → 分块 → 向量化 → LLM 抽取 → 图谱融合，实测通过
