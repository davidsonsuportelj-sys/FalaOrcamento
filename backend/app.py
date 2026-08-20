
import os
import json
import uuid
import hmac
import re
import shutil
import time
import urllib.request
import urllib.error
import smtplib
import secrets
import hashlib
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, session, send_file, g, redirect
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as PDFTable, TableStyle, KeepTogether

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text,
    Float, DateTime, Boolean, ForeignKey, select, insert, update, text, inspect, func
)
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from markupsafe import escape

try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
except Exception:
    google_id_token = None
    google_requests = None

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Migração automática da estrutura antiga: preserva o banco existente.
LEGACY_DB = PROJECT_ROOT / "falaorcamento.db"
CURRENT_DB = DATA_DIR / "falaorcamento.db"
if not CURRENT_DB.exists() and LEGACY_DB.exists():
    try:
        shutil.move(str(LEGACY_DB), str(CURRENT_DB))
    except Exception:
        pass

def normalize_db_url(url: str) -> str:
    if not url:
        return f"sqlite:///{CURRENT_DB}"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url

DATABASE_URL = normalize_db_url(os.environ.get("DATABASE_URL", ""))
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "empresario@falaorcamento.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
APP_ENV = os.environ.get("APP_ENV", "development").lower()
PUBLIC_APP_URL = os.environ.get("PUBLIC_APP_URL", "https://falaorcamento.davidson-suportelj.workers.dev").rstrip("/")
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER or "no-reply@falaorcamento.app").strip()
BOOTSTRAP_ADMIN = os.environ.get(
    "BOOTSTRAP_ADMIN",
    "true" if APP_ENV == "development" else "false"
).lower() in {"1","true","yes","on"}
SESSION_COOKIE_SECURE_CONFIG = os.environ.get(
    "SESSION_COOKIE_SECURE",
    "true" if APP_ENV == "production" else "false"
).lower() in {"1","true","yes","on"}
MOBILE_TOKEN_DAYS = max(1, min(int(os.environ.get("MOBILE_TOKEN_DAYS", "30")), 365))
MOBILE_ALLOWED_ORIGINS = {
    x.strip() for x in os.environ.get("MOBILE_ALLOWED_ORIGINS", "").split(",") if x.strip()
}

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

accounts = Table(
    "accounts", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(180), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False)
)

users = Table(
    "users", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer, ForeignKey("accounts.id"), nullable=False, index=True),
    Column("name", String(180), nullable=False, default=""),
    Column("email", String(180), nullable=False, unique=True, index=True),
    Column("password_hash", String(300), nullable=False, default=""),
    Column("google_sub", String(255), nullable=False, default="", index=True),
    Column("auth_provider", String(30), nullable=False, default="email"),
    Column("email_verified", Boolean, nullable=False, default=False),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_login_at", DateTime(timezone=True), nullable=True)
)

password_reset_tokens = Table(
    "password_reset_tokens", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False, index=True),
    Column("token", String(96), nullable=False, unique=True, index=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("used", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False)
)

api_tokens = Table(
    "api_tokens", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False, index=True),
    Column("token_hash", String(64), nullable=False, unique=True, index=True),
    Column("label", String(80), nullable=False, default="mobile"),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_used_at", DateTime(timezone=True), nullable=True)
)


provider = Table(
    "provider", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer, ForeignKey("accounts.id"), nullable=True, index=True),
    Column("name", String(180), nullable=False, default=""),
    Column("phone", String(80), nullable=False, default=""),
    Column("doc", String(80), nullable=False, default="")
)

quotes = Table(
    "quotes", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer, ForeignKey("accounts.id"), nullable=True, index=True),
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
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("responded_at", DateTime(timezone=True), nullable=True)
)

interpretation_logs = Table(
    "interpretation_logs", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer, ForeignKey("accounts.id"), nullable=True, index=True),
    Column("original_text", Text, nullable=False),
    Column("result_json", Text, nullable=False),
    Column("source", String(40), nullable=False, default=""),
    Column("model", String(120), nullable=False, default=""),
    Column("elapsed_ms", Integer, nullable=False, default=0),
    Column("corrected_json", Text, nullable=False, default=""),
    Column("created_at", DateTime(timezone=True), nullable=False)
)

clients = Table(
    "clients", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer, ForeignKey("accounts.id"), nullable=True, index=True),
    Column("name", String(180), nullable=False),
    Column("phone", String(80), nullable=False, default=""),
    Column("doc", String(80), nullable=False, default=""),
    Column("email", String(180), nullable=False, default=""),
    Column("notes", Text, nullable=False, default=""),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False)
)

def utcnow():
    return datetime.now(timezone.utc)

def _ensure_legacy_columns():
    """Adiciona account_id em bancos antigos sem apagar dados."""
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    for table_name in ("provider", "quotes", "clients", "interpretation_logs"):
        if table_name not in existing:
            continue
        cols = {c["name"] for c in insp.get_columns(table_name)}
        if "account_id" not in cols:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN account_id INTEGER"))
        if table_name == "quotes" and "responded_at" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE quotes ADD COLUMN responded_at TIMESTAMP"))


def _create_account(conn, name):
    result = conn.execute(insert(accounts).values(name=(name or "Minha empresa")[:180], created_at=utcnow()))
    account_id = result.inserted_primary_key[0]
    conn.execute(insert(provider).values(account_id=account_id, name=(name or "Minha empresa")[:180], phone="", doc=""))
    return account_id


def init_db():
    meta.create_all(engine)
    _ensure_legacy_columns()
    meta.create_all(engine)
    with engine.begin() as conn:
        first_user = conn.execute(select(users.c.id).limit(1)).first()
        if not first_user and BOOTSTRAP_ADMIN:
            account_id = _create_account(conn, "Minha empresa")
            conn.execute(insert(users).values(
                account_id=account_id,
                name="Empresário",
                email=ADMIN_EMAIL.strip().lower(),
                password_hash=generate_password_hash(ADMIN_PASSWORD),
                google_sub="",
                auth_provider="email",
                email_verified=True,
                is_active=True,
                created_at=utcnow(),
                last_login_at=None
            ))
            for table_name, table_obj in (("provider",provider),("quotes",quotes),("clients",clients),("interpretation_logs",interpretation_logs)):
                try:
                    conn.execute(update(table_obj).where(table_obj.c.account_id.is_(None)).values(account_id=account_id))
                except Exception:
                    pass


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
        "provider": {"name": r["provider_name"], "phone": r["provider_phone"], "doc": r["provider_doc"]},
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        "responseAt": _aware_utc(r.get("responded_at")).isoformat() if r.get("responded_at") else None,
        "publicUrl": f"{PUBLIC_APP_URL}/q/{r['public_token']}"
    }


def _send_reset_email(to_email, token):
    if not SMTP_HOST:
        return False
    reset_url = f"{PUBLIC_APP_URL}/?reset={token}"
    msg = EmailMessage()
    msg["Subject"] = "Redefina sua senha do FalaOrçamento"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(
        "Recebemos uma solicitação para redefinir sua senha do FalaOrçamento.\n\n"
        f"Abra este link (válido por 30 minutos):\n{reset_url}\n\n"
        "Se você não solicitou a alteração, ignore este e-mail."
    )
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
        smtp.starttls()
        if SMTP_USER:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)
    return True


def _aware_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _bearer_identity():
    cached = getattr(g, "_bearer_identity", None)
    if cached is not None:
        return cached or None

    auth = str(request.headers.get("Authorization") or "")
    if not auth.lower().startswith("bearer "):
        g._bearer_identity = False
        return None

    raw = auth[7:].strip()
    if len(raw) < 32:
        g._bearer_identity = False
        return None

    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    with engine.begin() as conn:
        row = conn.execute(
            select(
                api_tokens.c.id.label("token_id"),
                api_tokens.c.user_id,
                api_tokens.c.expires_at,
                api_tokens.c.revoked,
                users.c.account_id,
                users.c.email,
                users.c.name,
                users.c.is_active
            )
            .join(users, users.c.id == api_tokens.c.user_id)
            .where(api_tokens.c.token_hash == token_hash)
        ).mappings().first()

        if (
            not row
            or row["revoked"]
            or not row["is_active"]
            or _aware_utc(row["expires_at"]) <= utcnow()
        ):
            g._bearer_identity = False
            return None

        conn.execute(
            update(api_tokens)
            .where(api_tokens.c.id == row["token_id"])
            .values(last_used_at=utcnow())
        )

    g._bearer_identity = dict(row)
    return g._bearer_identity


def current_user_id():
    if session.get("user_id"):
        return session.get("user_id")
    identity = _bearer_identity()
    return identity["user_id"] if identity else None


def current_account_id():
    if session.get("account_id"):
        return session.get("account_id")
    identity = _bearer_identity()
    return identity["account_id"] if identity else None


def current_api_token_id():
    identity = _bearer_identity()
    return identity["token_id"] if identity else None


def is_admin():
    return bool(current_user_id() and current_account_id())


def require_admin():
    if not is_admin():
        return jsonify({"error": "Faça login para continuar"}), 401
    return None


def _session_user_payload(conn, user_id):
    row = conn.execute(
        select(users.c.id, users.c.account_id, users.c.name, users.c.email, users.c.auth_provider, accounts.c.name.label("account_name"))
        .join(accounts, accounts.c.id == users.c.account_id)
        .where(users.c.id == user_id)
    ).mappings().first()
    return dict(row) if row else None


def _start_session(user_row, remember=False):
    session.clear()
    session["user_id"] = int(user_row["id"])
    session["account_id"] = int(user_row["account_id"])
    session["user_email"] = user_row["email"]
    session["user_name"] = user_row.get("name") or ""
    session.permanent = bool(remember)

app = Flask(__name__, static_folder=None)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE_CONFIG,
    PERMANENT_SESSION_LIFETIME=timedelta(days=30)
)

@app.after_request
def security_headers(resp):
    if request.path.startswith("/api/") or request.path.startswith("/q/"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        resp.headers["Pragma"] = "no-cache"

    origin = str(request.headers.get("Origin") or "")
    if origin and origin in MOBILE_ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        resp.headers["Vary"] = "Origin"

    return resp



def _semantic_guardrails(original_text, parsed):
    """Correções conservadoras para erros recorrentes do modelo pequeno local."""
    text=" ".join(str(original_text or "").lower().split())
    items=parsed.get("items") or []

    # 1) "objeto de lugar" é movimento/reposicionamento, não substituição.
    # Aplicamos apenas quando o próprio objeto do item aparece próximo de "de lugar" na fala.
    if " de lugar" in text or "outro lugar" in text:
        for item in items:
            name=str(item.get("name") or "")
            low=name.lower()
            # Extract likely object after common action prefixes.
            obj=re.sub(
                r"^(troca|substituição|substituicao|mudança|mudanca|reposicionamento|movimentação|movimentacao)\s+de\s+",
                "", low
            ).strip()
            if not obj:
                continue
            # Match "fogão de lugar", "fogao de lugar", etc. by significant words.
            significant=[w for w in re.findall(r"[a-záàâãéêíóôõúç0-9]+",obj) if len(w)>2]
            if significant and all(w in text for w in significant):
                # Require explicit movement phrase near at least the last significant noun.
                noun=significant[-1]
                movement_patterns=[
                    rf"{re.escape(noun)}\s+de\s+lugar",
                    rf"{re.escape(noun)}\s+(?:para|pra)\s+(?:um\s+)?outro\s+lugar",
                    rf"(?:mudei|mover|movi|reposicionei|reposicionar)\s+(?:o|a|os|as)?\s*{re.escape(noun)}"
                ]
                if any(re.search(p,text) for p in movement_patterns):
                    item["name"]="Reposicionamento de " + obj

    # 2) "R$ 100 de cada" / "100 reais cada serviço": same unit for all cited service items.
    each_patterns=[
        r"(?:r\$\s*)?(\d+(?:[.,]\d{1,2})?)\s*(?:reais?)?\s+de\s+cada\b",
        r"(?:r\$\s*)?(\d+(?:[.,]\d{1,2})?)\s*(?:reais?)?\s+(?:para\s+)?cada\s+(?:um|serviço|servico)\b"
    ]
    each_value=None
    for pat in each_patterns:
        m=re.search(pat,text)
        if m:
            try:
                each_value=float(m.group(1).replace(",","."))
            except Exception:
                each_value=None
            break
    if each_value is not None and len(items)>=2:
        for item in items:
            item["unit"]=each_value
            try:
                q=float(item.get("qty") or 1)
            except Exception:
                q=1.0
            item["value"]=round(q*each_value,2)

    parsed["items"]=items
    return parsed


@app.get("/api/system-health")
def system_health():
    result={"backend":True,"database":False,"ai":False,"ai_model":OLLAMA_MODEL,"errors":[]}
    try:
        with engine.connect() as conn:
            conn.execute(select(provider.c.id).limit(1))
        result["database"]=True
    except Exception:
        result["errors"].append("Banco de dados indisponível")
    try:
        req=urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags",headers={"Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=2.5) as resp:
            payload=json.loads(resp.read().decode("utf-8"))
        models=[str(x.get("name") or "") for x in payload.get("models",[])]
        result["ai"]=any(m==OLLAMA_MODEL or m.startswith(OLLAMA_MODEL+":") or OLLAMA_MODEL.startswith(m+":") for m in models)
    except Exception:
        result["errors"].append("IA local indisponível")
    result["ok"]=result["backend"] and result["database"]
    return jsonify(result)

@app.get("/api/ai-health")
def ai_health():
    """Verifica se o Ollama local está acessível e se o modelo está disponível."""
    try:
        req = urllib.request.Request(
            OLLAMA_BASE_URL + "/api/tags",
            headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        names = [m.get("name", "") for m in payload.get("models", [])]
        model_ok = any(
            n == OLLAMA_MODEL or n.startswith(OLLAMA_MODEL + ":")
            for n in names
        )
        return jsonify({
            "ok": True,
            "ollama": "online",
            "model": OLLAMA_MODEL,
            "modelAvailable": model_ok,
            "models": names
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "ollama": "offline",
            "model": OLLAMA_MODEL,
            "error": str(e)
        }), 503

@app.post("/api/interpret")
def interpret_budget():
    started_at = time.perf_counter()
    denied = require_admin()
    if denied:
        return denied

    body = request.get_json(silent=True) or {}
    text = str(body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Texto vazio"}), 400

    schema = {
        "type": "object",
        "properties": {
            "client": {"type": "string"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "qty": {"type": "number"},
                        "unit": {"type": "number"}
                    },
                    "required": ["name", "qty", "unit"],
                    "additionalProperties": False
                }
            },
            "notes": {"type": "string"}
        },
        "required": ["client", "items", "notes"],
        "additionalProperties": False
    }

    system_prompt = """Você é o interpretador de orçamentos do FalaOrçamento.
Sua única função é transformar uma fala informal de um prestador brasileiro em dados de orçamento.

REGRAS:
1. Extraia somente informações que realmente aparecem na fala. Nunca invente valores.
2. Descubra o cliente pelo contexto:
   - "fui na casa de João" -> cliente João
   - "fiz para Maria" -> cliente Maria
   - "cliente Gabriel" -> cliente Gabriel
   - "atendi o Carlos" -> cliente Carlos
3. Retire pronomes e contexto inútil da descrição:
   - "troquei a porta dele" -> "Troca de porta"
   - "fui lá e troquei a calha" -> "Troca de calha"

4. NÃO espalhe um verbo para ações diferentes só porque aparecem na mesma frase.
   Interprete cada objeto de acordo com o complemento que vem junto dele.
   - "troquei a porta, troquei a janela e o fogão de lugar"
     -> "Troca de porta"
     -> "Troca de janela"
     -> "Reposicionamento de fogão"
   - "mudei a geladeira de lugar" -> "Reposicionamento de geladeira"
   - "coloquei o armário em outro lugar" -> "Reposicionamento de armário"
   Quando houver "de lugar", "para outro lugar", "mudei", "reposicionei" ou sentido equivalente,
   NÃO use "Troca de <objeto>" a menos que a fala diga claramente que o objeto foi substituído.

5. Quantidade e unitário:
   - "2 telhas 10 reais cada" -> qty 2, unit 10
   - "troca da porta 50 reais" -> qty 1, unit 50
   - "cobrei 100 de cada" depois de citar vários serviços
     -> atribua unit 100 a CADA serviço citado imediatamente antes.
   - "50 cada um" / "50 para cada serviço" segue a mesma regra.

6. Material, mão de obra e serviço podem ser itens separados quando tiverem preço próprio.

7. Se uma quantidade não for dita, use 1.

8. Se o cliente realmente não puder ser identificado, use "Cliente".

9. Em notes coloque somente condições explicitamente faladas, como pagamento, validade ou observações.

10. Preserve o sentido exato da ação. Não transforme "mover", "reposicionar", "instalar", "limpar",
    "pintar", "regular" ou "consertar" em "trocar".

11. Responda estritamente conforme o JSON Schema.

EXEMPLOS:
Fala: "Fui na casa de João troquei a porta dele 50 reais"
Resultado: cliente João; item "Troca de porta", qty 1, unit 50.

Fala: "troquei 2 telhas 10 reais cada, troquei a calha 50, material 50, serviço 150, cliente Gabriel"
Resultado: cliente Gabriel; "Troca de telhas" qty 2 unit 10; "Troca de calha" qty 1 unit 50; "Material" qty 1 unit 50; "Serviço" qty 1 unit 150.

Fala: "fui na casa de Gabriel troquei a porta troquei a janela e o fogão de lugar cobrei 100 reais de cada"
Resultado: cliente Gabriel; "Troca de porta" qty 1 unit 100; "Troca de janela" qty 1 unit 100; "Reposicionamento de fogão" qty 1 unit 100.
"""

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "format": schema,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_ctx": 2048
        },
        "keep_alive": "10m"
    }

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            OLLAMA_BASE_URL + "/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        content = result.get("message", {}).get("content", "")
        parsed = json.loads(content)
        parsed = _semantic_guardrails(text, parsed)

        clean_items = []
        for item in parsed.get("items", [])[:100]:
            try:
                qty = float(item.get("qty", 1) or 1)
                unit = float(item.get("unit", 0) or 0)
            except (ValueError, TypeError):
                qty, unit = 1.0, 0.0

            qty = max(0.01, qty)
            unit = max(0.0, unit)
            clean_items.append({
                "name": str(item.get("name") or "Serviço").strip()[:250],
                "qty": qty,
                "unit": unit,
                "value": round(qty * unit, 2)
            })

        if not clean_items:
            return jsonify({
                "error": "A IA não encontrou itens no orçamento",
                "fallback": True
            }), 422

        response_data = {
            "client": str(parsed.get("client") or "Cliente").strip()[:180],
            "items": clean_items,
            "notes": str(parsed.get("notes") or "").strip()[:4000],
            "source": "ollama",
            "model": OLLAMA_MODEL
        }
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        try:
            with engine.begin() as conn:
                result = conn.execute(insert(interpretation_logs).values(
                    account_id=current_account_id(),
                    original_text=text,
                    result_json=json.dumps(response_data, ensure_ascii=False),
                    source="ollama",
                    model=OLLAMA_MODEL,
                    elapsed_ms=elapsed_ms,
                    corrected_json="",
                    created_at=utcnow()
                ))
                response_data["interpretation_id"] = result.inserted_primary_key[0]
        except Exception as log_error:
            print("Falha ao registrar interpretação:", repr(log_error))
        response_data["elapsed_ms"] = elapsed_ms
        return jsonify(response_data)

    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        print("Erro HTTP Ollama:", detail)
        return jsonify({
            "error": "O Ollama respondeu com erro",
            "fallback": True
        }), 502
    except urllib.error.URLError as e:
        print("Ollama indisponível:", repr(e))
        return jsonify({
            "error": "Ollama não está acessível. Verifique se está iniciado.",
            "fallback": True
        }), 503
    except Exception as e:
        print("Erro na IA local:", repr(e))
        return jsonify({
            "error": "Não foi possível interpretar com a IA local",
            "fallback": True
        }), 502


@app.get("/api/clients")
def list_clients():
    denied = require_admin()
    if denied:
        return denied
    with engine.connect() as conn:
        rows = conn.execute(select(clients).where(clients.c.account_id==current_account_id()).order_by(clients.c.name.asc())).mappings().all()
    return jsonify([{
        "id":r["id"],"name":r["name"],"phone":r["phone"],"doc":r["doc"],
        "email":r["email"],"notes":r["notes"],
        "created_at":r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at":r["updated_at"].isoformat() if r["updated_at"] else None
    } for r in rows])

@app.post("/api/clients")
def create_client():
    denied = require_admin()
    if denied:
        return denied
    body=request.get_json(silent=True) or {}
    name=str(body.get("name") or "").strip()
    if not name:
        return jsonify({"error":"Informe o nome do cliente"}),400
    values={
        "account_id":current_account_id(),
        "name":name[:180],
        "phone":str(body.get("phone") or "").strip()[:80],
        "doc":str(body.get("doc") or "").strip()[:80],
        "email":str(body.get("email") or "").strip()[:180],
        "notes":str(body.get("notes") or "").strip()[:4000],
        "created_at":utcnow(),
        "updated_at":utcnow()
    }
    with engine.begin() as conn:
        result=conn.execute(insert(clients).values(**values))
        cid=result.inserted_primary_key[0]
        row=conn.execute(select(clients).where((clients.c.id==cid) & (clients.c.account_id==current_account_id()))).mappings().first()
    return jsonify(dict(row)),201

@app.patch("/api/clients/<int:client_id>")
def update_client(client_id):
    denied=require_admin()
    if denied:
        return denied
    body=request.get_json(silent=True) or {}
    values={}
    for key,limit in [("name",180),("phone",80),("doc",80),("email",180),("notes",4000)]:
        if key in body:
            values[key]=str(body.get(key) or "").strip()[:limit]
    if "name" in values and not values["name"]:
        return jsonify({"error":"Informe o nome do cliente"}),400
    values["updated_at"]=utcnow()
    with engine.begin() as conn:
        result=conn.execute(update(clients).where((clients.c.id==client_id) & (clients.c.account_id==current_account_id())).values(**values))
        if not result.rowcount:
            return jsonify({"error":"Cliente não encontrado"}),404
        row=conn.execute(select(clients).where((clients.c.id==client_id) & (clients.c.account_id==current_account_id()))).mappings().first()
    return jsonify(dict(row))

@app.delete("/api/clients/<int:client_id>")
def delete_client(client_id):
    denied=require_admin()
    if denied:
        return denied
    with engine.begin() as conn:
        row=conn.execute(select(clients).where((clients.c.id==client_id) & (clients.c.account_id==current_account_id()))).mappings().first()
        if not row:
            return jsonify({"error":"Cliente não encontrado"}),404
        conn.execute(clients.delete().where((clients.c.id==client_id) & (clients.c.account_id==current_account_id())))
    return jsonify({"ok":True})

@app.get("/api/interpretations")
def interpretation_history():
    denied = require_admin()
    if denied:
        return denied
    with engine.connect() as conn:
        rows = conn.execute(
            select(interpretation_logs)
            .where(interpretation_logs.c.account_id==current_account_id())
            .order_by(interpretation_logs.c.id.desc())
            .limit(50)
        ).mappings().all()
    data=[]
    for r in rows:
        try: result=json.loads(r["result_json"])
        except Exception: result={}
        try: corrected=json.loads(r["corrected_json"]) if r["corrected_json"] else None
        except Exception: corrected=None
        data.append({
            "id":r["id"],"text":r["original_text"],"result":result,
            "source":r["source"],"model":r["model"],"elapsed_ms":r["elapsed_ms"],
            "corrected":corrected,
            "created_at":r["created_at"].isoformat() if r["created_at"] else None
        })
    return jsonify(data)

@app.post("/api/interpretations/<int:log_id>/correction")
def save_interpretation_correction(log_id):
    denied = require_admin()
    if denied:
        return denied
    body=request.get_json(silent=True) or {}
    corrected=body.get("corrected")
    if not isinstance(corrected, dict):
        return jsonify({"error":"Correção inválida"}),400
    with engine.begin() as conn:
        result=conn.execute(
            update(interpretation_logs)
            .where((interpretation_logs.c.id==log_id) & (interpretation_logs.c.account_id==current_account_id()))
            .values(corrected_json=json.dumps(corrected,ensure_ascii=False))
        )
    if not result.rowcount:
        return jsonify({"error":"Interpretação não encontrada"}),404
    return jsonify({"ok":True})

@app.get("/api/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(select(provider.c.id).limit(1))
        return jsonify({"ok": True, "database": "online", "version": "1.6.17"})
    except Exception as e:
        return jsonify({"ok": False, "database": "offline", "error": str(e)}), 503

@app.get("/api/auth/config")
def auth_config():
    return jsonify({
        "googleEnabled": bool(GOOGLE_CLIENT_ID),
        "googleClientId": GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID else "",
        "demoEnabled": APP_ENV == "development",
        "mobileBearerAuth": True,
        "publicAppUrl": PUBLIC_APP_URL,
        "version": "1.6.17"
    })


@app.get("/api/session")
def api_session():
    if not is_admin():
        return jsonify({"authenticated": False})
    with engine.connect() as conn:
        user = _session_user_payload(conn, current_user_id())
    if not user:
        session.clear()
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "user": user})



def _issue_api_token(conn, user_id, label="mobile"):
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    expires_at = utcnow() + timedelta(days=MOBILE_TOKEN_DAYS)
    conn.execute(insert(api_tokens).values(
        user_id=user_id,
        token_hash=token_hash,
        label=str(label or "mobile")[:80],
        expires_at=expires_at,
        revoked=False,
        created_at=utcnow(),
        last_used_at=None
    ))
    return raw, expires_at


def _verify_google_credential(credential):
    if not GOOGLE_CLIENT_ID:
        raise RuntimeError("Login Google ainda não foi configurado")
    if google_id_token is None or google_requests is None:
        raise RuntimeError("Dependência google-auth não instalada")

    info = google_id_token.verify_oauth2_token(
        credential,
        google_requests.Request(),
        GOOGLE_CLIENT_ID
    )
    email = str(info.get("email") or "").strip().lower()
    sub = str(info.get("sub") or "").strip()
    name = str(info.get("name") or (email.split("@")[0] if email else "Usuário")).strip()[:180]
    verified = bool(info.get("email_verified"))
    if not email or not sub or not verified:
        raise ValueError("Conta Google não pôde ser verificada")
    return {"email": email, "sub": sub, "name": name}


def _get_or_create_google_user(conn, identity):
    email, sub, name = identity["email"], identity["sub"], identity["name"]
    user = conn.execute(select(users).where(users.c.email == email)).mappings().first()

    if user:
        if not user["is_active"]:
            raise PermissionError("Conta desativada")
        existing_sub = str(user["google_sub"] or "").strip()
        if existing_sub and existing_sub != sub:
            raise PermissionError("Esta conta já está vinculada a outra identidade Google")
        conn.execute(update(users).where(users.c.id == user["id"]).values(
            google_sub=sub,
            email_verified=True,
            last_login_at=utcnow()
        ))
        return conn.execute(select(users).where(users.c.id == user["id"])).mappings().first()

    account_id = _create_account(conn, f"Negócio de {name.split()[0]}")
    result = conn.execute(insert(users).values(
        account_id=account_id,
        name=name,
        email=email,
        password_hash="",
        google_sub=sub,
        auth_provider="google",
        email_verified=True,
        is_active=True,
        created_at=utcnow(),
        last_login_at=utcnow()
    ))
    user_id = result.inserted_primary_key[0]
    return conn.execute(select(users).where(users.c.id == user_id)).mappings().first()

@app.post("/api/register")
def register():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()[:180]
    business_name = str(body.get("businessName") or body.get("business_name") or "").strip()[:180]
    email = str(body.get("email") or "").strip().lower()[:180]
    password = str(body.get("password") or "")

    if len(name) < 2:
        return jsonify({"error": "Informe seu nome"}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Informe um e-mail válido"}), 400
    if len(password) < 8:
        return jsonify({"error": "A senha deve ter pelo menos 8 caracteres"}), 400
    if not business_name:
        business_name = f"Negócio de {name.split()[0]}"

    try:
        with engine.begin() as conn:
            exists = conn.execute(select(users.c.id).where(users.c.email == email)).first()
            if exists:
                return jsonify({"error": "Já existe uma conta com este e-mail"}), 409
            account_id = _create_account(conn, business_name)
            result = conn.execute(insert(users).values(
                account_id=account_id, name=name, email=email,
                password_hash=generate_password_hash(password),
                google_sub="", auth_provider="email", email_verified=False,
                is_active=True, created_at=utcnow(), last_login_at=utcnow()
            ))
            user_id = result.inserted_primary_key[0]
            user = conn.execute(select(users).where(users.c.id==user_id)).mappings().first()
        _start_session(user)
        return jsonify({"ok": True, "user": {"id": user_id, "name": name, "email": email, "account_id": account_id}}), 201
    except IntegrityError:
        return jsonify({"error": "Já existe uma conta com este e-mail"}), 409


@app.post("/api/login")
def login():
    body = request.get_json(silent=True) or {}
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    remember = bool(body.get("remember"))
    with engine.begin() as conn:
        user = conn.execute(select(users).where(users.c.email == email)).mappings().first()
        if not user or not user["is_active"] or not user["password_hash"] or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "E-mail ou senha incorretos"}), 401
        conn.execute(update(users).where(users.c.id==user["id"]).values(last_login_at=utcnow()))
    _start_session(user, remember=remember)
    return jsonify({"ok": True, "email": email, "name": user["name"]})


@app.post("/api/auth/google")
def google_login():
    body = request.get_json(silent=True) or {}
    credential = str(body.get("credential") or "").strip()
    if not credential:
        return jsonify({"error": "Credencial Google ausente"}), 400
    try:
        identity = _verify_google_credential(credential)
        with engine.begin() as conn:
            user = _get_or_create_google_user(conn, identity)
        _start_session(user, remember=True)
        return jsonify({"ok": True, "email": user["email"], "name": user["name"]})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        print("Falha no login Google:", repr(e))
        return jsonify({"error": "Não foi possível validar o login Google"}), 401


@app.post("/api/mobile/token")
def mobile_token():
    """Token Bearer para futuro app Android/iOS, sem alterar o login web por sessão."""
    body = request.get_json(silent=True) or {}
    label = str(body.get("label") or "mobile")[:80]

    try:
        with engine.begin() as conn:
            google_credential = str(body.get("googleCredential") or "").strip()
            if google_credential:
                identity = _verify_google_credential(google_credential)
                user = _get_or_create_google_user(conn, identity)
            else:
                email = str(body.get("email") or "").strip().lower()
                password = str(body.get("password") or "")
                user = conn.execute(select(users).where(users.c.email == email)).mappings().first()
                if (
                    not user
                    or not user["is_active"]
                    or not user["password_hash"]
                    or not check_password_hash(user["password_hash"], password)
                ):
                    return jsonify({"error": "E-mail ou senha incorretos"}), 401
                conn.execute(update(users).where(users.c.id == user["id"]).values(last_login_at=utcnow()))

            raw_token, expires_at = _issue_api_token(conn, user["id"], label=label)
            payload = _session_user_payload(conn, user["id"])

        return jsonify({
            "ok": True,
            "access_token": raw_token,
            "token_type": "Bearer",
            "expires_at": expires_at.isoformat(),
            "user": payload
        })
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 401


@app.get("/api/mobile/me")
def mobile_me():
    identity = _bearer_identity()
    if not identity:
        return jsonify({"error": "Token inválido ou expirado"}), 401
    with engine.connect() as conn:
        user = _session_user_payload(conn, identity["user_id"])
    return jsonify({"authenticated": True, "user": user})


@app.post("/api/mobile/logout")
def mobile_logout():
    token_id = current_api_token_id()
    if not token_id:
        return jsonify({"error": "Token inválido ou ausente"}), 401
    with engine.begin() as conn:
        conn.execute(update(api_tokens).where(api_tokens.c.id == token_id).values(revoked=True))
    return jsonify({"ok": True})


@app.post("/api/password/forgot")
def password_forgot():
    body = request.get_json(silent=True) or {}
    email = str(body.get("email") or "").strip().lower()
    generic = {"ok": True, "message": "Se esse e-mail estiver cadastrado, enviaremos as instruções de recuperação."}
    with engine.begin() as conn:
        user = conn.execute(select(users).where(users.c.email == email)).mappings().first()
        if not user:
            return jsonify(generic)
        conn.execute(
            update(password_reset_tokens)
            .where((password_reset_tokens.c.user_id == user["id"]) & (password_reset_tokens.c.used == False))
            .values(used=True)
        )
        token = secrets.token_urlsafe(48)
        conn.execute(insert(password_reset_tokens).values(
            user_id=user["id"], token=token, expires_at=utcnow()+timedelta(minutes=30),
            used=False, created_at=utcnow()
        ))
    try:
        sent = _send_reset_email(email, token)
    except Exception as e:
        sent = False
        print("Falha ao enviar e-mail de recuperação:", repr(e))
    if not sent and APP_ENV == "development":
        print(f"[DEV] Recuperação de senha para {email}: {PUBLIC_APP_URL}/?reset={token}")
    return jsonify(generic)


@app.post("/api/password/reset")
def password_reset():
    body = request.get_json(silent=True) or {}
    token = str(body.get("token") or "").strip()
    password = str(body.get("password") or "")
    if len(password) < 8:
        return jsonify({"error": "A senha deve ter pelo menos 8 caracteres"}), 400
    with engine.begin() as conn:
        row = conn.execute(select(password_reset_tokens).where(password_reset_tokens.c.token==token)).mappings().first()
        if not row or row["used"] or _aware_utc(row["expires_at"]) < utcnow():
            return jsonify({"error": "Link de recuperação inválido ou expirado"}), 400
        conn.execute(update(users).where(users.c.id==row["user_id"]).values(password_hash=generate_password_hash(password), auth_provider="email"))
        conn.execute(update(password_reset_tokens).where(password_reset_tokens.c.id==row["id"]).values(used=True))
    return jsonify({"ok": True})


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/account/stats")
def account_stats():
    denied = require_admin()
    if denied:
        return denied
    aid = current_account_id()
    with engine.connect() as conn:
        client_count = conn.execute(
            select(func.count()).select_from(clients).where(clients.c.account_id == aid)
        ).scalar_one()
        quote_count = conn.execute(
            select(func.count()).select_from(quotes).where(quotes.c.account_id == aid)
        ).scalar_one()
        quoted_total = conn.execute(
            select(func.coalesce(func.sum(quotes.c.total), 0)).where(quotes.c.account_id == aid)
        ).scalar_one()
    return jsonify({
        "clients": int(client_count or 0),
        "quotes": int(quote_count or 0),
        "quotedTotal": float(quoted_total or 0),
        "version": "1.6.17"
    })


@app.get("/api/account/export")
def account_export():
    denied = require_admin()
    if denied:
        return denied
    aid = current_account_id()
    uid = current_user_id()
    with engine.connect() as conn:
        account_row = conn.execute(select(accounts).where(accounts.c.id == aid)).mappings().first()
        user_row = conn.execute(select(users).where(users.c.id == uid)).mappings().first()
        provider_row = conn.execute(select(provider).where(provider.c.account_id == aid)).mappings().first()
        client_rows = conn.execute(select(clients).where(clients.c.account_id == aid)).mappings().all()
        quote_rows = conn.execute(select(quotes).where(quotes.c.account_id == aid)).mappings().all()

    def clean(row):
        if not row:
            return None
        out = {}
        for key, value in dict(row).items():
            if key in {"password_hash", "google_sub"}:
                continue
            if isinstance(value, datetime):
                out[key] = _aware_utc(value).isoformat()
            else:
                out[key] = value
        return out

    return jsonify({
        "schemaVersion": "1.6.11",
        "exportedAt": utcnow().isoformat(),
        "account": clean(account_row),
        "user": clean(user_row),
        "provider": clean(provider_row),
        "clients": [clean(row) for row in client_rows],
        "quotes": [clean(row) for row in quote_rows]
    })


@app.get("/api/production-readiness")
def production_readiness():
    denied = require_admin()
    if denied:
        return denied
    checks = {
        "productionMode": APP_ENV == "production",
        "postgresConfigured": not DATABASE_URL.lower().startswith("sqlite"),
        "googleConfigured": bool(GOOGLE_CLIENT_ID),
        "smtpConfigured": bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD),
        "secureCookie": bool(SESSION_COOKIE_SECURE_CONFIG),
        "bootstrapAdminDisabled": not BOOTSTRAP_ADMIN,
        "secretKeyCustom": SECRET_KEY not in {"", "dev-only-change-me", "change-me", "secret"}
    }
    return jsonify({"ready": all(checks.values()), "checks": checks, "version": "1.6.17"})



@app.get("/api/account/profile")
def account_profile():
    uid = current_user_id()
    aid = current_account_id()
    if not uid or not aid:
        return jsonify({"error":"Não autenticado"}), 401
    with engine.connect() as conn:
        user = conn.execute(select(users).where(users.c.id == uid)).mappings().first()
        account = conn.execute(select(accounts).where(accounts.c.id == aid)).mappings().first()
    if not user or not account:
        return jsonify({"error":"Conta não encontrada"}), 404
    return jsonify({
        "account":{"id":account["id"],"name":account["name"]},
        "user":{"id":user["id"],"name":user["name"],"email":user["email"],
                "email_verified":bool(user["email_verified"]),
                "auth_provider":user["auth_provider"]},
        "version":"1.6.17"
    })


@app.patch("/api/account/profile")
def update_account_profile():
    uid = current_user_id()
    aid = current_account_id()
    if not uid or not aid:
        return jsonify({"error":"Não autenticado"}), 401

    body = request.get_json(silent=True) or {}
    user_name = str(body.get("userName") or body.get("user_name") or "").strip()[:180]
    business_name = str(body.get("businessName") or body.get("business_name") or "").strip()[:180]

    if len(user_name) < 2:
        return jsonify({"error":"Informe o nome do responsável"}), 400
    if len(business_name) < 2:
        return jsonify({"error":"Informe o nome da empresa"}), 400

    with engine.begin() as conn:
        user = conn.execute(
            select(users).where((users.c.id == uid) & (users.c.account_id == aid))
        ).mappings().first()
        account = conn.execute(select(accounts).where(accounts.c.id == aid)).mappings().first()
        if not user or not account:
            return jsonify({"error":"Conta não encontrada"}), 404

        conn.execute(
            update(users)
            .where((users.c.id == uid) & (users.c.account_id == aid))
            .values(name=user_name)
        )
        conn.execute(
            update(accounts)
            .where(accounts.c.id == aid)
            .values(name=business_name)
        )

        # Mantém a identidade comercial dos novos orçamentos coerente com a empresa.
        existing_provider = conn.execute(
            select(provider).where(provider.c.account_id == aid)
        ).mappings().first()
        if existing_provider and not str(existing_provider["name"] or "").strip():
            conn.execute(
                update(provider)
                .where(provider.c.account_id == aid)
                .values(name=business_name)
            )

    session["user_name"] = user_name
    return jsonify({
        "ok": True,
        "account": {"id": aid, "name": business_name},
        "user": {
            "id": uid,
            "name": user_name,
            "email": user["email"],
            "email_verified": bool(user["email_verified"]),
            "auth_provider": user["auth_provider"]
        },
        "version": "1.6.17"
    })


@app.get("/api/provider")
def get_provider():
    denied = require_admin()
    if denied:
        return denied
    with engine.connect() as conn:
        row = conn.execute(select(provider).where(provider.c.account_id == current_account_id())).mappings().first()
    if not row:
        return jsonify({"name":"","phone":"","doc":""})
    return jsonify({"name":row["name"],"phone":row["phone"],"doc":row["doc"]})

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
        result = conn.execute(
            update(provider)
            .where(provider.c.account_id == current_account_id())
            .values(**values)
        )
        if not result.rowcount:
            conn.execute(insert(provider).values(account_id=current_account_id(), **values))
        if values["name"]:
            conn.execute(
                update(accounts)
                .where(accounts.c.id == current_account_id())
                .values(name=values["name"])
            )
    return jsonify({"ok": True, **values})


def _pdf_money(value):
    try:
        value=float(value or 0)
    except Exception:
        value=0.0
    s=f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def _pdf_num(value):
    try:
        n=float(value)
        if n.is_integer():
            return str(int(n))
        return f"{n:.2f}".replace(".", ",")
    except Exception:
        return "1"

def _safe_pdf_text(value):
    # Paragraph understands a small HTML subset; escape user content.
    import html as _html
    return _html.escape(str(value or "")).replace("\n", "<br/>")

def build_quote_pdf(payload):
    client=str(payload.get("client") or "Cliente").strip()
    items=payload.get("items") or []
    notes=str(payload.get("notes") or "").strip()
    quote_id=str(payload.get("id") or "").strip()
    provider_data=payload.get("provider") or {}

    buf=BytesIO()
    doc=SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=13*mm, bottomMargin=16*mm,
        title=f"Orçamento {quote_id}".strip(),
        author="FalaOrçamento"
    )

    styles=getSampleStyleSheet()
    ink=colors.HexColor("#101828")
    purple=colors.HexColor("#5947F1")
    purple_dark=colors.HexColor("#4738D1")
    purple_soft=colors.HexColor("#F3F1FF")
    slate=colors.HexColor("#667085")
    border=colors.HexColor("#E4E7EC")
    soft=colors.HexColor("#F8F9FC")
    green=colors.HexColor("#15803D")

    body=ParagraphStyle("pBody", parent=styles["Normal"], fontName="Helvetica",
                        fontSize=9.5, leading=13, textColor=ink)
    small=ParagraphStyle("pSmall", parent=body, fontSize=7.8, leading=10, textColor=slate)
    label=ParagraphStyle("pLabel", parent=small, fontName="Helvetica-Bold",
                         fontSize=7.4, leading=9, textColor=slate)
    heading=ParagraphStyle("pHeading", parent=body, fontName="Helvetica-Bold",
                           fontSize=21, leading=25, textColor=ink)
    section=ParagraphStyle("pSection", parent=body, fontName="Helvetica-Bold",
                           fontSize=8, leading=10, textColor=purple)
    right=ParagraphStyle("pRight", parent=body, alignment=TA_RIGHT)
    right_bold=ParagraphStyle("pRightBold", parent=right, fontName="Helvetica-Bold")
    total=ParagraphStyle("pTotal", parent=right, fontName="Helvetica-Bold",
                         fontSize=22, leading=24, textColor=purple_dark)

    provider_name=str(provider_data.get("name") or "Dados do prestador não cadastrados").strip()
    provider_phone=str(provider_data.get("phone") or "").strip()
    provider_doc=str(provider_data.get("doc") or "").strip()

    story=[]

    # Premium brand header
    brand=Paragraph(
        '<font color="#5947F1" size="14"><b>Fala</b></font>'
        '<font color="#101828" size="14"><b>Orçamento</b></font><br/>'
        '<font color="#667085" size="7.5">ORÇAMENTO PROFISSIONAL</font>', body)
    badge=PDFTable([[Paragraph('<font color="#15803D"><b>ORÇAMENTO</b></font>', small)]],
                   colWidths=[31*mm])
    badge.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#ECFDF3")),
        ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#ABEFC6")),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),2.2*mm),
        ("BOTTOMPADDING",(0,0),(-1,-1),2.2*mm),
    ]))
    head=PDFTable([[brand,badge]],colWidths=[130*mm,35*mm])
    head.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ALIGN",(1,0),(1,0),"RIGHT"),
        ("LINEBELOW",(0,0),(-1,-1),0.7,border),
        ("BOTTOMPADDING",(0,0),(-1,-1),5*mm),
    ]))
    story += [head, Spacer(1,7*mm)]

    qtitle=f"Orçamento #{_safe_pdf_text(quote_id)}" if quote_id else "Orçamento"
    meta=Paragraph(f"Emitido em <b>{datetime.now().strftime('%d/%m/%Y')}</b>",small)
    story += [Paragraph(qtitle,heading), Spacer(1,1.5*mm), meta, Spacer(1,6*mm)]

    # Provider and client in elegant cards
    def info_block(title_txt, main_txt, extra_lines):
        lines=[f'<font color="#5947F1"><b>{title_txt}</b></font>',
               f'<font size="11"><b>{_safe_pdf_text(main_txt)}</b></font>']
        for x in extra_lines:
            if x: lines.append(f'<font color="#667085" size="8">{_safe_pdf_text(x)}</font>')
        return Paragraph("<br/><br/>".join(lines),body)

    provider_block=info_block("PRESTADOR",provider_name,[provider_phone,provider_doc])
    client_block=info_block("CLIENTE",client,[])
    cards=PDFTable([[provider_block,client_block]],colWidths=[81*mm,81*mm])
    cards.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),soft),
        ("BOX",(0,0),(-1,-1),0.6,border),
        ("INNERGRID",(0,0),(-1,-1),0.6,border),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),5*mm),
        ("RIGHTPADDING",(0,0),(-1,-1),5*mm),
        ("TOPPADDING",(0,0),(-1,-1),4.5*mm),
        ("BOTTOMPADDING",(0,0),(-1,-1),4.5*mm),
    ]))
    story += [cards, Spacer(1,7*mm)]

    story += [Paragraph("DETALHAMENTO",section), Spacer(1,2.5*mm)]

    rows=[[
        Paragraph("Descrição",label),
        Paragraph("Qtd.",label),
        Paragraph("Valor unit.",label),
        Paragraph("Subtotal",label)
    ]]
    grand=0.0
    for raw in items[:100]:
        try: qty=float(raw.get("qty",1) or 1)
        except: qty=1
        try: unit=float(raw.get("unit",raw.get("value",0)) or 0)
        except: unit=0
        subtotal=qty*unit
        grand+=subtotal
        rows.append([
            Paragraph(_safe_pdf_text(raw.get("name") or "Serviço"),body),
            Paragraph(_pdf_num(qty),right),
            Paragraph(_pdf_money(unit),right),
            Paragraph(_pdf_money(subtotal),right_bold),
        ])
    if len(rows)==1:
        rows.append([Paragraph("Nenhum item informado.",small),"","",""])

    item_table=PDFTable(rows,colWidths=[81*mm,18*mm,31*mm,32*mm],repeatRows=1)
    item_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),purple_soft),
        ("TEXTCOLOR",(0,0),(-1,0),slate),
        ("LINEBELOW",(0,0),(-1,0),0.8,purple),
        ("LINEBELOW",(0,1),(-1,-1),0.45,border),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),3.2*mm),
        ("RIGHTPADDING",(0,0),(-1,-1),3.2*mm),
        ("TOPPADDING",(0,0),(-1,-1),3.4*mm),
        ("BOTTOMPADDING",(0,0),(-1,-1),3.4*mm),
    ]))
    story += [item_table, Spacer(1,6*mm)]

    # Total area
    total_box=PDFTable([
        [Paragraph("VALOR TOTAL",label), Paragraph(_pdf_money(grand),total)]
    ],colWidths=[90*mm,72*mm])
    total_box.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),purple_soft),
        ("BOX",(0,0),(-1,-1),0.8,colors.HexColor("#D8D3FF")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),5*mm),
        ("RIGHTPADDING",(0,0),(-1,-1),5*mm),
        ("TOPPADDING",(0,0),(-1,-1),4.5*mm),
        ("BOTTOMPADDING",(0,0),(-1,-1),4.5*mm),
    ]))
    story += [KeepTogether(total_box), Spacer(1,6*mm)]

    if notes:
        story += [Paragraph("CONDIÇÕES E OBSERVAÇÕES",section),Spacer(1,2*mm)]
        note=PDFTable([[Paragraph(_safe_pdf_text(notes),body)]],colWidths=[162*mm])
        note.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),soft),
            ("BOX",(0,0),(-1,-1),0.6,border),
            ("LEFTPADDING",(0,0),(-1,-1),4.5*mm),
            ("RIGHTPADDING",(0,0),(-1,-1),4.5*mm),
            ("TOPPADDING",(0,0),(-1,-1),4*mm),
            ("BOTTOMPADDING",(0,0),(-1,-1),4*mm),
        ]))
        story += [note,Spacer(1,7*mm)]

    # Closing
    closing=PDFTable([[
        Paragraph('<b>Obrigado pela preferência.</b><br/><font color="#667085" size="8">Este documento foi gerado digitalmente pelo FalaOrçamento.</font>',body),
        Paragraph('<font color="#5947F1"><b>FalaOrçamento</b></font>',right)
    ]],colWidths=[115*mm,47*mm])
    closing.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"BOTTOM"),
        ("LINEABOVE",(0,0),(-1,-1),0.6,border),
        ("TOPPADDING",(0,0),(-1,-1),4*mm),
    ]))
    story.append(closing)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.setFont("Helvetica",7)
        canvas.drawString(15*mm,7.5*mm,"Documento gerado pelo FalaOrçamento")
        canvas.drawRightString(195*mm,7.5*mm,f"Página {doc.page}")
        canvas.restoreState()

    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    buf.seek(0)
    return buf

@app.post("/api/pdf")
def generate_quote_pdf():
    denied=require_admin()
    if denied:
        return denied
    body=request.get_json(silent=True) or {}

    # O prestador do PDF deve ser SEMPRE o empresário/empresa salvo em "Meu negócio".
    # Não confiamos no frontend para esse campo e não usamos "FalaOrçamento" como prestador.
    with engine.connect() as conn:
        pr=conn.execute(select(provider).where(provider.c.account_id==current_account_id())).mappings().first()

    provider_data=dict(pr) if pr else {}
    body["provider"]={
        "name": str(provider_data.get("name") or "").strip(),
        "phone": str(provider_data.get("phone") or "").strip(),
        "doc": str(provider_data.get("doc") or "").strip()
    }

    pdf=build_quote_pdf(body)
    qid=str(body.get("id") or "").strip()
    filename=f"orcamento-{qid}.pdf" if qid else "orcamento.pdf"
    return send_file(pdf,mimetype="application/pdf",as_attachment=True,download_name=filename)

@app.get("/api/quotes")
def list_quotes():
    denied = require_admin()
    if denied:
        return denied
    with engine.connect() as conn:
        rows = conn.execute(
            select(quotes).where(quotes.c.account_id==current_account_id()).order_by(quotes.c.id.desc()).limit(100)
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
    client = str(body.get("client") or "").strip()[:180]
    incoming_items = body.get("items") or []
    notes = str(body.get("notes") or "")[:4000]

    if not client or client.lower() == "cliente":
        return jsonify({"error":"Informe o nome do cliente"}),400
    if not isinstance(incoming_items, list) or not incoming_items:
        return jsonify({"error":"Adicione pelo menos um item ao orçamento"}),400

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
        pr = conn.execute(select(provider).where(provider.c.account_id == current_account_id())).mappings().first()
        if not pr:
            pr = {"name":"","phone":"","doc":""}
        token = uuid.uuid4().hex
        now = utcnow()
        result = conn.execute(insert(quotes).values(
            account_id=current_account_id(),
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
        row = conn.execute(select(quotes).where((quotes.c.id == qid) & (quotes.c.account_id==current_account_id()))).mappings().first()

    return jsonify(quote_dict(row)), 201

@app.patch("/api/quotes/<token>")
def update_quote(token):
    body = request.get_json(silent=True) or {}

    with engine.begin() as conn:
        row = conn.execute(
            select(quotes).where(quotes.c.public_token == token)
        ).mappings().first()

        if not row:
            return jsonify({"error": "Orçamento não encontrado"}), 404

        values={"updated_at":utcnow()}

        # Cliente/itens/observações só podem ser alterados pela área administrativa.
        editable_fields = any(k in body for k in ("client","items","notes"))
        if editable_fields:
            denied = require_admin()
            if denied:
                return denied
            if row["account_id"] != current_account_id():
                return jsonify({"error":"Orçamento não pertence a esta conta"}),403

            client = str(body.get("client", row["client"]) or "Cliente").strip()[:180]
            notes = str(body.get("notes", row["notes"]) or "")[:4000]
            incoming_items = body.get("items")
            if incoming_items is None:
                clean_items = json.loads(row["items_json"])
                total = float(row["total"] or 0)
            else:
                clean_items=[]
                total=0.0
                for raw in (incoming_items or [])[:100]:
                    try:
                        qty=float(raw.get("qty",1) or 1)
                        unit=float(raw.get("unit",0) or 0)
                    except (ValueError,TypeError):
                        qty,unit=1.0,0.0
                    qty=max(0.01,min(qty,100000))
                    unit=max(0.0,min(unit,100000000))
                    item_total=round(qty*unit,2)
                    clean_items.append({
                        "name":str(raw.get("name") or "Serviço").strip()[:250],
                        "qty":qty,"unit":unit,"value":item_total
                    })
                    total += item_total

            values.update({
                "client":client,
                "items_json":json.dumps(clean_items,ensure_ascii=False),
                "notes":notes,
                "total":round(total,2)
            })

        if "status" in body:
            status=body.get("status")
            if status not in {"pending","accepted","rejected"}:
                return jsonify({"error":"Status inválido"}),400
            current_status = str(row["status"] or "pending")
            if current_status in {"accepted","rejected"} and status != current_status:
                return jsonify({
                    "error":"Este orçamento já recebeu uma resposta do cliente",
                    "status":current_status,
                    "responseAt":_aware_utc(row.get("responded_at")).isoformat() if row.get("responded_at") else None
                }),409
            values["status"]=status
            if current_status == "pending" and status in {"accepted","rejected"}:
                values["responded_at"]=utcnow()

        conn.execute(
            update(quotes)
            .where(quotes.c.public_token == token)
            .values(**values)
        )

        updated_row=conn.execute(
            select(quotes).where(quotes.c.public_token == token)
        ).mappings().first()

    return jsonify(quote_dict(updated_row))

def _public_quote_html(row):
    q = quote_dict(row)
    status = str(q.get("status") or "pending")
    status_label = {"accepted":"ACEITO","rejected":"RECUSADO"}.get(status,"PENDENTE")
    status_class = {"accepted":"accepted","rejected":"rejected"}.get(status,"pending")
    items_html = "".join(
        f'<div class="item"><span>{escape(str(item.get("name") or "Serviço"))}</span><b>R$ {float(item.get("qty",1) or 1)*float(item.get("unit",0) or 0):,.2f}</b></div>'
        for item in (q.get("items") or [])
    ).replace(",", "X").replace(".", ",").replace("X", ".")
    total_text = f'{float(q.get("total") or 0):,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".")
    response_at = q.get("responseAt") or ""
    if status == "pending":
        actions = '<form method="post" action="/q/'+str(escape(str(q["token"])))+'/respond" class="actions">' + '<button class="accept" name="status" value="accepted" type="submit">✓ ACEITAR ORÇAMENTO</button>' + '<button class="reject" name="status" value="rejected" type="submit">✕ RECUSAR</button></form>'
    else:
        msg = "Orçamento aceito." if status == "accepted" else "Orçamento recusado."
        actions = f'<div class="response {status_class}">✓ {escape(msg)}' + (f'<small>Resposta registrada em {escape(response_at)}</small>' if response_at else '') + '</div>'
    notes = q.get("notes") or ""
    notes_html = f'<div class="notes"><b>Observações</b><br>{escape(str(notes))}</div>' if notes else ''
    provider = q.get("provider") or {}
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orçamento #{escape(str(q['id']))} · FalaOrçamento</title><meta name="theme-color" content="#4f46e5">
<style>*{{box-sizing:border-box}}body{{margin:0;background:#f5f7ff;color:#101828;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:24px 14px}}.wrap{{max-width:520px;margin:0 auto}}.brand{{display:flex;align-items:center;justify-content:center;gap:10px;font-size:22px;font-weight:800;margin:8px 0 22px}}.logo{{width:38px;height:38px;border-radius:12px;background:#5b4df6;color:white;display:grid;place-items:center;box-shadow:0 8px 24px rgba(79,70,229,.22)}}.brand span{{color:#5b4df6}}.card{{background:#fff;border:1px solid #e4e7ec;border-radius:18px;padding:18px;box-shadow:0 12px 35px rgba(16,24,40,.06)}}.head{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}}h1{{font-size:20px;margin:0}}.badge{{font-size:11px;font-weight:800;padding:6px 9px;border-radius:7px}}.pending{{background:#fff1c7;color:#8a6100}}.accepted{{background:#dff7e7;color:#087a38}}.rejected{{background:#fee4e2;color:#b42318}}.meta{{font-size:13px;line-height:1.5;margin:15px 0}}.meta b{{display:block;margin-bottom:2px}}.item{{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid #eef0f5;padding:12px 0;font-size:14px}}.item b{{white-space:nowrap}}.total{{display:flex;align-items:end;justify-content:space-between;padding-top:18px;font-size:15px}}.total strong{{font-size:25px}}.notes{{font-size:13px;background:#f8f9fc;border-radius:10px;padding:12px;margin-top:14px}}.actions{{display:grid;gap:10px;margin-top:12px}}button{{width:100%;padding:14px 12px;border-radius:11px;font-weight:800;font-size:14px;cursor:pointer}}.accept{{background:#2dbd68;color:white;border:1px solid #2dbd68}}.reject{{background:white;color:#e43c3c;border:1px solid #ff5b5b}}.response{{margin-top:12px;border-radius:11px;padding:14px;text-align:center;font-weight:800}}.response.accepted{{background:#e7f8ed;color:#087a38}}.response.rejected{{background:#feeceb;color:#b42318}}.response small{{display:block;font-weight:500;margin-top:5px;opacity:.8}}.footer{{text-align:center;color:#98a2b3;font-size:11px;margin:18px 0}}</style></head><body><main class="wrap"><div class="brand"><div class="logo">🎙</div>Fala<span>Orçamento</span></div><section class="card"><div class="head"><h1>Orçamento #{escape(str(q['id']))}</h1><span class="badge {status_class}">{status_label}</span></div><div class="meta"><b>Prestador</b>{escape(str(provider.get('name') or 'Prestador'))}<br>{escape(str(provider.get('phone') or ''))}<br>{escape(str(provider.get('doc') or ''))}</div><div class="meta"><b>Cliente</b>{escape(str(q.get('client') or 'Cliente'))}</div>{items_html}<div class="total"><span>Total</span><strong>R$ {total_text}</strong></div>{notes_html}</section>{actions}<div class="footer">Orçamento digital gerado pelo FalaOrçamento.</div></main></body></html>"""

@app.get("/q/<token>")
def public_quote_page(token):
    row = get_quote_by_token(token)
    if not row:
        return ("Orçamento não encontrado.", 404, {"Content-Type":"text/plain; charset=utf-8"})
    return (_public_quote_html(row), 200, {"Content-Type":"text/html; charset=utf-8", "Cache-Control":"no-store"})

@app.post("/q/<token>/respond")
def public_quote_respond(token):
    status = str(request.form.get("status") or "").strip().lower()
    if status not in {"accepted","rejected"}:
        return redirect(f"/q/{token}", code=303)
    with engine.begin() as conn:
        row = conn.execute(select(quotes).where(quotes.c.public_token == token)).mappings().first()
        if not row:
            return ("Orçamento não encontrado.", 404, {"Content-Type":"text/plain; charset=utf-8"})
        current = str(row["status"] or "pending")
        if current == "pending":
            conn.execute(update(quotes).where(quotes.c.public_token == token).values(status=status, responded_at=utcnow(), updated_at=utcnow()))
    return redirect(f"/q/{token}", code=303)


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.get("/<path:path>")
def static_files(path):
    file_path = FRONTEND_DIR / path
    if file_path.is_file():
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"FalaOrçamento v1.6.17 Inicialização Robusta: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
