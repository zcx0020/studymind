"""fetch_model.py —— 部署环境（Render 等）启动前拉取嵌入模型到持久化磁盘

本地开发/离线包不需要本脚本（模型已随包附带）。
用法: python scripts/fetch_model.py
- 目标目录取环境变量 BGE_M3_PATH（默认 /var/data/bge-m3）
- 已存在（config.json + model.safetensors 齐）则跳过，幂等
- 国内网络通过 HF_ENDPOINT=https://hf-mirror.com 走镜像（.env 已配置）
"""
import os
import sys
from pathlib import Path

target = Path(os.environ.get("BGE_M3_PATH", "/var/data/bge-m3"))
print(f"[fetch_model] 目标目录: {target}")

if (target / "config.json").exists() and (target / "model.safetensors").exists():
    print("[fetch_model] 模型已存在，跳过下载")
    sys.exit(0)

print("[fetch_model] 开始下载 BAAI/bge-m3（约 2.3GB，仅首次）...")
from huggingface_hub import snapshot_download  # noqa: E402 —— 依赖 sentence-transformers

target.mkdir(parents=True, exist_ok=True)
snapshot_download("BAAI/bge-m3", local_dir=str(target))
print("[fetch_model] 下载完成")
