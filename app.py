
import os
import json
import uuid
import hmac
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, session
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text,
    Float, DateTime, select, insert, update
)
from sqlalchemy.exc import SQLAlchemyError
from openai import OpenAI

ROOT = Path(__file__).resolve().parent

def normalize_db_url(url: str) -> str:
    if not url:
        return f"sqlite:///{ROOT / 'falaorcamento.db'}"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url

DATABASE_URL = normalize_db_url(os.environ.get("DATABASE_URL", ""))
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "empresario@falaorcamento.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")

connect_args = {}
if DATABASE_URL.startswith("sqlite:"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
    connect_args=connect_args
)
meta = MetaData()

provider = Table(
    "provider", meta,
    Column("id", Integer, primary_key=True),
    Column("name", String(180), nullable=False, default=""),
    Column("phone", String(80), nullable=False, default=""),
    Column("doc", String(80), nullable=False, default="")
)

quotes = Table(
    "quotes", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("public_token", String(64), unique=True, nullable=False, index=True),
    Column("client", String(180), nullable=False),
    Column("items_json", Text, nullable=False),
    Column("notes", Text, nullable=False, default=""),
    Column("total", Float, nullable=False, default=0),
    Column("status", String(20), nullable=False, default="pending"),
    Column("provider_name", String(180), nullable=False, default=""),
    Column("provider_phone", String(80), nullable=False, default=""),
    Column("provider_doc", String(80), nullable=False, default=""),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False)
)

def utcnow():
    return datetime.now(timezone.utc)

def init_db():
    meta.create_all(engine)
    with engine.begin() as conn:
        row = conn.execute(select(provider).where(provider.c.id == 1)).mappings().first()
        if not row:
            conn.execute(insert(provider).values(id=1, name="", phone="", doc=""))

def quote_dict(row):
    r = dict(row)
    return {
        "id": f"{r['id']:04d}",
        "token": r["public_token"],
        "client": r["client"],
        "items": json.loads(r["items_json"]),
        "notes": r["notes"],
        "total": float(r["total"] or 0),
        "status": r["status"],
        "provider": {
            "name": r["provider_name"],
            "phone": r["provider_phone"],
            "doc": r["provider_doc"]
        },
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None
    }

def is_admin():
    return session.get("admin") is True

def require_admin():
    if not is_admin():
        return jsonify({"error": "Sessão administrativa necessária"}), 401
    return None

app = Flask(__name__, static_folder=None)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("RENDER", "").lower() == "true"
)

@app.after_request
def security_headers(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    return resp


@app.post("/api/interpret")
def interpret_budget():
    denied = require_admin()
    if denied:
        return denied
    if not OPENAI_API_KEY:
        return jsonify({"error":"IA não configurada","fallback":True}), 503

    body=request.get_json(silent=True) or {}
    text=str(body.get("text") or "").strip()
    if not text:
        return jsonify({"error":"Texto vazio"}),400

    schema={
      "type":"object",
      "properties":{
        "client":{"type":"string"},
        "items":{"type":"array","items":{"type":"object","properties":{
          "name":{"type":"string"},"qty":{"type":"number"},"unit":{"type":"number"}
        },"required":["name","qty","unit"],"additionalProperties":False}},
        "notes":{"type":"string"}
      },
      "required":["client","items","notes"],
      "additionalProperties":False
    }
    instructions="""Você interpreta falas informais brasileiras de profissionais criando orçamentos.
Extraia somente informações realmente ditas. Não invente preços, quantidades ou nomes.
Identifique o cliente mesmo em construções como 'fui na casa de João', 'fiz para Maria', 'cliente Gabriel'.
Transforme ações em descrições curtas profissionais: 'troquei a porta dele' -> 'Troca de porta'.
Quando houver '2 telhas 10 reais cada', qty=2 e unit=10.
Quando só houver um preço para um serviço, qty=1.
Não inclua contexto irrelevante na descrição. Notes deve conter apenas condições/observações úteis explicitamente ditas.
Se o cliente não puder ser inferido com segurança, use 'Cliente'."""
    try:
        client=OpenAI(api_key=OPENAI_API_KEY)
        response=client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=text,
            text={"format":{"type":"json_schema","name":"budget","strict":True,"schema":schema}}
        )
        parsed=json.loads(response.output_text)
        clean=[]
        for it in parsed.get("items",[])[:100]:
            q=float(it.get("qty") or 1)
            u=float(it.get("unit") or 0)
            clean.append({"name":str(it.get("name") or "Serviço")[:250],
                          "qty":q,"unit":u,"value":round(q*u,2)})
        parsed["items"]=clean
        parsed["source"]="ai"
        return jsonify(parsed)
    except Exception as e:
        print("Erro IA:",repr(e))
        return jsonify({"error":"Não foi possível interpretar com IA","fallback":True}),502

@app.get("/api/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(select(provider.c.id).limit(1))
        return jsonify({"ok": True, "database": "online", "version": "0.7"})
    except Exception as e:
        return jsonify({"ok": False, "database": "offline", "error": str(e)}), 503

@app.get("/api/session")
def api_session():
    return jsonify({"authenticated": is_admin()})

@app.post("/api/login")
def login():
    body = request.get_json(silent=True) or {}
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))

    email_ok = hmac.compare_digest(email, ADMIN_EMAIL.strip().lower())
    password_ok = hmac.compare_digest(password, ADMIN_PASSWORD)

    if email_ok and password_ok:
        session["admin"] = True
        session["admin_email"] = email
        return jsonify({"ok": True, "email": email})

    return jsonify({"error": "E-mail ou senha incorretos"}), 401

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.get("/api/provider")
def get_provider():
    denied = require_admin()
    if denied:
        return denied
    with engine.connect() as conn:
        row = conn.execute(select(provider).where(provider.c.id == 1)).mappings().first()
    return jsonify(dict(row))

@app.post("/api/provider")
def save_provider():
    denied = require_admin()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    values = {
        "name": str(body.get("name", "")).strip()[:180],
        "phone": str(body.get("phone", "")).strip()[:80],
        "doc": str(body.get("doc", "")).strip()[:80],
    }
    with engine.begin() as conn:
        conn.execute(update(provider).where(provider.c.id == 1).values(**values))
    return jsonify({"ok": True, **values})

@app.get("/api/quotes")
def list_quotes():
    denied = require_admin()
    if denied:
        return denied
    with engine.connect() as conn:
        rows = conn.execute(
            select(quotes).order_by(quotes.c.id.desc()).limit(100)
        ).mappings().all()
    return jsonify([quote_dict(r) for r in rows])

def get_quote_by_token(token):
    with engine.connect() as conn:
        return conn.execute(
            select(quotes).where(quotes.c.public_token == token)
        ).mappings().first()

@app.get("/api/quotes/<token>")
def get_quote(token):
    # O token aleatório funciona como a chave pública do orçamento.
    row = get_quote_by_token(token)
    if not row:
        return jsonify({"error": "Orçamento não encontrado"}), 404
    return jsonify(quote_dict(row))

@app.post("/api/quotes")
def create_quote():
    denied = require_admin()
    if denied:
        return denied

    body = request.get_json(silent=True) or {}
    client = str(body.get("client") or "Cliente").strip()[:180]
    incoming_items = body.get("items") or []
    notes = str(body.get("notes") or "")[:4000]

    clean_items = []
    total = 0.0
    for raw in incoming_items[:100]:
        try:
            qty = float(raw.get("qty", 1) or 1)
            unit = float(raw.get("unit", 0) or 0)
        except (ValueError, TypeError):
            qty, unit = 1.0, 0.0

        qty = max(0.01, min(qty, 100000))
        unit = max(0.0, min(unit, 100000000))
        name = str(raw.get("name") or "Serviço").strip()[:250]
        item_total = round(qty * unit, 2)
        clean_items.append({
            "name": name,
            "qty": qty,
            "unit": unit,
            "value": item_total
        })
        total += item_total

    with engine.begin() as conn:
        pr = conn.execute(select(provider).where(provider.c.id == 1)).mappings().first()
        token = uuid.uuid4().hex
        now = utcnow()
        result = conn.execute(insert(quotes).values(
            public_token=token,
            client=client,
            items_json=json.dumps(clean_items, ensure_ascii=False),
            notes=notes,
            total=round(total, 2),
            status="pending",
            provider_name=pr["name"],
            provider_phone=pr["phone"],
            provider_doc=pr["doc"],
            created_at=now,
            updated_at=now
        ))
        qid = result.inserted_primary_key[0]
        row = conn.execute(select(quotes).where(quotes.c.id == qid)).mappings().first()

    return jsonify(quote_dict(row)), 201

@app.patch("/api/quotes/<token>")
def update_quote_status(token):
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if status not in {"pending", "accepted", "rejected"}:
        return jsonify({"error": "Status inválido"}), 400

    with engine.begin() as conn:
        row = conn.execute(
            select(quotes).where(quotes.c.public_token == token)
        ).mappings().first()
        if not row:
            return jsonify({"error": "Orçamento não encontrado"}), 404

        conn.execute(
            update(quotes)
            .where(quotes.c.public_token == token)
            .values(status=status, updated_at=utcnow())
        )
        updated_row = conn.execute(
            select(quotes).where(quotes.c.public_token == token)
        ).mappings().first()

    return jsonify(quote_dict(updated_row))

@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")

@app.get("/<path:path>")
def static_files(path):
    file_path = ROOT / path
    if file_path.is_file():
        return send_from_directory(ROOT, path)
    return send_from_directory(ROOT, "index.html")

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    if ADMIN_PASSWORD == "admin":
        print("\nATENÇÃO: execução local usando senha administrativa padrão: admin")
    print(f"FalaOrçamento v0.7: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
