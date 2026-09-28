# StudyMind 线上部署指南（Vercel 前端 + Render 后端）

> 目标架构：Vercel（Vue 静态站）→ HTTPS 调用 → Render（FastAPI）→ PostgreSQL（Render 托管）+ Neo4j（AuraDB 免费实例）+ 持久化磁盘（BGE-M3 模型与向量库）

## 一、部署前须知（重要限制）

| 事项 | 说明 |
| --- | --- |
| 免费额度 | Render **免费版没有持久化磁盘**（临时盘仅 512MB），装不下 2.3GB 的 BGE-M3 嵌入模型。本配置使用付费 Starter（$7/月）+ 磁盘（$0.25/GB/月）。课程演示结束后删服务即停止计费 |
| Neo4j | Render 不提供 Neo4j，改用 **Neo4j AuraDB Free**（免费，1 个实例，最多 200k 节点/400k 关系，课程项目够用） |
| 后台任务 | 出题/诊断走内存任务管理器 + 后台线程，进程重启任务会丢失（重试一次即可）；Render 免费/低档实例空闲 15 分钟会休眠，首次请求需等待数十秒唤醒，演示前先刷新一次页面 |
| 模型下载 | 首次部署启动时自动下载 BGE-M3 到磁盘（走 hf-mirror，约 2.3GB，10~20 分钟），之后重启秒起 |

## 二、后端部署到 Render

**方式 A：Blueprint 一键部署（推荐）**

1. 把整个项目推到 GitHub 仓库（`render.yaml` 在仓库根目录）。
2. Render 控制台 → New → **Blueprint** → 连接该仓库。
3. Render 自动创建：`studymind-api`（Python Web 服务）+ `studymind-db`（PostgreSQL）。
4. 到 `studymind-api` 的 **Environment** 页补齐三个敏感变量：
   - `DEEPSEEK_API_KEY`：你的 DeepSeek 密钥
   - `NEO4J_PASSWORD`：AuraDB 密码
   - `NEO4J_URI`：改成你实际创建的 AuraDB 地址（见第三节）
5. 等待首次构建（含模型下载），完成后访问 `https://studymind-api.onrender.com/api/health` 应返回 `{"status":"ok"}`。

**方式 B：手动创建（不用 Blueprint）**

1. New → **Web Service** → 连接仓库。
2. 设置：Runtime = Python 3；**Root Directory = `backend`**；Build Command = `pip install -r requirements.txt`；Start Command = `bash -c "python ../scripts/fetch_model.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT"`；Plan = Starter。
3. **Disks** 页添加磁盘：Mount Path = `/var/data`，大小 5GB。
4. New → **PostgreSQL** 创建数据库 `studymind-db`，在 Web 服务的 Environment 里添加 `POSTGRES_DSN`，值填数据库的 Internal Connection String。
5. 按第一节表格添加其余环境变量。

> 数据库建表无需手动操作：后端启动时检测到新库会自动执行 `scripts/init_db.sql`（幂等）。

## 三、创建 Neo4j AuraDB 免费实例（5 分钟）

1. 打开 https://console.neo4j.io → 注册/登录 → **Create Instance** → 选择 **AuraDB Free**。
2. 记住设置的密码（会存为 `NEO4J_PASSWORD`），创建后复制连接串（形如 `neo4j+s://xxxxxx.databases.neo4j.io`，填到 `NEO4J_URI`）。
3. 回到 Render 的 Environment 更新 `NEO4J_URI` / `NEO4J_PASSWORD`，保存后服务自动重新部署。

## 四、前端部署到 Vercel

1. Vercel 控制台 → **Add New → Project** → 导入同一个 GitHub 仓库。
2. **Root Directory 选 `frontend`**（Vercel 会读取 `frontend/vercel.json`，已内置 SPA 路由重写，History 模式刷新不会 404）。
3. 环境变量（Project → Settings → Environment Variables，**Production**）：
   `VITE_API_BASE` = `https://studymind-api.onrender.com/api`（改成你的 Render 域名）
4. Deploy。部署完成后把 Vercel 域名（如 `https://studymind-web.vercel.app`）填回 Render 的 `CORS_ORIGINS`（支持逗号分隔多个域名）。

## 五、环境变量清单（Render 后台配置）

| 变量 | 必填 | 值 / 来源 | 说明 |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | ✅ | 自备 | DeepSeek 密钥（platform.deepseek.com） |
| `DEEPSEEK_BASE_URL` | 默认 | `https://api.deepseek.com/v1` | 换 GLM/Qwen 改这里 |
| `DEEPSEEK_MODEL` | 默认 | `deepseek-chat` | 模型名 |
| `POSTGRES_DSN` | ✅ | Render DB 连接串 | Blueprint 自动注入；手动部署填 Internal Connection String |
| `NEO4J_URI` | ✅ | AuraDB 连接串 | `neo4j+s://xxx.databases.neo4j.io` |
| `NEO4J_USER` | 默认 | `neo4j` | AuraDB 用户名 |
| `NEO4J_PASSWORD` | ✅ | 自设 | AuraDB 密码 |
| `BGE_M3_PATH` | ✅ | `/var/data/bge-m3` | 嵌入模型目录（磁盘挂载点内） |
| `CHROMA_PATH` | ✅ | `/var/data/kb` | 向量库目录（磁盘挂载点内） |
| `HF_ENDPOINT` | 建议 | `https://hf-mirror.com` | 模型下载走国内镜像 |
| `CORS_ORIGINS` | ✅ | Vercel 域名 | 逗号分隔；本地默认 `*` |

**Vercel 前台配置**：`VITE_API_BASE`（构建期注入，指向 Render 后端，末尾带 `/api`）。

## 六、上线后生成演示数据

云端数据库是空的。在本机（或 Render Shell）执行演示脚本、指向云端库即可，**无需改动脚本**：

1. 把本地 `backend/.env` 的 `POSTGRES_DSN` / `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` 改成云端地址，`CHROMA_PATH` 留本地 `./kb`（向量在 Render 磁盘，但脚本也可只在云端建图谱+计划，首次云端出题会自动构建向量）。
2. 运行 `python3 scripts/02_demo_no_pdf.py`（约 2~3 分钟，内容写入云端 PostgreSQL + AuraDB）。
3. 打开 Vercel 前端即可看到知识库并开始答题演示。
