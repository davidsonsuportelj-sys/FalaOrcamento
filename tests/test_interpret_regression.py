"""Regressão v1.6.25: interpretação natural, associação descrição/quantidade/preço e cliente."""
import ast
import re
from pathlib import Path

SRC=(Path(__file__).parents[1]/"backend"/"app.py").read_text(encoding="utf-8")
TREE=ast.parse(SRC)
NS={"re":re}
FUNCS={
    "_recover_specific_item_names","_spoken_number_to_int","_money_from_segment",
    "_canonical_service_name","_extract_strong_text_items","_repair_items_from_text",
    "_recover_client_name"
}
for node in TREE.body:
    if isinstance(node,ast.FunctionDef) and node.name in FUNCS:
        exec(compile(ast.Module(body=[node],type_ignores=[]),"<regression>","exec"),NS)

recover=NS["_recover_specific_item_names"]
repair=NS["_repair_items_from_text"]
recover_client=NS["_recover_client_name"]

def run(text, raw, parsed_client="Cliente"):
    items=[{"name":n,"qty":q,"unit":u} for n,q,u in raw]
    items=recover(text,items)
    items=repair(text,items)
    return recover_client(text,parsed_client),items

CASES=[
    # Casos validados nas v1.6.23/v1.6.24
    ("João","Cliente João, instalação de 3 tomadas a 80 reais cada e troca de disjuntor por 150 reais",
     [("Serviço",3,80),("Serviço",1,150)],[("Instalação de tomadas",3,80),("Troca de disjuntor",1,150)]),
    ("Marcos","Cliente Marcos, pintura de 2 quartos por 450 reais cada, pintura da sala por 700 reais e aplicação de massa corrida no corredor por 300 reais.",
     [("Pintura de quartos",2,450),("Serviço",1,700),("Serviço",1,300)],[("Pintura de quartos",2,450),("Pintura de sala",1,700),("Aplicação de massa corrida no corredor",1,300)]),
    ("Roberto","Cliente Roberto, troca de 2 torneiras a 120 reais cada, instalação de chuveiro por 180 reais e conserto de vazamento na pia por 250 reais.",
     [("Troca de torneiras",2,120),("Instalação de chuveiro",1,180),("Reparo de vazamento na pia",1,250)],[("Troca de torneiras",2,120),("Instalação de chuveiro",1,180),("Reparo de vazamento na pia",1,250)]),
    ("Carlos","Cliente Carlos, vou instalar 4 tomadas novas cobrando 75 reais em cada uma, também preciso trocar o quadro de disjuntores por 650 reais e revisar a parte elétrica da cozinha por 280 reais.",
     [("Serviço",4,75),("Serviço",1,650),("Serviço",1,280)],[("Instalação de tomadas",4,75),("Troca de quadro de disjuntores",1,650),("Revisão de parte elétrica da cozinha",1,280)]),
    ("Ana","Orçamento para a Ana, vou assentar 25 metros de piso a 45 reais o metro, fazer o reboco de uma parede por 600 reais e trocar 5 telhas quebradas cobrando 35 reais cada.",
     [("Troca de telhas quebradas",25,45),("Serviço",1,600),("Serviço",5,35)],[("Assentamento de piso",25,45),("Reboco de parede",1,600),("Troca de telhas quebradas",5,35)]),

    # Casos reais que motivaram a v1.6.25
    ("Renato","Cliente Renato, vou trocar as pastilhas de freio dianteiras por 320 reais, fazer a troca de óleo e filtro por 180 e alinhar o carro por 90 reais.",
     [("Troca de s pastilhas de freio",1,320),("Troca de óleo e filtro por 18",1,180),("Serviço",1,90)],
     [("Troca de pastilhas de freio dianteiras",1,320),("Troca de óleo e filtro",1,180),("Alinhamento de carro",1,90)]),
    ("Fernanda","Orçamento para Fernanda, limpeza de 3 aparelhos de ar condicionado a 120 reais cada, carga de gás em 1 aparelho por 250 e instalação de um suporte por 150.",
     [("Limpeza de aparelhos de ar",3,120),("Instalação de suporte",1,250),("Serviço",1,150)],
     [("Limpeza de aparelhos de ar condicionado",3,120),("Carga de gás",1,250),("Instalação de suporte",1,150)]),
    ("Gustavo","Cliente Gustavo, ajuste de duas portas de armário por 85 reais e 50 centavos cada, instalação de 4 puxadores a 25 reais cada e montagem de uma prateleira por 140 reais.",
     [("Instalação de puxadores a 2",2,85.5),("Serviço",4,25),("Serviço",1,140)],
     [("Ajuste de portas de armário",2,85.5),("Instalação de puxadores",4,25),("Montagem de prateleira",1,140)]),
    ("Patrícia","Para a cliente Patrícia, instalação de 5 luminárias, o serviço todo fica em 600 reais, troca de uma tomada por 80 reais e instalação de ventilador de teto por 250.",
     [("O serviço todo fica em",1,600),("Troca de uma tomada por 8",1,250)],
     [("Instalação de luminárias",1,600),("Troca de tomada",1,80),("Instalação de ventilador de teto",1,250)]),
    ("Lucas","Cliente Lucas, assentamento de 20 metros de porcelanato a 65 reais o metro de mão de obra e mais 900 reais de material, rejunte por 300 reais.",
     [("Assentamento de porcelanato",20,65),("Serviço",1,900),("Serviço",1,300)],
     [("Assentamento de porcelanato",20,65),("Material",1,900),("Rejunte",1,300)]),
]

for expected_client,text,raw,expected in CASES:
    client,items=run(text,raw)
    assert client==expected_client,(expected_client,client)
    got=[(x["name"],float(x["qty"]),float(x["unit"])) for x in items]
    exp=[(n,float(q),float(u)) for n,q,u in expected]
    assert got==exp,(expected_client,got,exp)

# Autocorreção: a v1.6.25 não deve reintroduzir o item cancelado.
text="Orçamento para Juliana, troca de 2 torneiras a 100 reais cada, não, corrigindo, são 3 torneiras a 100 reais cada, e instalação de chuveiro por 180 reais."
client,items=run(text,[("Troca de torneiras",3,100),("Instalação de chuveiro",1,180)])
assert client=="Juliana"
assert [(x["name"],x["qty"],x["unit"]) for x in items]==[("Troca de torneiras",3,100),("Instalação de chuveiro",1,180)]

print("OK: 11 cenários de regressão passaram")
