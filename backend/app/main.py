from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import traceback
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
import httpx  # 引入 httpx 来解决编码问题

load_dotenv()

# 1. 数据库连接
SQLALCHEMY_DATABASE_URL = "sqlite:///D:/my-plan/my-plan-main/backend/data/app.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 2. 核心修复：定制 httpx 客户端，强制不读环境代理，搞定 Windows 编码问题
custom_http_client = httpx.Client(trust_env=False)

llm = ChatOpenAI(
    model="glm-5.3-flash",
    temperature=0.7,
    api_key="cd5384e5ed3b4df4a0a9a8e9d6686111.6Y0Ioir054Dwdqxx",
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    http_client=custom_http_client  # 挂载我们定制的客户端
)

app = FastAPI(title="AI Plan Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str
    conversation_id: int = None  # 不传就自动新建一个会话


@app.get("/")
def read_root():
    return {"status": "ok", "message": "AI Plan Agent Backend is running"}


@app.get("/api/tasks")
def get_tasks(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT id, name, progress, target FROM tasks")).fetchall()
    return [{"id": r[0], "name": r[1], "progress": r[2], "target": r[3]} for r in result]


@app.get("/api/stats/week")
def get_week_stats(db: Session = Depends(get_db)):
    result = db.execute(text(
        "SELECT date, tasks_done, tasks_total, completion_pct FROM daily_logs ORDER BY date DESC LIMIT 7")).fetchall()
    return [{"date": r[0], "done": r[1], "total": r[2], "pct": r[3]} for r in result]


@app.post("/api/chat")
def chat_with_agent(request: ChatRequest, db: Session = Depends(get_db)):
    query = request.query
    conv_id = request.conversation_id
    try:
        # --- 第 1 步：搞定 conversation_id ---
        if conv_id is None:
            # 新建会话
            cursor = db.execute(text("INSERT INTO conversations (title) VALUES (:title)"),
                                {"title": query[:20]})
            db.commit()
            conv_id = cursor.lastrowid
        else:
            # 校验这个会话是不是真的存在
            check = db.execute(text("SELECT id FROM conversations WHERE id = :id"), {"id": conv_id}).fetchone()
            if not check:
                return {"error": f"会话 {conv_id} 不存在"}

        # --- 第 2 步：把用户说的话存进数据库 ---
        db.execute(text("INSERT INTO messages (conversation_id, role, content) VALUES (:cid, 'user', :content)"),
                   {"cid": conv_id, "content": query})
        db.commit()

        # --- 第 3 步：读最近 5 条历史消息（简单记忆） ---
        history = db.execute(
            text("SELECT role, content FROM messages WHERE conversation_id = :cid ORDER BY created_at DESC LIMIT 5"),
            {"cid": conv_id}
        ).fetchall()
        history.reverse()  # 从旧到新排列
        history_text = "\n".join([f"{r[0]}: {r[1]}" for r in history])

        # --- 第 4 步：读数据库任务数据（RAG 弹药） ---
        tasks = db.execute(text("SELECT name, progress, target FROM tasks")).fetchall()
        context = "\n".join([f"{t[0]}: {t[1]}/{t[2]}" for t in tasks])

        # --- 第 5 步：拼 Prompt，让 AI 结合历史和数据回答 ---
        prompt = f"""你是李泽宇的专属规划军师，名叫“小清”。
        你的目标：帮助李泽宇考上清华计算机研究生，并拿到大厂AI应用开发实习Offer。
        你的性格：直接、接地气、有洞察力，像兄弟一样聊天，不绕弯子，不说废话。该夸的时候夸，该骂的时候绝不嘴软。你懂他的所有规划、进度和情绪。

        这是李泽宇的真实任务数据：
        {context}

        这是你们最近的聊天记录：
        {history_text}

        用户刚刚说：{query}

        请以小清的身份，结合以上所有信息，给出简短、直接、可执行的规划建议。"""

        response = llm.invoke(prompt)
        answer = response.content

        # --- 第 6 步：把 AI 的回复也存进数据库 ---
        db.execute(text("INSERT INTO messages (conversation_id, role, content) VALUES (:cid, 'assistant', :content)"),
                   {"cid": conv_id, "content": answer})
        db.commit()

        return {
            "conversation_id": conv_id,
            "response": answer
        }

    except Exception as e:
        print("\n" + "=" * 50)
        print("CRITICAL ERROR IN /api/chat:")
        traceback.print_exc()
        print("=" * 50 + "\n")
        return {"error": str(e)}