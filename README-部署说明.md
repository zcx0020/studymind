# StudyMind —— 基于大模型的个性化 AI 学习助手

**部署与运行说明**（23 级人工智能 1 班 · 朱晨馨、游星宇）

## 一、项目简介

学生上传教材（或无教材直接输入主题）后，系统自动完成教材解析、知识图谱构建、学习计划生成与智能出题；答题后基于 Elo 掌握度模型实时评估，答错时通过 GraphRAG 诊断错误根因并**自动重排学习计划**（核心创新点），形成"答错—诊断—重排—再练—掌握"的学习闭环。

- 前端：Vue 3 + TypeScript + Tailwind（构建产物已随包附带，**目标电脑无需安装 Node.js**）
- 后端：Python 3 + FastAPI（启动后直接托管前端页面，浏览器访问一个端口即可）
- 数据库：PostgreSQL + Neo4j（Docker 容器，镜像文件已随包附带）
- AI：DeepSeek 大模型（需自行填写 API 密钥）+ 本地 BGE-M3 嵌入模型（已随包附带，离线可用）

## 二、运行环境要求

| 软件 | 要求 | 说明 |
| --- | --- | --- |
| 操作系统 | Windows 10/11（推荐） | Linux/macOS 亦可，用 `一键启动.sh` |
| Docker Desktop | 任意近期版本 | 运行 PostgreSQL 与 Neo4j 容器 |
| Python | 3.10 ~ 3.12 | 运行后端服务 |
| 网络 | 首次演示需联网 | 调用 DeepSeek 生成内容 |

## 三、快速启动（三步）

1. **配置密钥**：用记事本打开本目录下的 `.env` 文件，把第一行
   `DEEPSEEK_API_KEY=sk-在此填入你的密钥`
   中的占位文字替换为真实密钥（在 https://platform.deepseek.com 申请，支持支付宝充值，费用很低）。
2. **启动 Docker Desktop**（保持运行即可）。
3. **双击 `一键启动.bat`**（Linux/macOS 运行 `bash 一键启动.sh`）。

脚本会自动完成：导入数据库镜像 → 启动容器 → 安装 Python 依赖（仅首次）→ 启动服务并打开浏览器。看到浏览器弹出 StudyMind 首页即成功。

> 服务地址：**http://localhost:8000** （接口文档：http://localhost:8000/docs）

## 四、生成演示内容（首次运行必须做）

新环境里数据库是空的，运行演示脚本自动生成一套完整演示数据（调用 DeepSeek，约 2~3 分钟）：

```
python scripts\02_demo_no_pdf.py      # 无教材模式：生成知识库+图谱+学习计划
python scripts\03_demo_adaptive.py    # 自适应演示：答题→答错→诊断→计划重排
```

完成后刷新首页即可看到生成的知识库，直接演示答题闭环。

## 五、手动启动（不用一键脚本时的等效步骤）

```
docker load -i docker-images\postgres16.tar      # 仅首次
docker load -i docker-images\neo4j5.tar          # 仅首次
docker compose up -d                             # 启动数据库
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple   # 仅首次
cd backend
uvicorn app.main:app --port 8000                 # 启动服务
```

## 六、常见问题

| 现象 | 处理办法 |
| --- | --- |
| 8000 端口被占用 | 换端口启动：`uvicorn app.main:app --port 8001`，浏览器访问 http://localhost:8001 |
| 提示 Docker 未检测到 | 打开 Docker Desktop 等右下角鲸鱼图标变绿后再运行 |
| 上传 PDF 解析失败 | 扫描版教材需先安装 Tesseract OCR（https://github.com/UB-Mannheim/tesseract/wiki），并在安装时勾选中文语言包 chi_sim；电子版 PDF 不需要 |
| 出题/诊断长时间无结果 | 检查 .env 中密钥是否正确、网络是否可达 api.deepseek.com |
| 想清空数据重来 | 先 `docker compose down -v` 删容器和数据库，再按第四节重新生成 |
| 演示账号 | 系统内置演示用户（用户名 demo），无需注册登录 |

## 七、目录结构

```
studymind_可运行程序_v1.0/
├── 一键启动.bat / 一键启动.sh     启动脚本（推荐入口）
├── .env                           配置文件（API 密钥在此填写）
├── docker-compose.yml             数据库容器编排
├── requirements.txt               Python 依赖（已锁定实测版本）
├── docker-images/                 PostgreSQL / Neo4j 镜像文件（离线导入）
├── backend/                       后端源代码（FastAPI）
│   ├── models/bge-m3/             本地嵌入模型（离线可用）
│   └── kb/                        向量库数据目录（初始为空）
├── frontend/                      前端源代码 + dist/ 构建产物
├── scripts/                       数据库初始化脚本与演示脚本
└── docs/                          应用方案文档（含 LaTeX 源文件）
```

## 八、与申报书/方案文档的对应

- 应用方案文档：`docs/StudyMind应用方案.tex`（XeLaTeX 编译）
- 核心创新点演示：答题练习页答错任意一题 → 观察"学习诊断"自动生成 → 学习计划页可见任务被自动插入/调整
- 掌握度模型：每个知识点维护 Elo 分值 θ（初始 1500），答对/答错按 Elo 公式更新，连续答对 3 题或 θ≥1700 判定已掌握
