"""Regressão do pós-processamento de descrições da v1.6.24 (sem rede/Groq)."""
import ast, re
from pathlib import Path

SRC = (Path(__file__).parents[1] / "backend" / "app.py").read_text(encoding="utf-8")
TREE = ast.parse(SRC)
NS = {"re": re}
for fname in ("_recover_specific_item_names", "_recover_client_name"):
    node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == fname)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<regression>", "exec"), NS)
recover = NS["_recover_specific_item_names"]
recover_client = NS["_recover_client_name"]

CASES = [
    ("João", "Cliente João, instalação de 3 tomadas a 80 reais cada e troca de disjuntor por 150 reais", [("Serviço",3,80),("Serviço",1,150)], ["Instalação de tomadas","Troca de disjuntor"]),
    ("Marcos", "Cliente Marcos, pintura de 2 quartos por 450 reais cada, pintura da sala por 700 reais e aplicação de massa corrida no corredor por 300 reais.", [("Pintura de quartos",2,450),("Serviço",1,700),("Serviço",1,300)], ["Pintura de quartos","Pintura de sala","Aplicação de massa corrida no corredor"]),
    ("Roberto", "Cliente Roberto, troca de 2 torneiras a 120 reais cada, instalação de chuveiro por 180 reais e conserto de vazamento na pia por 250 reais.", [("Troca de torneiras",2,120),("Instalação de chuveiro",1,180),("Reparo de vazamento na pia",1,250)], ["Troca de torneiras","Instalação de chuveiro","Reparo de vazamento na pia"]),
    ("Carlos", "Cliente Carlos, vou instalar 4 tomadas novas cobrando 75 reais em cada uma, também preciso trocar o quadro de disjuntores por 650 reais e revisar a parte elétrica da cozinha por 280 reais.", [("Serviço",4,75),("Serviço",1,650),("Serviço",1,280)], ["Instalação de tomadas","Troca de quadro de disjuntores","Revisão de parte elétrica da cozinha"]),
    ("Ana", "Orçamento para a Ana, vou assentar 25 metros de piso a 45 reais o metro, fazer o reboco de uma parede por 600 reais e trocar 5 telhas quebradas cobrando 35 reais cada.", [("Troca de telhas quebradas",25,45),("Serviço",1,600),("Serviço",5,35)], ["Assentamento de piso","Reboco de parede","Troca de telhas quebradas"]),
]

for expected_client, text, raw, expected_names in CASES:
    items=[{"name":n,"qty":q,"unit":u} for n,q,u in raw]
    before=[(x["qty"],x["unit"]) for x in items]
    got=recover(text, items)
    assert recover_client(text, "Cliente") == expected_client
    assert [x["name"] for x in got] == expected_names
    assert [(x["qty"],x["unit"]) for x in got] == before
print(f"OK: {len(CASES)} cenários de regressão passaram")
