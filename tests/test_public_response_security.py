"""Regressão v1.6.30: confirmação pública e proteção de decisão."""
import ast, hashlib, hmac, re
from pathlib import Path
SRC=(Path(__file__).parents[1]/"backend"/"app.py").read_text(encoding="utf-8")
TREE=ast.parse(SRC)
NS={"re":re,"hmac":hmac,"hashlib":hashlib,"SECRET_KEY":"test-secret"}
for node in TREE.body:
    if isinstance(node,ast.FunctionDef) and node.name in {"_phone_last4","_quote_response_hash"}:
        exec(compile(ast.Module(body=[node],type_ignores=[]),"<security>","exec"),NS)
assert NS["_phone_last4"]("(11) 99876-1234")=="1234"
assert NS["_phone_last4"]("12")==""
a=NS["_quote_response_hash"]("tok-a","1234")
b=NS["_quote_response_hash"]("tok-a","1234")
c=NS["_quote_response_hash"]("tok-b","1234")
d=NS["_quote_response_hash"]("tok-a","9999")
assert len(a)==64 and a==b and a!=c and a!=d
assert 'hmac.compare_digest(verify_hash, expected)' in SRC
assert 'failures >= 5' in SRC
assert 'timedelta(minutes=15)' in SRC
assert 'Confirmação indisponível' in SRC
print('OK: confirmação pública protegida e limitador de tentativas presentes')
