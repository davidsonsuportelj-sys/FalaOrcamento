
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
import sqlite3, json, uuid, os, mimetypes

ROOT = Path(__file__).resolve().parent
DB = ROOT / "falaorcamento.db"

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            public_token TEXT UNIQUE NOT NULL,
            client TEXT NOT NULL,
            items_json TEXT NOT NULL,
            notes TEXT DEFAULT '',
            total REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            provider_name TEXT DEFAULT '',
            provider_phone TEXT DEFAULT '',
            provider_doc TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS provider (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            doc TEXT DEFAULT ''
        );
        INSERT OR IGNORE INTO provider(id,name,phone,doc) VALUES(1,'','','');
        """)
        conn.commit()

def row_to_quote(r):
    return {
        "id": f"{r['id']:04d}",
        "token": r["public_token"],
        "client": r["client"],
        "items": json.loads(r["items_json"]),
        "notes": r["notes"],
        "total": r["total"],
        "status": r["status"],
        "provider": {
            "name": r["provider_name"],
            "phone": r["provider_phone"],
            "doc": r["provider_doc"]
        },
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"]
    }

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = urlparse(path).path
        rel = path.lstrip("/") or "index.html"
        return str(ROOT / rel)

    def log_message(self, fmt, *args):
        print("[FalaOrçamento]", fmt % args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        p = urlparse(self.path).path

        if p == "/api/health":
            return self.send_json({"ok": True})

        if p == "/api/provider":
            with db() as conn:
                r = conn.execute("SELECT name,phone,doc FROM provider WHERE id=1").fetchone()
            return self.send_json(dict(r))

        if p == "/api/quotes":
            with db() as conn:
                rows = conn.execute("SELECT * FROM quotes ORDER BY id DESC LIMIT 50").fetchall()
            return self.send_json([row_to_quote(r) for r in rows])

        if p.startswith("/api/quotes/"):
            token = p.split("/")[-1]
            with db() as conn:
                r = conn.execute(
                    "SELECT * FROM quotes WHERE public_token=? OR printf('%04d',id)=?",
                    (token, token)
                ).fetchone()
            if not r:
                return self.send_json({"error":"Orçamento não encontrado"}, 404)
            return self.send_json(row_to_quote(r))

        return super().do_GET()

    def do_POST(self):
        p = urlparse(self.path).path

        if p == "/api/provider":
            body = self.read_json()
            name = str(body.get("name","")).strip()
            phone = str(body.get("phone","")).strip()
            doc = str(body.get("doc","")).strip()
            with db() as conn:
                conn.execute("UPDATE provider SET name=?,phone=?,doc=? WHERE id=1",(name,phone,doc))
                conn.commit()
            return self.send_json({"ok":True,"name":name,"phone":phone,"doc":doc})

        if p == "/api/quotes":
            body = self.read_json()
            client = str(body.get("client") or "Cliente").strip()
            items = body.get("items") or []
            notes = str(body.get("notes") or "")
            status = str(body.get("status") or "pending")
            total = 0.0
            clean_items = []
            for i in items:
                try:
                    q = float(i.get("qty",1) or 1)
                    unit = float(i.get("unit",0) or 0)
                except Exception:
                    q, unit = 1.0, 0.0
                clean_items.append({
                    "name": str(i.get("name","Serviço")),
                    "qty": q,
                    "unit": unit,
                    "value": q * unit
                })
                total += q * unit

            with db() as conn:
                pr = conn.execute("SELECT name,phone,doc FROM provider WHERE id=1").fetchone()
                token = uuid.uuid4().hex[:12]
                cur = conn.execute("""
                    INSERT INTO quotes(
                        public_token,client,items_json,notes,total,status,
                        provider_name,provider_phone,provider_doc
                    ) VALUES(?,?,?,?,?,?,?,?,?)
                """,(
                    token, client, json.dumps(clean_items,ensure_ascii=False), notes, total, status,
                    pr["name"], pr["phone"], pr["doc"]
                ))
                conn.commit()
                r = conn.execute("SELECT * FROM quotes WHERE id=?",(cur.lastrowid,)).fetchone()
            return self.send_json(row_to_quote(r), 201)

        return self.send_json({"error":"Rota não encontrada"},404)

    def do_PATCH(self):
        p = urlparse(self.path).path
        if p.startswith("/api/quotes/"):
            token = p.split("/")[-1]
            body = self.read_json()
            allowed = {"pending","accepted","rejected"}
            status = body.get("status")
            if status not in allowed:
                return self.send_json({"error":"Status inválido"},400)
            with db() as conn:
                cur = conn.execute("""
                    UPDATE quotes SET status=?, updated_at=CURRENT_TIMESTAMP
                    WHERE public_token=? OR printf('%04d',id)=?
                """,(status,token,token))
                conn.commit()
                r = conn.execute(
                    "SELECT * FROM quotes WHERE public_token=? OR printf('%04d',id)=?",
                    (token,token)
                ).fetchone()
            if not r:
                return self.send_json({"error":"Orçamento não encontrado"},404)
            return self.send_json(row_to_quote(r))
        return self.send_json({"error":"Rota não encontrada"},404)

def main():
    init_db()
    port = int(os.environ.get("PORT","8000"))
    print(f"\nFalaOrçamento v0.6.3")
    print(f"Acesse: http://localhost:{port}")
    print("Para testar em outro aparelho na mesma rede, use o IP local deste computador.")
    print("Pressione Ctrl+C para encerrar.\n")
    os.chdir(ROOT)
    ThreadingHTTPServer(("0.0.0.0",port), Handler).serve_forever()

if __name__ == "__main__":
    main()
