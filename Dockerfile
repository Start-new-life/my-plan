# 使用轻量级 Python 3.10 作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端代码
COPY backend/ ./backend/

# 暴露 FastAPI 的 8000 端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]