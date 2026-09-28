-- StudyMind 核心表结构（首次 docker compose up 时自动执行）
-- 注：课程版去掉了 pgvector 依赖（postgres:16 镜像不含该扩展），
--     题目去重改为应用层做（BGE-M3 向量，见 rag/adaptive_quiz.py）

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
    id           SERIAL PRIMARY KEY,
    user_id      INT REFERENCES users(id),
    title        VARCHAR(255) NOT NULL,
    course_name  VARCHAR(255),
    file_path    TEXT,
    source_type  VARCHAR(20) DEFAULT 'pdf'
                 CHECK (source_type IN ('pdf','paste','markdown','docx','image','llm_generated','seed')),
    parse_status VARCHAR(20) DEFAULT 'pending',
    page_count   INT,
    error_message TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id            SERIAL PRIMARY KEY,
    document_id   INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_path  TEXT,
    page          INT,
    chunk_type    VARCHAR(10) DEFAULT 'text'
                  CHECK (chunk_type IN ('text','formula','figure','table')),
    content       TEXT NOT NULL,
    content_hash  CHAR(32),
    parent_id     INT REFERENCES chunks(id),
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);

CREATE TABLE IF NOT EXISTS knowledge_points (
    id            SERIAL PRIMARY KEY,
    document_id   INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    name          VARCHAR(255) NOT NULL,
    kp_type       VARCHAR(20) CHECK (kp_type IN
                  ('Concept','Theorem','Formula','Algorithm','Example','ExamPoint')),
    definition    TEXT,
    section_path  TEXT,
    UNIQUE (document_id, name)
);

CREATE TABLE IF NOT EXISTS chunk_knowledge (
    chunk_id           INT REFERENCES chunks(id) ON DELETE CASCADE,
    knowledge_point_id INT REFERENCES knowledge_points(id) ON DELETE CASCADE,
    PRIMARY KEY (chunk_id, knowledge_point_id)
);

CREATE TABLE IF NOT EXISTS study_plans (
    id          SERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(id),
    document_id INT NOT NULL REFERENCES documents(id),
    goal        TEXT,
    total_days  INT,
    daily_limit INT DEFAULT 5,
    status      VARCHAR(20) DEFAULT 'active',
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plan_items (
    id                 SERIAL PRIMARY KEY,
    plan_id            INT NOT NULL REFERENCES study_plans(id) ON DELETE CASCADE,
    knowledge_point_id INT NOT NULL REFERENCES knowledge_points(id),
    day_index          INT,
    task_type          VARCHAR(10) DEFAULT 'learn'
                       CHECK (task_type IN ('learn','review','practice')),
    est_minutes        INT,
    status             VARCHAR(20) DEFAULT 'pending',
    created_by         VARCHAR(20) DEFAULT 'llm'   -- llm: 初始计划; adaptive: 动态调整插入
);

CREATE TABLE IF NOT EXISTS questions (
    id                SERIAL PRIMARY KEY,
    document_id       INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    knowledge_point_id INT NOT NULL REFERENCES knowledge_points(id),
    qtype             VARCHAR(20) CHECK (qtype IN
                      ('single_choice','multi_choice','true_false','fill_blank','short_answer')),
    stem              TEXT NOT NULL,
    options           JSONB,
    answer            TEXT NOT NULL,
    analysis          TEXT NOT NULL,
    difficulty        SMALLINT DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5),
    bloom             VARCHAR(10) DEFAULT '理解',
    source_chunk_id   INT REFERENCES chunks(id),
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quiz_records (
    id           SERIAL PRIMARY KEY,
    user_id      INT NOT NULL REFERENCES users(id),
    question_id  INT NOT NULL REFERENCES questions(id),
    is_correct   BOOLEAN NOT NULL,
    user_answer  TEXT,
    llm_feedback JSONB,
    duration_sec INT,
    elo_delta    REAL,          -- 本题对知识点的 Elo 变化量（会话总结聚合用）
    theta_before REAL,          -- 作答前的掌握度快照（会话总结聚合用）
    created_at   TIMESTAMPTZ DEFAULT now()
);
-- 老库升级：幂等补列（新库已含，直接跳过）
ALTER TABLE quiz_records ADD COLUMN IF NOT EXISTS elo_delta REAL;
ALTER TABLE quiz_records ADD COLUMN IF NOT EXISTS theta_before REAL;
CREATE INDEX IF NOT EXISTS idx_quiz_user_time ON quiz_records(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS mastery_states (
    id                SERIAL PRIMARY KEY,
    user_id           INT NOT NULL REFERENCES users(id),
    knowledge_point_id INT NOT NULL REFERENCES knowledge_points(id),
    elo_theta         REAL DEFAULT 1500.0,
    correct_count     INT DEFAULT 0,
    wrong_count       INT DEFAULT 0,
    streak            INT DEFAULT 0,
    last_review_at    TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, knowledge_point_id)
);

CREATE TABLE IF NOT EXISTS diagnosis_reports (
    id            SERIAL PRIMARY KEY,
    user_id       INT NOT NULL REFERENCES users(id),
    weak_kp_id    INT NOT NULL REFERENCES knowledge_points(id),
    root_cause        TEXT,
    remedy_path       JSONB,
    next_strategy     JSONB,
    confused_concepts JSONB,
    created_at        TIMESTAMPTZ DEFAULT now()
);

-- 演示用户（id=1），课程项目直接使用
INSERT INTO users (username, password_hash)
VALUES ('demo', 'demo')
ON CONFLICT (username) DO NOTHING;
