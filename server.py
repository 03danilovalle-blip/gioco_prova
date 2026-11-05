import os
from flask import Flask, request, jsonify, send_from_directory
import random
import string
from threading import Lock
import copy

app = Flask(__name__, static_folder="static", static_url_path="/static")

rooms = {}
rooms_lock = Lock()

DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "a")
MAX_TURNS = 8


def generate_room_code(length=6):
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(chars, k=length))
        if code not in rooms:
            return code


def safe_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def default_costs():
    return {
        "investimenti": 0.0,
        "ammortamenti": 0.0,
        "quantita_A": 0.0,
        "quantita_B": 0.0,
        "quantita_acquisti": 0.0,
        "finanziamento": 0.0,
        "debiti": 0.0,
        "crediti": 0.0,
        "stipendi": 0.0,
        "ricavi": 0.0,
        "costo_acquisti": 0.0,
        "costo_personale": 0.0,
        "promozione": 0.0,
        "capacita": 0.0,
        "ricerca": 0.0,
        "interessi": 0.0,
    }


def default_company(
    initial_capital,
    initial_raw_material_inventory=0,
    initial_capacity=100,
    initial_personnel=5,
    purchase_cost=0
):
    initial_capital = safe_float(initial_capital, 0)
    initial_raw_material_inventory = safe_float(
        initial_raw_material_inventory,
        0
    )
    initial_capacity = safe_float(initial_capacity, 100)
    initial_personnel = safe_int(initial_personnel, 5)
    purchase_cost = safe_float(purchase_cost, 0)

    # Valore economico del magazzino materie prime iniziale
    valore_magazzino_mp_iniziale = (
        initial_raw_material_inventory * purchase_cost
    )

    # Capitale sociale prima dell'elaborazione del turno 1
    capitale_sociale_iniziale = (
        initial_capital + valore_magazzino_mp_iniziale
    )

    return {
        "capital": round(initial_capital, 2),

        # Quantità fisica di materie prime
        "raw_material_inventory": initial_raw_material_inventory,

        "capacity": round(initial_capacity, 2),
        "personnel": initial_personnel,

        "fixed_investments": 0.0,
        "promotion_assets": [],
        "current_turn_depreciation": 0.0,
        "current_turn_promotion_investment": 0.0,
        "finanziamenti_attivi": [],
        "investimenti_attivi": [],
        "ricerche_interne_attive": [],

        "report": {
            "balance_sheet": {
                "fixed_investments": 0.0,

                # La cassa iniziale coincide con il capitale iniziale
                "cash": round(initial_capital, 2),

                # Nel report il magazzino è espresso in valore economico
                "raw_material_inventory": round(
                    valore_magazzino_mp_iniziale,
                    2
                ),

                "finished_goods_inventory": 0.0,
                "current_investments": 0.0,

                # CS iniziale = C0 + MP0 × CA
                "share_capital": round(
                    capitale_sociale_iniziale,
                    2
                ),
                "reserves": 0.0,

                "bank_debt_fixed": 0.0,
                "bank_debt_current": 0.0,
            },

            "income_statement": {
                "sales_revenue": 0.0,
                "variation_finished_goods": 0.0,
                "purchase_raw_materials": 0.0,
                "variation_raw_materials": 0.0,
                "personnel_cost": 0.0,
                "depreciation": 0.0,
                "interest": 0.0,
                "value_added": 0.0,
                "ebitda": 0.0,
                "operating_income": 0.0,
                "profit": 0.0,
            },

            "cash_flow": {
                "inflows_from_customers": 0.0,
                "outflows_to_suppliers": 0.0,
                "outflows_for_personnel": 0.0,
                "cash_interest": 0.0,
                "cash_promotion": 0.0,
                "cash_capacity": 0.0,
                "cash_research": 0.0,
                "debt_acquisition": 0.0,
                "debt_payment": 0.0,
            },
        },
    }
def default_products(production_time_a=0, production_time_b=0):
    return {
        "A": {
            "name": "Prodotto A",
            "price": 0,
            "visibility": 0.0,
            "research": 0.0,
            "quantity": 0,
            "production_per_hour": int(production_time_a),
            "research_mode": "Interna",
        },
        "B": {
            "name": "Prodotto B",
            "price": 0,
            "visibility": 0.0,
            "research": 0.0,
            "quantity": 0,
            "production_per_hour": int(production_time_b),
            "research_mode": "Interna",
        },
    }


def default_room_settings():
    return {
        "initial_capital": 100000,
        "initial_raw_material_inventory": 500,
        "initial_capacity": 100,
        "initial_personnel": 5,
        "market_initial_a": "150",
        "market_initial_b": "150",
        "market_final_a": "300",
        "market_final_b": "400",
        "market_variable_percentages_a": [50, 20, 30],
        "market_variable_percentages_b": [50, 30, 20],
        "market_values_a": [],
        "market_values_b": [],
        "interests": 6,
        "purchase_cost": 10,
        "production_time_a": 1,
        "production_time_b": 2,
        "investment_visibility_ratio_a": 10,
        "investment_visibility_ratio_b": 20,
        "innovation_internal_research_ratio_a": 10,
        "innovation_coproj_research_ratio_a": 20,
        "innovation_internal_research_ratio_b": 20,
        "innovation_coproj_research_ratio_b": 30,
        "investment_capacity_ratio": 10,
    }


def process_promotion_investments(company, promotion_amounts):
    company.setdefault("promotion_assets", [])
    company.setdefault("fixed_investments", 0.0)
    company.setdefault("current_turn_depreciation", 0.0)
    company.setdefault("current_turn_promotion_investment", 0.0)

    total_new_promotion = 0.0

    for amount in promotion_amounts:
        amount = float(amount or 0)

        if amount > 0:
            total_new_promotion += amount

            company["promotion_assets"].append({
                "remaining_value": round(amount, 2),
                "quota": round(amount / 4.0, 2),
                "remaining_turns": 4,
            })

    depreciation_this_turn = 0.0
    updated_assets = []

    for asset in company["promotion_assets"]:
        remaining_value = float(asset.get("remaining_value", 0))
        quota = float(asset.get("quota", 0))
        remaining_turns = int(asset.get("remaining_turns", 0))

        if remaining_turns > 0 and remaining_value > 0:
            applied_quota = min(quota, remaining_value)
            remaining_value = round(remaining_value - applied_quota, 2)
            remaining_turns -= 1
            depreciation_this_turn += applied_quota

        if remaining_turns > 0 and remaining_value > 0:
            updated_assets.append({
                "remaining_value": remaining_value,
                "quota": quota,
                "remaining_turns": remaining_turns,
            })

    company["promotion_assets"] = updated_assets
    company["fixed_investments"] = round(sum(a["remaining_value"] for a in updated_assets), 2)
    company["current_turn_depreciation"] = round(depreciation_this_turn, 2)
    company["current_turn_promotion_investment"] = round(total_new_promotion, 2)

    return company


def update_costs_from_state(costs, company, products):
    costs.setdefault("investimenti", 0.0)
    costs.setdefault("ammortamenti", 0.0)
    costs.setdefault("quantita_A", 0.0)
    costs.setdefault("quantita_B", 0.0)
    costs.setdefault("quantita_acquisti", 0.0)
    costs.setdefault("finanziamento", 0.0)
    costs.setdefault("debiti", 0.0)
    costs.setdefault("crediti", 0.0)
    costs.setdefault("stipendi", 0.0)
    costs.setdefault("ricavi", 0.0)
    costs.setdefault("costo_acquisti", 0.0)
    costs.setdefault("costo_personale", 0.0)
    costs.setdefault("promozione", 0.0)
    costs.setdefault("capacita", 0.0)
    costs.setdefault("ricerca", 0.0)
    costs.setdefault("interessi", 0.0)

    costs["investimenti"] = round(float(company.get("fixed_investments", 0)), 2)
    costs["ammortamenti"] = round(
        float(costs.get("ammortamenti", 0))
        + float(company.get("current_turn_depreciation", 0)),
        2
    )
    costs["quantita_A"] = float(products.get("A", {}).get("quantity", 0))
    costs["quantita_B"] = float(products.get("B", {}).get("quantity", 0))

    return costs


def update_cumulative_report(company, costs=None):
    costs = costs or {}

    company.setdefault("report", {})
    company["report"].setdefault("balance_sheet", {})
    company["report"].setdefault("income_statement", {})
    company["report"].setdefault("cash_flow", {})

    bs = company["report"]["balance_sheet"]
    inc = company["report"]["income_statement"]
    cf = company["report"]["cash_flow"]

    bs.setdefault("fixed_investments", 0.0)
    bs.setdefault("cash", round(float(company.get("capital", 0)), 2))
    bs.setdefault("raw_material_inventory", 0.0)
    bs.setdefault("finished_goods_inventory", 0.0)
    bs.setdefault("current_investments", 0.0)
    bs.setdefault("share_capital", 0.0)
    bs.setdefault("reserves", 0.0)
    bs.setdefault("bank_debt_fixed", 0.0)
    bs.setdefault("bank_debt_current", 0.0)

    inc.setdefault("sales_revenue", 0.0)
    inc.setdefault("variation_finished_goods", 0.0)
    inc.setdefault("purchase_raw_materials", 0.0)
    inc.setdefault("variation_raw_materials", 0.0)
    inc.setdefault("personnel_cost", 0.0)
    inc.setdefault("depreciation", 0.0)
    inc.setdefault("interest", 0.0)
    inc.setdefault("value_added", 0.0)
    inc.setdefault("ebitda", 0.0)
    inc.setdefault("operating_income", 0.0)
    inc.setdefault("profit", 0.0)

    cf.setdefault("inflows_from_customers", 0.0)
    cf.setdefault("outflows_to_suppliers", 0.0)
    cf.setdefault("outflows_for_personnel", 0.0)
    cf.setdefault("cash_interest", 0.0)
    cf.setdefault("cash_promotion", 0.0)
    cf.setdefault("cash_capacity", 0.0)
    cf.setdefault("cash_research", 0.0)
    cf.setdefault("debt_acquisition", 0.0)
    cf.setdefault("debt_payment", 0.0)

    return company


def save_turn_memory(player, turn_number, decisions):
    player.setdefault("history", {})

    company_snapshot = copy.deepcopy(player.get("company", {}))
    products_snapshot = copy.deepcopy(player.get("products", {}))
    costs_snapshot = copy.deepcopy(player.get("costs", {}))
    sales_snapshot = copy.deepcopy(player.get("sales", {"A": 0.0, "B": 0.0}))
    report_snapshot = copy.deepcopy(company_snapshot.get("report", {}))

    player["history"][str(turn_number)] = {
        "leve": copy.deepcopy(decisions),
        "azienda": company_snapshot,
        "prodotti": products_snapshot,
        "costi": costs_snapshot,
        "sales": sales_snapshot,
        "report": report_snapshot,
    }


def get_previous_turn_state(player, current_turn):
    previous_turn = str(current_turn - 1)
    history = player.get("history", {})

    if previous_turn in history:
        return (
            copy.deepcopy(history[previous_turn].get("azienda", {})),
            copy.deepcopy(history[previous_turn].get("prodotti", {})),
        )

    return (
        copy.deepcopy(player.get("company", {})),
        copy.deepcopy(player.get("products", {})),
    )


def genera_andamento_mercato_realistico(mercato_iniziale, mercato_finale, numero_turni=8, volatilita=0.40):
    mercato_iniziale = safe_float(mercato_iniziale, 0)
    mercato_finale = safe_float(mercato_finale, 0)

    if numero_turni <= 1:
        return [round(mercato_iniziale, 2)]

    andamento = [round(mercato_iniziale, 2)]
    differenza_totale = mercato_finale - mercato_iniziale
    passo_medio = differenza_totale / (numero_turni - 1)

    for turno in range(1, numero_turni - 1):
        valore_lineare = mercato_iniziale + passo_medio * turno
        oscillazione_massima = abs(passo_medio) * volatilita
        oscillazione = random.uniform(-oscillazione_massima, oscillazione_massima)
        andamento.append(round(valore_lineare + oscillazione, 2))

    andamento.append(round(mercato_finale, 2))
    return andamento


def valore_mercato_per_turno(valori_mercato, turno_index):
    if not valori_mercato or turno_index < 0 or turno_index >= len(valori_mercato):
        return 0.0
    return safe_float(valori_mercato[turno_index], 0)


def pesi_percentuali(percentuali):
    percentuali = list(percentuali or [0, 0, 0])

    while len(percentuali) < 3:
        percentuali.append(0)

    return (
        safe_float(percentuali[0], 0) / 100,
        safe_float(percentuali[1], 0) / 100,
        safe_float(percentuali[2], 0) / 100,
    )


def mercato(percentuali_mercato_a, percentuali_mercato_b, valori_mercato_a, valori_mercato_b, players, current_turn):
    turno_index = current_turn - 1

    peso_prezzo_a, peso_visibilita_a, peso_ricerca_a = pesi_percentuali(percentuali_mercato_a)
    peso_prezzo_b, peso_visibilita_b, peso_ricerca_b = pesi_percentuali(percentuali_mercato_b)

    mercato_a = int(round(valore_mercato_per_turno(valori_mercato_a, turno_index)))
    mercato_b = int(round(valore_mercato_per_turno(valori_mercato_b, turno_index)))

    classifica_a = []
    classifica_b = []

    for player in players:
        nome_azienda = player.get("company_name", "Azienda sconosciuta")
        products = player.get("products", {})

        prodotto_a = products.get("A", {})
        prodotto_b = products.get("B", {})

        prezzo_a = safe_float(prodotto_a.get("price", 0), 0)
        prezzo_b = safe_float(prodotto_b.get("price", 0), 0)

        visibilita_a = safe_float(prodotto_a.get("visibility", 0), 0)
        visibilita_b = safe_float(prodotto_b.get("visibility", 0), 0)

        ricerca_a = safe_float(prodotto_a.get("research", 0), 0)
        ricerca_b = safe_float(prodotto_b.get("research", 0), 0)

        quantita_a = int(safe_float(prodotto_a.get("quantity", 0), 0))
        quantita_b = int(safe_float(prodotto_b.get("quantity", 0), 0))

        indice_totale_a = (
            -peso_prezzo_a * prezzo_a
            + peso_visibilita_a * visibilita_a
            + peso_ricerca_a * ricerca_a
        )

        indice_totale_b = (
            -peso_prezzo_b * prezzo_b
            + peso_visibilita_b * visibilita_b
            + peso_ricerca_b * ricerca_b
        )

        classifica_a.append({
            "player_ref": player,
            "azienda": nome_azienda,
            "indice_totale": round(indice_totale_a, 4),
            "prezzo": prezzo_a,
            "visibilita": visibilita_a,
            "ricerca": ricerca_a,
            "quantita_disponibile": quantita_a,
            "quantita_venduta": 0,
        })

        classifica_b.append({
            "player_ref": player,
            "azienda": nome_azienda,
            "indice_totale": round(indice_totale_b, 4),
            "prezzo": prezzo_b,
            "visibilita": visibilita_b,
            "ricerca": ricerca_b,
            "quantita_disponibile": quantita_b,
            "quantita_venduta": 0,
        })

    classifica_a.sort(key=lambda item: item["indice_totale"], reverse=True)
    classifica_b.sort(key=lambda item: item["indice_totale"], reverse=True)

    mercato_residuo_a = mercato_a
    mercato_residuo_b = mercato_b

    for posizione, item in enumerate(classifica_a, start=1):
        item["posizione"] = posizione

        quantita_disponibile = int(safe_float(item.get("quantita_disponibile", 0), 0))
        quantita_venduta = int(min(quantita_disponibile, mercato_residuo_a))

        item["quantita_venduta"] = quantita_venduta
        mercato_residuo_a = int(max(0, mercato_residuo_a - quantita_venduta))

        player_ref = item.get("player_ref")

        if player_ref is not None:
            player_ref.setdefault("sales", {})
            player_ref.setdefault("products", {})
            player_ref["products"].setdefault("A", {})

            player_ref["sales"]["A"] = quantita_venduta

            player_ref["products"]["A"]["quantity"] = max(
                0,
                int(
                    safe_float(player_ref["products"]["A"].get("quantity", 0), 0)
                    - quantita_venduta
                )
            )

    for posizione, item in enumerate(classifica_b, start=1):
        item["posizione"] = posizione

        quantita_disponibile = int(safe_float(item.get("quantita_disponibile", 0), 0))
        quantita_venduta = int(min(quantita_disponibile, mercato_residuo_b))

        item["quantita_venduta"] = quantita_venduta
        mercato_residuo_b = int(max(0, mercato_residuo_b - quantita_venduta))

        player_ref = item.get("player_ref")

        if player_ref is not None:
            player_ref.setdefault("sales", {})
            player_ref.setdefault("products", {})
            player_ref["products"].setdefault("B", {})

            player_ref["sales"]["B"] = quantita_venduta

            player_ref["products"]["B"]["quantity"] = max(
                0,
                int(
                    safe_float(player_ref["products"]["B"].get("quantity", 0), 0)
                    - quantita_venduta
                )
            )

    for item in classifica_a:
        item.pop("player_ref", None)

    for item in classifica_b:
        item.pop("player_ref", None)

    return {
        "mercato_a": int(mercato_a),
        "mercato_b": int(mercato_b),
        "mercato_residuo_a": int(mercato_residuo_a),
        "mercato_residuo_b": int(mercato_residuo_b),
        "classifica_a": classifica_a,
        "classifica_b": classifica_b,
    }


def aggiorna_costi_e_flussi_turno(player, decisions, settings):
    company = player.get("company", {})
    products = player.get("products", {})
    sales = player.get("sales", {"A": 0, "B": 0})
    costs = player.get("costs", default_costs())

    venduto_a = safe_float(sales.get("A", 0), 0)
    venduto_b = safe_float(sales.get("B", 0), 0)

    prezzo_a = safe_float(products.get("A", {}).get("price", 0), 0)
    prezzo_b = safe_float(products.get("B", {}).get("price", 0), 0)

    ricavi = venduto_a * prezzo_a + venduto_b * prezzo_b

    quantita_acquisti = safe_float(
        decisions.get("Approvvigionamento_Quantità", 0),
        0
    )

    costo_acquisto_unitario = safe_float(
        settings.get("purchase_cost", 0),
        0
    )

    costo_acquisti = quantita_acquisti * costo_acquisto_unitario

    personale = safe_float(company.get("personnel", 0), 0)

    straordinari = safe_float(
        decisions.get("Risorse umane_Straordinari", 0),
        0
    )

    costo_personale = personale * 3840 + straordinari * 12

    promozione_a = safe_float(
        decisions.get("Marketing_Prodotto A_Promozione", 0),
        0
    )

    promozione_b = safe_float(
        decisions.get("Marketing_Prodotto B_Promozione", 0),
        0
    )

    investimento_capacita = safe_float(
        decisions.get("Produzione_Investimento capacità", 0),
        0
    )

    ricerca_a = safe_float(
        decisions.get("Ricerca e sviluppo_Prodotto A_Ricerca prodotto", 0),
        0
    )

    ricerca_b = safe_float(
        decisions.get("Ricerca e sviluppo_Prodotto B_Ricerca prodotto", 0),
        0
    )

    finanziamento = safe_float(
        decisions.get("Finanza_Richiesta di finanziamento", 0),
        0
    )

    interessi = safe_float(
        settings.get("interests", 0),
        0
    )

    costs["ricavi"] = round(ricavi, 2)
    costs["costo_acquisti"] = round(costo_acquisti, 2)
    costs["costo_personale"] = round(costo_personale, 2)
    costs["promozione"] = round(promozione_a + promozione_b, 2)
    costs["capacita"] = round(investimento_capacita, 2)
    costs["ricerca"] = round(ricerca_a + ricerca_b, 2)
    costs["finanziamento"] = round(finanziamento, 2)
    costs["interessi"] = round(interessi, 2)
    costs["quantita_acquisti"] = round(quantita_acquisti, 2)

    report = company.setdefault("report", {})
    cf = report.setdefault("cash_flow", {})

    cf["inflows_from_customers"] = round(ricavi, 2)
    cf["outflows_to_suppliers"] = round(costo_acquisti, 2)
    cf["outflows_for_personnel"] = round(costo_personale, 2)
    cf["cash_promotion"] = round(promozione_a + promozione_b, 2)
    cf["cash_capacity"] = round(investimento_capacita, 2)
    cf["cash_research"] = round(ricerca_a + ricerca_b, 2)
    cf["debt_acquisition"] = round(finanziamento, 2)
    cf.setdefault("debt_payment", 0.0)

    company["report"] = report
    player["company"] = company
    player["costs"] = costs

    return player


def aggiorna_conto_economico_turno(player, decisions, settings, dati_iniziali_turno):
    company = player.get("company", {})
    products = player.get("products", {})
    sales = player.get("sales", {"A": 0, "B": 0})

    report = company.setdefault("report", {})
    inc = report.setdefault("income_statement", {})

    costo_acquisto = safe_float(settings.get("purchase_cost", 0), 0)

    venduto_a = safe_float(sales.get("A", 0), 0)
    venduto_b = safe_float(sales.get("B", 0), 0)

    prezzo_a = safe_float(products.get("A", {}).get("price", 0), 0)
    prezzo_b = safe_float(products.get("B", {}).get("price", 0), 0)

    quantita_finale_a = safe_float(products.get("A", {}).get("quantity", 0), 0)
    quantita_finale_b = safe_float(products.get("B", {}).get("quantity", 0), 0)

    quantita_iniziale_a = safe_float(
        dati_iniziali_turno.get("quantity_a", 0),
        0
    )

    quantita_iniziale_b = safe_float(
        dati_iniziali_turno.get("quantity_b", 0),
        0
    )

    magazzino_mp_iniziale_fisico = safe_float(
        dati_iniziali_turno.get("raw_material_inventory", 0),
        0
    )

    magazzino_mp_finale_fisico = safe_float(
        company.get("raw_material_inventory", 0),
        0
    )

    produzione_oraria_a = safe_float(
        products.get("A", {}).get("production_per_hour", 0),
        0
    )

    produzione_oraria_b = safe_float(
        products.get("B", {}).get("production_per_hour", 0),
        0
    )

    costo_unitario_a = costo_acquisto
    costo_unitario_b = costo_acquisto

    if produzione_oraria_a > 0:
        costo_unitario_a += 8 / produzione_oraria_a

    if produzione_oraria_b > 0:
        costo_unitario_b += 8 / produzione_oraria_b

    ricavi_vendita = (
        venduto_a * prezzo_a
        + venduto_b * prezzo_b
    )

    variazione_prodotti_finiti = (
        (quantita_finale_a - quantita_iniziale_a) * costo_unitario_a
        + (quantita_finale_b - quantita_iniziale_b) * costo_unitario_b
    )

    variazione_materie_prime = (
        (magazzino_mp_iniziale_fisico - magazzino_mp_finale_fisico)
        * costo_acquisto
    )

    quantita_acquisti = safe_float(
        decisions.get("Approvvigionamento_Quantità", 0),
        0
    )

    acquisto_materie_prime = quantita_acquisti * costo_acquisto

    personale = safe_float(company.get("personnel", 0), 0)

    straordinari = safe_float(
        decisions.get("Risorse umane_Straordinari", 0),
        0
    )

    costo_personale = personale * 3840 + straordinari * 12

    depreciation = safe_float(
        inc.get("depreciation", 0),
        0
    )

    interest = safe_float(
        inc.get("interest", 0),
        0
    )

    value_added = (
        ricavi_vendita
        + variazione_prodotti_finiti
        - acquisto_materie_prime
        - variazione_materie_prime
    )

    ebitda = value_added - costo_personale
    operating_income = ebitda - depreciation
    profit = operating_income - interest

    inc["sales_revenue"] = round(ricavi_vendita, 2)
    inc["variation_finished_goods"] = round(variazione_prodotti_finiti, 2)
    inc["purchase_raw_materials"] = round(acquisto_materie_prime, 2)
    inc["variation_raw_materials"] = round(variazione_materie_prime, 2)
    inc["personnel_cost"] = round(costo_personale, 2)
    inc["value_added"] = round(value_added, 2)
    inc["ebitda"] = round(ebitda, 2)
    inc["operating_income"] = round(operating_income, 2)
    inc["profit"] = round(profit, 2)

    company["report"] = report
    player["company"] = company

    return player


def aggiorna_capitale_turno(player, decisions, settings):
    company = player.get("company", {})
    products = player.get("products", {})
    sales = player.get("sales", {"A": 0, "B": 0})

    capitale_iniziale_turno = safe_float(company.get("capital", 0), 0)

    finanziamento = safe_float(
        decisions.get("Finanza_Richiesta di finanziamento", 0),
        0
    )

    promozione_a = safe_float(
        decisions.get("Marketing_Prodotto A_Promozione", 0),
        0
    )

    promozione_b = safe_float(
        decisions.get("Marketing_Prodotto B_Promozione", 0),
        0
    )

    investimento_capacita = safe_float(
        decisions.get("Produzione_Investimento capacità", 0),
        0
    )

    ricerca_a = safe_float(
        decisions.get("Ricerca e sviluppo_Prodotto A_Ricerca prodotto", 0),
        0
    )

    ricerca_b = safe_float(
        decisions.get("Ricerca e sviluppo_Prodotto B_Ricerca prodotto", 0),
        0
    )

    personale = safe_float(
        company.get("personnel", 0),
        0
    )

    straordinari = safe_float(
        decisions.get("Risorse umane_Straordinari", 0),
        0
    )

    quantita_acquisti = safe_float(
        decisions.get("Approvvigionamento_Quantità", 0),
        0
    )

    costo_acquisti = safe_float(
        settings.get("purchase_cost", 0),
        0
    )

    venduto_a = safe_float(sales.get("A", 0), 0)
    venduto_b = safe_float(sales.get("B", 0), 0)

    prezzo_a = safe_float(
        products.get("A", {}).get("price", 0),
        0
    )

    prezzo_b = safe_float(
        products.get("B", {}).get("price", 0),
        0
    )

    ricavi = venduto_a * prezzo_a + venduto_b * prezzo_b

    nuovo_capitale = (
        capitale_iniziale_turno
        + finanziamento
        - promozione_a
        - promozione_b
        - investimento_capacita
        - ricerca_a
        - ricerca_b
        - personale * 3840
        - straordinari * 12
        - quantita_acquisti * costo_acquisti
        + ricavi
    )

    company["capital"] = round(nuovo_capitale, 2)
    player["company"] = company

    return player


def aggiorna_stato_patrimoniale_turno(
    player,
    decisions,
    settings,
    dati_iniziali_turno,
    current_turn
):
    company = player.setdefault("company", {})
    products = player.setdefault("products", {})
    sales = player.setdefault(
        "sales",
        {"A": 0, "B": 0}
    )

    report = company.setdefault("report", {})
    bs = report.setdefault("balance_sheet", {})
    inc = report.setdefault("income_statement", {})

    costo_acquisto = safe_float(
        settings.get("purchase_cost", 0),
        0
    )

    previous_bs = dati_iniziali_turno.get(
        "balance_sheet",
        {}
    )

    # ==================================================
    # VALORI DEL TURNO PRECEDENTE
    # ==================================================

    magazzino_pf_precedente = safe_float(
        previous_bs.get(
            "finished_goods_inventory",
            0
        ),
        0
    )

    if current_turn == 1:
        # Al turno 1 si parte dalla quantità iniziale
        # moltiplicata per il costo unitario.
        magazzino_mp_precedente_valore = (
            safe_float(
                settings.get(
                    "initial_raw_material_inventory",
                    0
                ),
                0
            )
            *
            costo_acquisto
        )
    else:
        # Dai turni successivi si usa il valore economico
        # dello Stato Patrimoniale precedente.
        magazzino_mp_precedente_valore = safe_float(
            previous_bs.get(
                "raw_material_inventory",
                0
            ),
            0
        )

    # ==================================================
    # LEVE DEL TURNO
    # ==================================================

    investimento_capacita = safe_float(
        decisions.get(
            "Produzione_Investimento capacità",
            0
        ),
        0
    )

    ricerca_a = safe_float(
        decisions.get(
            "Ricerca e sviluppo_Prodotto A_Ricerca prodotto",
            0
        ),
        0
    )

    ricerca_b = safe_float(
        decisions.get(
            "Ricerca e sviluppo_Prodotto B_Ricerca prodotto",
            0
        ),
        0
    )

    promozione_a = safe_float(
        decisions.get(
            "Marketing_Prodotto A_Promozione",
            0
        ),
        0
    )

    promozione_b = safe_float(
        decisions.get(
            "Marketing_Prodotto B_Promozione",
            0
        ),
        0
    )

    quantita_acquisti = safe_float(
        decisions.get(
            "Approvvigionamento_Quantità",
            0
        ),
        0
    )

    quantita_prod_a = safe_float(
        decisions.get(
            "Produzione_Quantità prodotto A",
            0
        ),
        0
    )

    quantita_prod_b = safe_float(
        decisions.get(
            "Produzione_Quantità prodotto B",
            0
        ),
        0
    )

    finanziamento = safe_float(
        decisions.get(
            "Finanza_Richiesta di finanziamento",
            0
        ),
        0
    )

    # ==================================================
    # VENDITE E COSTO PRODOTTI FINITI
    # ==================================================

    venduto_a = safe_float(
        sales.get("A", 0),
        0
    )

    venduto_b = safe_float(
        sales.get("B", 0),
        0
    )

    produzione_oraria_a = safe_float(
        products.get("A", {}).get(
            "production_per_hour",
            0
        ),
        0
    )

    produzione_oraria_b = safe_float(
        products.get("B", {}).get(
            "production_per_hour",
            0
        ),
        0
    )

    costo_unitario_a = costo_acquisto
    costo_unitario_b = costo_acquisto

    if produzione_oraria_a > 0:
        costo_unitario_a += (
            8 / produzione_oraria_a
        )

    if produzione_oraria_b > 0:
        costo_unitario_b += (
            8 / produzione_oraria_b
        )

    # ==================================================
    # ATTIVO
    # ==================================================

    bs["cash"] = round(
        safe_float(
            company.get("capital", 0),
            0
        ),
        2
    )

    # Manteniamo i valori già calcolati dalle eventuali
    # funzioni che gestiscono ammortamenti e investimenti.
    investimenti_attuali = safe_float(
        bs.get(
            "fixed_investments",
            company.get("fixed_investments", 0)
        ),
        0
    )

    investimenti_correnti_attuali = safe_float(
        bs.get("current_investments", 0),
        0
    )

    bs["fixed_investments"] = round(
        investimenti_attuali
        + investimento_capacita
        + ricerca_a
        + ricerca_b
        + promozione_a
        + promozione_b,
        2
    )

    bs["current_investments"] = round(
        investimenti_correnti_attuali,
        2
    )

    # Valore economico del magazzino MP:
    # valore precedente
    # + acquisti × costo
    # - materie usate × costo.
    bs["raw_material_inventory"] = round(
        magazzino_mp_precedente_valore
        +
        (
            quantita_acquisti
            - quantita_prod_a
            - quantita_prod_b
        )
        * costo_acquisto,
        2
    )

    bs["finished_goods_inventory"] = round(
        magazzino_pf_precedente
        +
        (
            quantita_prod_a
            - venduto_a
        )
        * costo_unitario_a
        +
        (
            quantita_prod_b
            - venduto_b
        )
        * costo_unitario_b,
        2
    )

    bs.setdefault(
        "customer_receivables",
        0.0
    )

    # ==================================================
    # DEBITI
    # ==================================================

    debiti_fissi_attuali = safe_float(
        bs.get("bank_debt_fixed", 0),
        0
    )

    debiti_correnti_attuali = safe_float(
        bs.get("bank_debt_current", 0),
        0
    )

    # Il nuovo finanziamento viene inizialmente aggiunto
    # ai debiti fissi. Le funzioni di rimborso possono poi
    # trasferire o sottrarre le quote.
    bs["bank_debt_fixed"] = round(
        debiti_fissi_attuali
        + finanziamento,
        2
    )

    bs["bank_debt_current"] = round(
        debiti_correnti_attuali,
        2
    )

    # ==================================================
    # CAPITALE SOCIALE
    # ==================================================

    capitale_sociale = (
        safe_float(
            settings.get("initial_capital", 0),
            0
        )
        +
        safe_float(
            settings.get(
                "initial_raw_material_inventory",
                0
            ),
            0
        )
        *
        costo_acquisto
    )

    # Il capitale sociale rimane fisso.
    bs["share_capital"] = round(
        capitale_sociale,
        2
    )

    # ==================================================
    # RISERVE
    # ==================================================

    utile_corrente = safe_float(
        inc.get("profit", 0),
        0
    )

    if current_turn == 1:
        # Riserve 1 = utile 1
        riserve = utile_corrente

    else:
        history = player.get(
            "history",
            {}
        )

        previous_turn = history.get(
            str(current_turn - 1),
            {}
        )

        precedente_bs_storico = (
            previous_turn
            .get("azienda", {})
            .get("report", {})
            .get("balance_sheet", {})
        )

        riserve_precedenti = safe_float(
            precedente_bs_storico.get(
                "reserves",
                0
            ),
            0
        )

        # Riserve t = riserve t-1 + utile t
        riserve = (
            riserve_precedenti
            + utile_corrente
        )

    bs["reserves"] = round(
        riserve,
        2
    )

    # ==================================================
    # SALVATAGGIO
    # ==================================================

    company["report"] = report
    player["company"] = company

    return player



@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/create_room", methods=["POST"])
def create_room():
    data = request.get_json(force=True)
    password = data.get("password", "").strip()

    if password != DEFAULT_ADMIN_PASSWORD:
        return jsonify({
            "success": False,
            "message": "Password admin non valida."
        }), 401

    with rooms_lock:
        room_code = generate_room_code()
        rooms[room_code] = {
            "room_code": room_code,
            "admin_password": password,
            "status": "waiting",
            "turn": 1,
            "max_turns": MAX_TURNS,
            "settings_ready": False,
            "players_initialized": False,
            "settings": default_room_settings(),
            "players": [],
        }

    return jsonify({
        "success": True,
        "room_code": room_code,
        "message": "Stanza creata con successo."
    }), 200


@app.route("/room/<room_code>", methods=["GET"])
def get_room(room_code):
    room_code = room_code.strip().upper()

    with rooms_lock:
        room = rooms.get(room_code)

        if not room:
            return jsonify({
                "success": False,
                "message": "Stanza non trovata."
            }), 404

        public_room = {k: v for k, v in room.items() if k != "admin_password"}

        return jsonify({
            "success": True,
            "room": public_room
        }), 200


@app.route("/update_room_settings", methods=["POST"])
def update_room_settings():
    data = request.get_json(force=True)
    room_code = data.get("room_code", "").strip().upper()
    password = data.get("password", "").strip()

    with rooms_lock:
        room = rooms.get(room_code)

        if not room:
            return jsonify({
                "success": False,
                "message": "Stanza non trovata."
            }), 404

        if room["admin_password"] != password:
            return jsonify({
                "success": False,
                "message": "Password admin non valida."
            }), 401

        initial_capital = safe_float(data.get("initial_capital", 0), 0)
        initial_raw_material_inventory = safe_int(data.get("initial_raw_material_inventory", 0), 0)
        initial_capacity = safe_int(data.get("initial_capacity", 100), 100)
        initial_personnel = safe_int(data.get("initial_personnel", 5), 5)

        if initial_capital <= 0:
            return jsonify({
                "success": False,
                "message": "Il capitale iniziale deve essere maggiore di 0."
            }), 400

        market_initial_a = str(data.get("market_initial_a", "")).strip()
        market_initial_b = str(data.get("market_initial_b", "")).strip()
        market_final_a = str(data.get("market_final_a", "")).strip()
        market_final_b = str(data.get("market_final_b", "")).strip()

        if not market_initial_a or not market_initial_b or not market_final_a or not market_final_b:
            return jsonify({
                "success": False,
                "message": "Inserire mercato iniziale e finale per A e B."
            }), 400

        percentages_a = [
            safe_float(x, 0)
            for x in data.get("market_variable_percentages_a", [0, 0, 0])[:3]
        ]
        percentages_b = [
            safe_float(x, 0)
            for x in data.get("market_variable_percentages_b", [0, 0, 0])[:3]
        ]

        while len(percentages_a) < 3:
            percentages_a.append(0)

        while len(percentages_b) < 3:
            percentages_b.append(0)

        if sum(percentages_a) != 100:
            return jsonify({
                "success": False,
                "message": (
                    "La somma delle 3 percentuali variabili di mercato di A deve essere 100. "
                    f"Somma attuale: {sum(percentages_a)}."
                )
            }), 400

        if sum(percentages_b) != 100:
            return jsonify({
                "success": False,
                "message": (
                    "La somma delle 3 percentuali variabili di mercato di B deve essere 100. "
                    f"Somma attuale: {sum(percentages_b)}."
                )
            }), 400

        was_ready = room.get("settings_ready", False)

        room["settings"] = {
            "initial_capital": initial_capital,
            "initial_raw_material_inventory": initial_raw_material_inventory,
            "initial_capacity": initial_capacity,
            "initial_personnel": initial_personnel,
            "market_initial_a": market_initial_a,
            "market_initial_b": market_initial_b,
            "market_final_a": market_final_a,
            "market_final_b": market_final_b,
            "market_variable_percentages_a": percentages_a,
            "market_variable_percentages_b": percentages_b,
            "market_values_a": genera_andamento_mercato_realistico(
                market_initial_a,
                market_final_a,
                MAX_TURNS
            ),
            "market_values_b": genera_andamento_mercato_realistico(
                market_initial_b,
                market_final_b,
                MAX_TURNS
            ),
            "interests": safe_float(data.get("interests", 0), 0),
            "purchase_cost": safe_float(data.get("purchase_cost", 0), 0),
            "production_time_a": safe_int(data.get("production_time_a", 0), 0),
            "production_time_b": safe_int(data.get("production_time_b", 0), 0),
            "investment_visibility_ratio_a": safe_float(data.get("investment_visibility_ratio_a", 0), 0),
            "investment_visibility_ratio_b": safe_float(data.get("investment_visibility_ratio_b", 0), 0),
            "innovation_internal_research_ratio_a": safe_float(data.get("innovation_internal_research_ratio_a", 0), 0),
            "innovation_coproj_research_ratio_a": safe_float(data.get("innovation_coproj_research_ratio_a", 0), 0),
            "innovation_internal_research_ratio_b": safe_float(data.get("innovation_internal_research_ratio_b", 0), 0),
            "innovation_coproj_research_ratio_b": safe_float(data.get("innovation_coproj_research_ratio_b", 0), 0),
            "investment_capacity_ratio": safe_float(data.get("investment_capacity_ratio", 0), 0),
        }

        room["settings_ready"] = True

        if not was_ready and not room.get("players_initialized", False):
            for player in room["players"]:
                player["company"] = default_company(
                    initial_capital,
                    initial_raw_material_inventory,
                    initial_capacity,
                    initial_personnel,
                    room["settings"]["purchase_cost"]
                )
                player["products"] = default_products(
                    room["settings"]["production_time_a"],
                    room["settings"]["production_time_b"]
                )
                player["costs"] = default_costs()
                player["sales"] = {"A": 0.0, "B": 0.0}
                player["history"] = {}

            room["players_initialized"] = True

    return jsonify({
        "success": True,
        "message": "Parametri stanza aggiornati."
    }), 200


@app.route("/join_room", methods=["POST"])
def join_room():
    data = request.get_json(force=True)
    room_code = data.get("room_code", "").strip().upper()
    company_name = data.get("company_name", "").strip()

    if not company_name:
        return jsonify({
            "success": False,
            "message": "Inserisci un nome azienda."
        }), 400

    with rooms_lock:
        room = rooms.get(room_code)

        if not room:
            return jsonify({
                "success": False,
                "message": "Codice stanza non valido."
            }), 404

        if not room.get("settings_ready", False):
            return jsonify({
                "success": False,
                "message": "La stanza non è ancora pronta: l'admin deve prima salvare i parametri."
            }), 400

        existing_names = [p["company_name"].lower() for p in room["players"]]

        if company_name.lower() in existing_names:
            return jsonify({
                "success": False,
                "message": "Nome azienda già presente nella stanza."
            }), 400

        s = room["settings"]

        player_data = {
            "company_name": company_name,
            "company": default_company(
                s["initial_capital"],
                s["initial_raw_material_inventory"],
                s["initial_capacity"],
                s["initial_personnel"],
                s["purchase_cost"]
            ),
            "products": default_products(
                s["production_time_a"],
                s["production_time_b"]
            ),
            "costs": default_costs(),
            "sales": {"A": 0.0, "B": 0.0},
            "connected": True,
            "current_turn": 1,
            "choices_confirmed": False,
            "game_finished": False,
            "decisions_by_turn": {},
            "history": {},
        }

        room["players"].append(player_data)

    return jsonify({
        "success": True,
        "message": "Ingresso in stanza effettuato.",
        "player": player_data,
        "room_code": room_code
    }), 200


def calcola_classifica_generale_turno(room, current_turn):
    risultati_mercato = room.get("market_results", {})
    mercato_a = safe_float(risultati_mercato.get("mercato_a", 0), 0)
    mercato_b = safe_float(risultati_mercato.get("mercato_b", 0), 0)

    classifica = []

    for player in room.get("players", []):
        nome_azienda = player.get("company_name", "Azienda sconosciuta")
        sales = player.get("sales", {"A": 0, "B": 0})
        company = player.get("company", {})
        report = company.get("report", {})
        inc = report.get("income_statement", {})
        bs = report.get("balance_sheet", {})

        venduto_a = safe_float(sales.get("A", 0), 0)
        venduto_b = safe_float(sales.get("B", 0), 0)

        quota_a = venduto_a / mercato_a if mercato_a > 0 else 0
        quota_b = venduto_b / mercato_b if mercato_b > 0 else 0

        quota_mercato = (quota_a + quota_b)/2

        utile = safe_float(inc.get("profit", 0), 0)
        patrimonio_netto = (safe_float(bs.get("share_capital", 0), 0)+safe_float(bs.get("reserves", 0), 0))

        roe = utile / patrimonio_netto if patrimonio_netto != 0 else 0
        
        roe=round(roe,2)

        punteggio = 0.7 * quota_mercato + 0.3 * roe

        classifica.append({
            "azienda": nome_azienda,
            "quota_mercato": round(quota_mercato, 4),
            "roe": round(roe, 4),
            "punteggio": round(punteggio, 4),
            "venduto_a": int(venduto_a),
            "venduto_b": int(venduto_b),
        })

    classifica.sort(key=lambda x: x["punteggio"], reverse=True)

    for posizione, item in enumerate(classifica, start=1):
        item["posizione"] = posizione

    room.setdefault("ranking_by_turn", {})
    room["ranking_by_turn"][str(current_turn)] = classifica
    room["current_ranking"] = classifica

    return classifica


def aggiorna_finanziamenti(player, current_turn, settings):
    company = player.get("company", {})
    report = company.setdefault("report", {})
    bs = report.setdefault("balance_sheet", {})
    inc = report.setdefault("income_statement", {})
    cf = report.setdefault("cash_flow", {})

    company.setdefault("finanziamenti_attivi", [])

    debiti = safe_float(bs.get("bank_debt_fixed", 0), 0)
    debiti_correnti = safe_float(bs.get("bank_debt_current", 0), 0)
    capitale = safe_float(company.get("capital", 0), 0)

    interessi_totali_turno = 0.0
    pagamento_debiti_turno = 0.0

    finanziamenti_aggiornati = []

    for finanziamento in company.get("finanziamenti_attivi", []):
        importo = safe_float(finanziamento.get("importo", 0), 0)
        turno_erogazione = safe_int(finanziamento.get("turno_erogazione", 0), 0)
        tasso_interesse = safe_float(finanziamento.get("tasso_interesse", 0), 0)

        quota = importo / 4
        interesse_turno = importo * (tasso_interesse / 100)

        distanza = current_turn - turno_erogazione

        if distanza == 1:
            debiti -= quota
            debiti_correnti += quota
            finanziamenti_aggiornati.append(finanziamento)

        elif distanza in [2, 3, 4]:
            debiti -= quota
            capitale -= quota
            capitale -= interesse_turno
            interessi_totali_turno += interesse_turno
            finanziamenti_aggiornati.append(finanziamento)
            pagamento_debiti_turno += quota

        elif distanza == 5:
            debiti_correnti -= quota
            capitale -= quota
            capitale -= interesse_turno
            interessi_totali_turno += interesse_turno
            pagamento_debiti_turno += quota

        elif distanza < 5:
            finanziamenti_aggiornati.append(finanziamento)

    bs["bank_debt_fixed"] = round(max(0, debiti), 2)
    bs["bank_debt_current"] = round(max(0, debiti_correnti), 2)

    company["capital"] = round(capitale, 2)
    bs["cash"] = round(capitale, 2)

    inc["interest"] = round(interessi_totali_turno, 2)
    cf["cash_interest"] = round(interessi_totali_turno, 2)
    cf["debt_payment"] = round(pagamento_debiti_turno, 2)


    company["finanziamenti_attivi"] = finanziamenti_aggiornati
    player["company"] = company

    return player


def aggiorna_investimenti_pluriennali(player, current_turn):
    company = player.get("company", {})
    report = company.setdefault("report", {})
    bs = report.setdefault("balance_sheet", {})
    inc = report.setdefault("income_statement", {})

    company.setdefault("investimenti_attivi", [])

    investimenti = safe_float(bs.get("fixed_investments", 0), 0)
    investimenti_correnti = safe_float(bs.get("current_investments", 0), 0)

    ammortamenti_turno = 0.0
    investimenti_aggiornati = []

    for investimento in company.get("investimenti_attivi", []):
        importo = safe_float(investimento.get("importo", 0), 0)
        turno_investimento = safe_int(investimento.get("turno_investimento", 0), 0)

        quota = importo / 4
        distanza = current_turn - turno_investimento

        if distanza == 1:
            investimenti -= quota
            investimenti_correnti += quota
            investimenti_aggiornati.append(investimento)

        elif distanza in [2, 3, 4]:
            investimenti -= quota
            ammortamenti_turno += quota
            investimenti_aggiornati.append(investimento)

        elif distanza == 5:
            investimenti_correnti -= quota
            ammortamenti_turno += quota

        elif distanza < 5:
            investimenti_aggiornati.append(investimento)

    bs["fixed_investments"] = round(max(0, investimenti), 2)
    bs["current_investments"] = round(max(0, investimenti_correnti), 2)

    inc["depreciation"] = round(ammortamenti_turno, 2)

    company["investimenti_attivi"] = investimenti_aggiornati
    player["company"] = company

    return player




@app.route("/end_game", methods=["POST"])
def end_game():
    data = request.get_json(force=True)
    room_code = data.get("room_code", "").strip().upper()
    company_name = data.get("company_name", "").strip()

    with rooms_lock:
        room = rooms.get(room_code)

        if not room:
            return jsonify({"success": False, "message": "Stanza non trovata."}), 404

        player = next(
            (p for p in room.get("players", []) if p.get("company_name", "").lower() == company_name.lower()),
            None
        )

        if not player:
            return jsonify({"success": False, "message": "Giocatore non trovato nella stanza."}), 404

        max_turns = room.get("max_turns", MAX_TURNS)

        if player.get("current_turn", 1) <= max_turns:
            return jsonify({
                "success": False,
                "message": "Non puoi terminare la partita prima della fine dell'ultimo turno."
            }), 400

        player["game_finished"] = True
        player["choices_confirmed"] = True

        return jsonify({
            "success": True,
            "message": "Partita terminata correttamente. Non puoi più modificare le scelte.",
            "current_turn": player.get("current_turn", max_turns + 1),
            "max_turns": max_turns,
            "company": player.get("company", {}),
            "products": player.get("products", {}),
            "costs": player.get("costs", {}),
            "sales": player.get("sales", {"A": 0.0, "B": 0.0}),
            "history": player.get("history", {}),
            "market_results": room.get("market_results", {}),
            "market_results_by_turn": room.get("market_results_by_turn", {}),
            "current_ranking": room.get("current_ranking", []),
            "ranking_by_turn": room.get("ranking_by_turn", {}),
            "game_finished": True,
            "choices_confirmed": True,
        }), 200


def programma_ricerca_interna(
    player,
    prodotto,
    importo,
    rapporto,
    turno_investimento
):
    """
    Registra una ricerca interna che produrrà il proprio effetto
    al turno t+2.
    """

    importo = safe_float(importo, 0)
    rapporto = safe_float(rapporto, 0)
    turno_investimento = safe_int(turno_investimento, 1)

    if prodotto not in ("A", "B"):
        return player

    if importo <= 0 or rapporto <= 0:
        return player

    incremento = importo / rapporto
    turno_applicazione = turno_investimento + 1

    company = player.setdefault("company", {})
    ricerche_attive = company.setdefault(
        "ricerche_interne_attive",
        []
    )

    # Se il giocatore riconferma lo stesso turno, sostituiamo
    # il progetto precedente invece di duplicarlo.
    ricerche_attive = [
        ricerca
        for ricerca in ricerche_attive
        if not (
            ricerca.get("prodotto") == prodotto
            and safe_int(
                ricerca.get("turno_investimento", 0),
                0
            ) == turno_investimento
        )
    ]

    ricerche_attive.append({
        "prodotto": prodotto,
        "importo": round(importo, 2),
        "rapporto": round(rapporto, 6),
        "incremento": round(incremento, 2),
        "turno_investimento": turno_investimento,
        "turno_applicazione": turno_applicazione
    })

    company["ricerche_interne_attive"] = ricerche_attive
    player["company"] = company

    return player


def applica_ricerche_interne_maturate(player, current_turn):
    """
    Applica una sola volta le ricerche interne il cui turno
    di applicazione è uguale al turno corrente.
    """

    current_turn = safe_int(current_turn, 1)

    company = player.setdefault("company", {})
    products = player.setdefault("products", {})

    products.setdefault("A", {})
    products.setdefault("B", {})

    ricerche_attive = company.setdefault(
        "ricerche_interne_attive",
        []
    )

    ricerche_ancora_attive = []

    for ricerca in ricerche_attive:
        prodotto = ricerca.get("prodotto")
        turno_applicazione = safe_int(
            ricerca.get("turno_applicazione", 0),
            0
        )

        if prodotto not in ("A", "B"):
            continue

        if turno_applicazione <= current_turn:
            incremento = safe_float(
                ricerca.get("incremento", 0),
                0
            )

            ricerca_attuale = safe_float(
                products[prodotto].get("research", 0),
                0
            )

            products[prodotto]["research"] = round(
                ricerca_attuale + incremento,
                2
            )

        else:
            ricerche_ancora_attive.append(ricerca)

    company["ricerche_interne_attive"] = (
        ricerche_ancora_attive
    )

    player["company"] = company
    player["products"] = products

    return player





@app.route("/submit_choices", methods=["POST"])
def submit_choices():
    data = request.get_json(force=True)
    room_code = data.get("room_code", "").strip().upper()
    company_name = data.get("company_name", "").strip()
    decisions = data.get("decisions", {})

    with rooms_lock:
        room = rooms.get(room_code)

        if not room:
            return jsonify({
                "success": False,
                "message": "Stanza non trovata."
            }), 404

        player = next(
            (p for p in room["players"] if p["company_name"].lower() == company_name.lower()),
            None
        )

        if not player:
            return jsonify({
                "success": False,
                "message": "Giocatore non trovato nella stanza."
            }), 404

        if player.get("game_finished", False):
            return jsonify({
                "success": False,
                "message": "La partita è già terminata. Non puoi più modificare le scelte."
            }), 400

        current_turn = player.get("current_turn", 1)
        max_turns = room.get("max_turns", MAX_TURNS)
        


        if current_turn > max_turns:
            return jsonify({
                "success": False,
                "message": "Hai completato gli 8 turni. Premi 'Termina partita' per chiudere il gioco."
            }), 400
        
        # Applica gli effetti delle ricerche interne avviate due turni prima.
        player = applica_ricerche_interne_maturate(
            player,
            current_turn
        )

        if player.get("choices_confirmed", False):
            return jsonify({
                "success": True,
                "message": "Scelte già confermate. In attesa degli altri giocatori.",
                "current_turn": player.get("current_turn", current_turn),
                "max_turns": max_turns,
                "company": player.get("company", {}),
                "products": player.get("products", {}),
                "costs": player.get("costs", {}),
                "sales": player.get("sales", {"A": 0.0, "B": 0.0}),
                "history": player.get("history", {}),
                "market_results": room.get("market_results", {}),
                "market_results_by_turn": room.get("market_results_by_turn", {}),
                "current_ranking": room.get("current_ranking", []),
                "ranking_by_turn": room.get("ranking_by_turn", {}),
                "game_finished": player.get("game_finished", False),
                "choices_confirmed": True,
            }), 200

        s = room["settings"]

        company = player.get(
            "company",
            default_company(
                s["initial_capital"],
                s["initial_raw_material_inventory"],
                s["initial_capacity"],
                s["initial_personnel"],
                s["purchase_cost"]
            )
        )

        products = player.get(
            "products",
            default_products(
                s["production_time_a"],
                s["production_time_b"]
            )
        )

        costs = player.get("costs", default_costs())

        previous_company, previous_products = get_previous_turn_state(player, current_turn)

        player["dati_iniziali_turno"] = {
            "quantity_a": safe_float(products.get("A", {}).get("quantity", 0), 0),
            "quantity_b": safe_float(products.get("B", {}).get("quantity", 0), 0),
            "raw_material_inventory": safe_float(company.get("raw_material_inventory", 0), 0),
            "balance_sheet": copy.deepcopy(
                company.get("report", {}).get("balance_sheet", {})
            )
        }

        player["decisions_by_turn"][str(current_turn)] = copy.deepcopy(decisions)
        
        
        promozione_a = safe_float(
            decisions.get("Marketing_Prodotto A_Promozione", 0),
            0
        )

        promozione_b = safe_float(
            decisions.get("Marketing_Prodotto B_Promozione", 0),
            0
        )

        investimento_capacita = safe_float(
            decisions.get("Produzione_Investimento capacità", 0),
            0
        )

        ricerca_a = safe_float(
            decisions.get("Ricerca e sviluppo_Prodotto A_Ricerca prodotto", 0),
            0
        )

        ricerca_b = safe_float(
            decisions.get("Ricerca e sviluppo_Prodotto B_Ricerca prodotto", 0),
            0
        )

        totale_investimento_pluriennale = (
            promozione_a
            + promozione_b
            + investimento_capacita
            + ricerca_a
            + ricerca_b
        )

        if totale_investimento_pluriennale > 0:
            company.setdefault("investimenti_attivi", [])
            company["investimenti_attivi"].append({
                "importo": totale_investimento_pluriennale,
                "turno_investimento": current_turn
            })
        
        
        finanziamento_richiesto = safe_float(
            decisions.get("Finanza_Richiesta di finanziamento", 0),
            0
        )

        if finanziamento_richiesto > 0:
            company.setdefault("finanziamenti_attivi", [])
            company["finanziamenti_attivi"].append({
                "importo": finanziamento_richiesto,
                "turno_erogazione": current_turn,
                "tasso_interesse": safe_float(s.get("interests", 0), 0)
            })
        
        player["choices_confirmed"] = True

        previous_capacity = safe_float(
            previous_company.get("capacity", s["initial_capacity"]),
            s["initial_capacity"]
        )

        capacity_investment = safe_float(
            decisions.get("Produzione_Investimento capacità", 0),
            0
        )

        capacity_ratio = safe_float(
            s.get("investment_capacity_ratio", 0),
            0
        )

        capacity_increment = (
            capacity_investment / capacity_ratio
            if capacity_investment > 0 and capacity_ratio > 0
            else 0.0
        )

        company["capacity"] = round(previous_capacity + capacity_increment, 2)

        company["personnel"] = safe_int(
            decisions.get(
                "Risorse umane_Personale attuale",
                company.get("personnel", s["initial_personnel"])
            ),
            company.get("personnel", s["initial_personnel"])
        )

        previous_raw_material_inventory = safe_float(
            previous_company.get(
                "raw_material_inventory",
                s.get("initial_raw_material_inventory", 0)
            ),
            s.get("initial_raw_material_inventory", 0)
        )

        supply_quantity = safe_float(
            decisions.get("Approvvigionamento_Quantità", 0),
            0
        )

        produced_quantity_a = safe_float(
            decisions.get("Produzione_Quantità prodotto A", 0),
            0
        )

        produced_quantity_b = safe_float(
            decisions.get("Produzione_Quantità prodotto B", 0),
            0
        )

        available_raw_material_inventory = previous_raw_material_inventory + supply_quantity
        total_produced_quantity = produced_quantity_a + produced_quantity_b

        if total_produced_quantity > available_raw_material_inventory:
            return jsonify({
                "success": False,
                "message": (
                    "Errore produzione: la somma tra Quantità prodotto A e Quantità prodotto B "
                    "non può superare il magazzino materie prime disponibile. "
                    f"Disponibile: {available_raw_material_inventory}, "
                    f"richiesto: {total_produced_quantity}."
                )
            }), 400

        production_per_hour_a = safe_float(
            products["A"].get("production_per_hour", s.get("production_time_a", 0)),
            s.get("production_time_a", 0)
        )

        production_per_hour_b = safe_float(
            products["B"].get("production_per_hour", s.get("production_time_b", 0)),
            s.get("production_time_b", 0)
        )

        if production_per_hour_a <= 0 or production_per_hour_b <= 0:
            return jsonify({
                "success": False,
                "message": (
                    "Errore produzione: il valore P/h di Prodotto A e Prodotto B "
                    "deve essere maggiore di 0."
                )
            }), 400

        required_hours = (
            produced_quantity_a / production_per_hour_a
            + produced_quantity_b / production_per_hour_b
        )

        available_capacity = safe_float(company.get("capacity", 0), 0)

        if required_hours > available_capacity:
            return jsonify({
                "success": False,
                "message": (
                    "Errore produzione: le ore richieste superano la capacità aziendale disponibile. "
                    f"Ore richieste: {round(required_hours, 2)}, "
                    f"capacità disponibile: {available_capacity}."
                )
            }), 400

        overtime = safe_float(
            decisions.get("Risorse umane_Straordinari", 0),
            0
        )

        personnel = safe_float(company.get("personnel", 0), 0)
        available_work_hours = personnel * 480 + overtime

        if required_hours > available_work_hours:
            return jsonify({
                "success": False,
                "message": (
                    "Errore produzione: le ore richieste superano le ore di lavoro disponibili. "
                    f"Ore richieste: {round(required_hours, 2)}, "
                    f"ore disponibili: {available_work_hours}."
                )
            }), 400

        company["raw_material_inventory"] = round(
            available_raw_material_inventory
            - produced_quantity_a
            - produced_quantity_b,
            2
        )

        promotion_a = safe_float(
            decisions.get("Marketing_Prodotto A_Promozione", 0),
            0
        )

        promotion_b = safe_float(
            decisions.get("Marketing_Prodotto B_Promozione", 0),
            0
        )

        previous_visibility_a = safe_float(
            previous_products.get("A", {}).get("visibility", 0),
            0
        )

        previous_visibility_b = safe_float(
            previous_products.get("B", {}).get("visibility", 0),
            0
        )

        ratio_visibility_a = safe_float(
            s.get("investment_visibility_ratio_a", 0),
            0
        )

        ratio_visibility_b = safe_float(
            s.get("investment_visibility_ratio_b", 0),
            0
        )

        visibility_increment_a = (
            promotion_a / ratio_visibility_a
            if promotion_a > 0 and ratio_visibility_a > 0
            else 0.0
        )

        visibility_increment_b = (
            promotion_b / ratio_visibility_b
            if promotion_b > 0 and ratio_visibility_b > 0
            else 0.0
        )

        products["A"]["visibility"] = round(previous_visibility_a + visibility_increment_a, 2)
        products["B"]["visibility"] = round(previous_visibility_b + visibility_increment_b, 2)

        company = process_promotion_investments(company, [promotion_a, promotion_b])

        research_input_a = safe_float(
            decisions.get("Ricerca e sviluppo_Prodotto A_Ricerca prodotto", 0),
            0
        )

        research_input_b = safe_float(
            decisions.get("Ricerca e sviluppo_Prodotto B_Ricerca prodotto", 0),
            0
        )

        research_mode_a = decisions.get(
            "Ricerca e sviluppo_Prodotto A_Ricerca prodotto_modalita",
            products["A"].get("research_mode", "Interna")
        )

        research_mode_b = decisions.get(
            "Ricerca e sviluppo_Prodotto B_Ricerca prodotto_modalita",
            products["B"].get("research_mode", "Interna")
        )

        ratio_research_a = safe_float(
            s.get(
                "innovation_coproj_research_ratio_a"
                if research_mode_a == "Co-progettazione"
                else "innovation_internal_research_ratio_a",
                0
            ),
            0
        )

        ratio_research_b = safe_float(
            s.get(
                "innovation_coproj_research_ratio_b"
                if research_mode_b == "Co-progettazione"
                else "innovation_internal_research_ratio_b",
                0
            ),
            0
        )


# Il valore di partenza contiene già le eventuali ricerche
# interne maturate all'inizio del turno.
        ricerca_attuale_a = safe_float(
            products.get("A", {}).get("research", 0),
            0
        )

        ricerca_attuale_b = safe_float(
            products.get("B", {}).get("research", 0),
            0
        )

        incremento_immediato_a = 0.0
        incremento_immediato_b = 0.0


# -------------------------
# PRODOTTO A
# -------------------------

        if research_mode_a == "Interna":
             rapporto_interno_a = safe_float(
                s.get(
                    "innovation_internal_research_ratio_a",
                    0
                ),
                0
             )

             programma_ricerca_interna(
                player=player,
                prodotto="A",
                importo=research_input_a,
                rapporto=rapporto_interno_a,
                turno_investimento=current_turn
            )

        else:
            rapporto_coprogettazione_a = safe_float(
                s.get(
                    "innovation_coproj_research_ratio_a",
                    0
                ),
                0
            )

            if (
                research_input_a > 0
                and rapporto_coprogettazione_a > 0
            ):
                incremento_immediato_a = (
                    research_input_a
                    / rapporto_coprogettazione_a
                )


# -------------------------
# PRODOTTO B
# -------------------------

        if research_mode_b == "Interna":
            rapporto_interno_b = safe_float(
                s.get(
                    "innovation_internal_research_ratio_b",
                    0
                ),
                0
            )

            programma_ricerca_interna(
                player=player,
                prodotto="B",
                importo=research_input_b,
                rapporto=rapporto_interno_b,
                turno_investimento=current_turn
            )

        else:
            rapporto_coprogettazione_b = safe_float(
                s.get(
                    "innovation_coproj_research_ratio_b",
                    0
                ),
                0
            )

            if (
                 research_input_b > 0
                and rapporto_coprogettazione_b > 0
            ):
                incremento_immediato_b = (
                    research_input_b
                    / rapporto_coprogettazione_b
                 )


        products["A"]["research"] = round(
            ricerca_attuale_a + incremento_immediato_a,
            2
        )

        products["B"]["research"] = round(
            ricerca_attuale_b + incremento_immediato_b,
            2
        )

        products["A"]["research_mode"] = research_mode_a
        products["B"]["research_mode"] = research_mode_b




        price_a = decisions.get("Marketing_Prodotto A_Prezzo", "")
        price_b = decisions.get("Marketing_Prodotto B_Prezzo", "")

        if price_a != "":
            products["A"]["price"] = safe_int(price_a, products["A"].get("price", 0))

        if price_b != "":
            products["B"]["price"] = safe_int(price_b, products["B"].get("price", 0))

        initial_quantity_a = safe_float(
            products.get("A", {}).get("quantity", 0),
            0
        )

        initial_quantity_b = safe_float(
            products.get("B", {}).get("quantity", 0),
            0
        )

        products["A"]["quantity"] = int(initial_quantity_a + produced_quantity_a)
        products["B"]["quantity"] = int(initial_quantity_b + produced_quantity_b)

        products["A"]["production_per_hour"] = safe_int(s.get("production_time_a", 0), 0)
        products["B"]["production_per_hour"] = safe_int(s.get("production_time_b", 0), 0)

        costs = update_costs_from_state(costs, company, products)
        costs["quantita_acquisti"] = supply_quantity

        company = update_cumulative_report(company, costs)

        player["company"] = company
        player["products"] = products
        player["costs"] = costs

        all_players_confirmed = all(
            p.get("choices_confirmed", False)
            and p.get("current_turn", 1) == current_turn
            for p in room.get("players", [])
        )

        if all_players_confirmed:
            risultato_mercato = mercato(
                s.get("market_variable_percentages_a", [0, 0, 0]),
                s.get("market_variable_percentages_b", [0, 0, 0]),
                s.get("market_values_a", []),
                s.get("market_values_b", []),
                room.get("players", []),
                current_turn,
            )
            
            for p in room.get("players", []):
                aggiorna_finanziamenti(p, current_turn, s)
                
            for p in room.get("players", []):
                aggiorna_investimenti_pluriennali(p, current_turn)
            

            for p in room.get("players", []):
                decisioni_player = p.get("decisions_by_turn", {}).get(str(current_turn), {})
                aggiorna_costi_e_flussi_turno(p, decisioni_player, s)

            for p in room.get("players", []):
                decisioni_player = p.get("decisions_by_turn", {}).get(str(current_turn), {})
                dati_iniziali_turno = p.get("dati_iniziali_turno", {})
                aggiorna_conto_economico_turno(
                    p,
                    decisioni_player,
                    s,
                    dati_iniziali_turno
                )

            for p in room.get("players", []):
                decisioni_player = p.get("decisions_by_turn", {}).get(str(current_turn), {})
                aggiorna_capitale_turno(p, decisioni_player, s)

            for p in room.get("players", []):
                decisioni_player = p.get("decisions_by_turn", {}).get(str(current_turn), {})
                dati_iniziali_turno = p.get("dati_iniziali_turno", {})
                aggiorna_stato_patrimoniale_turno(
                    p,
                    decisioni_player,
                    s,
                    dati_iniziali_turno,
                    current_turn
                )
            
            room.setdefault("market_results_by_turn", {})
            room["market_results_by_turn"][str(current_turn)] = risultato_mercato
            room["market_results"] = risultato_mercato
            
            
            
            classifica_generale = calcola_classifica_generale_turno(room, current_turn)

            for p in room.get("players", []):
                p["company"] = update_cumulative_report(
                    p.get("company", {}),
                    p.get("costs", {})
                )

            room.setdefault("market_results_by_turn", {})
            room["market_results_by_turn"][str(current_turn)] = risultato_mercato
            room["market_results"] = risultato_mercato

            for p in room.get("players", []):
                save_turn_memory(
                    p,
                    current_turn,
                    p.get("decisions_by_turn", {}).get(str(current_turn), {})
                )

                if str(current_turn) in p.get("history", {}):
                    p["history"][str(current_turn)]["sales"] = copy.deepcopy(
                        p.get("sales", {"A": 0.0, "B": 0.0})
                    )
                    p["history"][str(current_turn)]["market_results"] = copy.deepcopy(
                        risultato_mercato
                    )

            if current_turn < max_turns:
                for p in room.get("players", []):
                    p["current_turn"] = current_turn + 1
                    p["choices_confirmed"] = False

                room["turn"] = current_turn + 1
                message = (
                    f"Tutti i giocatori hanno confermato. "
                    f"Mercato calcolato. Si passa al turno {current_turn + 1}."
                )
            else:
                for p in room.get("players", []):
                    p["current_turn"] = max_turns + 1
                    p["choices_confirmed"] = True

                room["turn"] = max_turns + 1
                message = (
                    "Tutti i giocatori hanno confermato. "
                    "Mercato finale calcolato. Partita conclusa."
                )

        else:
            message = "Scelte confermate. In attesa degli altri giocatori."

    return jsonify({
        "success": True,
        "message": message,
        "current_turn": player["current_turn"],
        "max_turns": max_turns,
        "company": player["company"],
        "products": player["products"],
        "costs": player.get("costs", {}),
        "sales": player.get("sales", {"A": 0.0, "B": 0.0}),
        "history": player.get("history", {}),
        "market_results": room.get("market_results", {}),
        "market_results_by_turn": room.get("market_results_by_turn", {}),
        "current_ranking": room.get("current_ranking", []),
        "ranking_by_turn": room.get("ranking_by_turn", {}),
        "game_finished": player.get("game_finished", False),
        "choices_confirmed": player.get("choices_confirmed", False),
    }), 200


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)