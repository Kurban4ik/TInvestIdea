"""Build and validate a fictional, offline investor-retrospective dataset.

Run from any directory: python examples/build_demo.py
Python standard library only. No network calls or live account data.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parent
D = Decimal
ASSET = "asset_synx"
SPLIT_DATE = "2025-02-17"
START = "2025-02-03"
END = "2025-03-31"
META = {
    "schema_version": "0.1.0",
    "dataset_id": "synthetic_retrospective_v1",
    "synthetic": True,
    "timezone": "Europe/Moscow",
    "currency": "RUB",
    "warning": "Все компании, торги, новости и операции вымышлены. .invalid — заглушки ссылок.",
}


def money(value):
    return str(D(value).quantize(D("0.01"), rounding=ROUND_HALF_UP))


def days(first, last):
    current = date.fromisoformat(first)
    while current <= date.fromisoformat(last):
        if current.weekday() < 5:
            yield current.isoformat()
        current += timedelta(days=1)


def dump(name, payload):
    (ROOT / name).write_text(
        json.dumps({"meta": META, **payload}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def source(source_id, kind, published_at, path):
    return {
        "source_id": source_id,
        "kind": kind,
        "published_at": published_at,
        "provider_available_at": published_at,
        "ingested_at": "2025-04-01T06:00:00+03:00",
        "uri": "https://demo.invalid/" + path,
    }


def news_item(item_id, timestamp, title, body, kind="issuer_disclosure", **extra):
    item = {
        "news_id": item_id,
        "version": 1,
        "asset_ids": [ASSET],
        "publisher": "Учебная лента SYNX",
        "content_type": kind,
        "title": title,
        "body": body,
        "language": "ru",
        "event_at": timestamp,
        "first_published_at": timestamp,
        "published_at": timestamp,
        "provider_available_at": timestamp,
        "ingested_at": "2025-04-01T06:00:00+03:00",
        "source_id": "src_" + item_id,
        "url": "https://demo.invalid/news/" + item_id,
        "content_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "supersedes": None,
        "duplicate_cluster_id": item_id,
        **extra,
    }
    return item


NEWS = [
    news_item("n_dividend", "2025-01-30T09:00:00+03:00", "Утверждён дивиденд",
              "Утверждена выплата 20 RUB на акцию до сплита, или 10 RUB после сплита 1:2. "
              "Ex-date 3 марта; дата фиксации 4 марта; платёж запланирован на 17 марта."),
    news_item("n_contract", "2025-02-25T08:00:00+03:00", "SYNX заключила контракт",
              "Подписан контракт на 300 млн RUB. Финансовый эффект и рентабельность не раскрыты."),
    news_item("n_contract_copy", "2025-02-25T08:05:00+03:00", "Копия сообщения о контракте",
              "Подписан контракт на 300 млн RUB. Финансовый эффект и рентабельность не раскрыты.",
              kind="news_reprint", duplicate_cluster_id="n_contract"),
    news_item("n_outlook_v1", "2025-03-03T19:15:00+03:00", "Изменён прогноз выручки",
              "Компания снизила прогноз роста выручки на год с 12% до 4%.",
              event_at="2025-03-03T18:55:00+03:00"),
    news_item("n_outlook_v2", "2025-03-05T10:00:00+03:00", "Уточнение прогноза",
              "Прогноз роста выручки снижен с 12% до 6%, а не до 4%, указанных 3 марта.",
              event_at="2025-03-03T18:55:00+03:00",
              version=2, supersedes="n_outlook_v1"),
    news_item("n_opinion", "2025-03-04T20:00:00+03:00", "Мнение аналитика о падении",
              "По мнению автора, участники рынка переоценили перспективы компании.",
              kind="analyst_opinion"),
]


def interpolate_anchors(anchors):
    dates = list(days(START, END))
    positions = {dt: i for i, dt in enumerate(dates)}
    result = {}
    pairs = sorted(anchors.items())
    for (left, left_value), (right, right_value) in zip(pairs, pairs[1:]):
        a, b = positions[left], positions[right]
        for i in range(a, b + 1):
            result[dates[i]] = left_value + (right_value - left_value) * (i - a) / (b - a)
    return result


def make_bars():
    rng = random.Random(7401)
    train_dates = list(days("2024-09-02", "2025-01-31"))
    levels = [[], [], []]
    values = [1000.0, 1000.0, 1000.0]
    for dt in train_dates:
        rm = rng.gauss(0.0003, 0.007)
        sector_excess = rng.gauss(0.0001, 0.005)
        rs = rm + sector_excess
        ry = 0.0001 + 0.8 * rm + 0.35 * sector_excess + rng.gauss(0, 0.003)
        for index, ret in enumerate([ry, rm, rs]):
            values[index] *= 1 + ret
            levels[index].append((dt, values[index]))
    series = {}
    for name, observations in zip([ASSET, "index_market_tr", "index_sector_tr"], levels):
        factor = 1000 / observations[-1][1]
        series[name] = {dt: round(value * factor, 8) for dt, value in observations}

    # Synthetic weekday calendar. Real integration must use the venue calendar.
    # The stock anchors are expressed in post-split units, including pre-split dates.
    post_split_prices = interpolate_anchors({
        START: 500, "2025-02-14": 500, SPLIT_DATE: 500,
        "2025-02-20": 502, "2025-02-24": 505, "2025-02-25": 540,
        "2025-02-28": 530, "2025-03-03": 500, "2025-03-04": 475,
        "2025-03-07": 480, "2025-03-10": 450,
        "2025-03-19": 490, "2025-03-20": 480, END: 510,
    })
    series[ASSET].update({dt: round(value * (2 if dt < SPLIT_DATE else 1), 8)
                         for dt, value in post_split_prices.items()})
    series["index_market_tr"].update(interpolate_anchors({
        START: 1000, "2025-02-24": 1020, "2025-02-25": 1024,
        "2025-03-03": 1025, "2025-03-04": 1020,
        "2025-03-07": 1022, "2025-03-10": 1021,
        "2025-03-20": 1030, END: 1040,
    }))
    series["index_sector_tr"].update(interpolate_anchors({
        START: 1000, "2025-02-24": 1015, "2025-02-25": 1020,
        "2025-03-03": 1018, "2025-03-04": 1010,
        "2025-03-07": 1012, "2025-03-10": 1011,
        "2025-03-20": 1015, END: 1020,
    }))
    # Use the exact persisted price precision for both calculations and output.
    series = {name: {dt: float(f"{price:.8f}") for dt, price in observations.items()}
              for name, observations in series.items()}
    bars = []
    for instrument, observations in series.items():
        for dt, price in sorted(observations.items()):
            bars.append({
                "bar_id": f"bar_{instrument}_{dt}",
                "instrument_id": instrument,
                "session_date": dt,
                "close_at": dt + "T18:45:00+03:00",
                "provider_available_at": dt + "T18:50:00+03:00",
                "ingested_at": "2025-04-01T06:00:00+03:00",
                "close": f"{price:.8f}",
                "price_basis": "raw" if instrument == ASSET else "total_return_index",
                "source_id": "src_market_snapshot",
                "revision": 1,
            })
    return series, bars


def solve(matrix, vector):
    a = [row[:] + [target] for row, target in zip(matrix, vector)]
    for col in range(len(vector)):
        pivot = max(range(col, len(a)), key=lambda row: abs(a[row][col]))
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        if abs(scale) < 1e-15:
            raise ValueError("Singular regression design")
        a[col] = [v / scale for v in a[col]]
        for row in range(len(a)):
            if row != col:
                scale = a[row][col]
                a[row] = [v - scale * p for v, p in zip(a[row], a[col])]
    return [row[-1] for row in a]


def fit_and_detect(series):
    dates = sorted(series[ASSET])
    rows = []
    for previous, current in zip(dates, dates[1:]):
        prev = series[ASSET][previous]
        ratio = 2 if current == SPLIT_DATE else 1
        dividend = 10 if current == "2025-03-03" else 0
        ret = (series[ASSET][current] * ratio + dividend * ratio) / prev - 1
        rm = series["index_market_tr"][current] / series["index_market_tr"][previous] - 1
        rs = series["index_sector_tr"][current] / series["index_sector_tr"][previous] - 1
        rows.append({"date": current, "previous_date": previous, "stock_return": ret, "market_return": rm,
                     "sector_return": rs, "x": [1, rm, rs - rm]})
    train = [row for row in rows if row["date"] < START]
    matrix = [[sum(row["x"][i] * row["x"][j] for row in train)
               for j in range(3)] for i in range(3)]
    vector = [sum(row["x"][i] * row["stock_return"] for row in train) for i in range(3)]
    coefficients = solve(matrix, vector)
    residuals = [row["stock_return"] - sum(a*b for a, b in zip(coefficients, row["x"]))
                 for row in train]
    sigma = math.sqrt(sum(r*r for r in residuals) / (len(train) - 3))
    output = []
    for row in rows:
        if row["date"] < START:
            continue
        expected = sum(a*b for a, b in zip(coefficients, row["x"]))
        residual = row["stock_return"] - expected
        output.append({
            "session_date": row["date"],
            "adjusted_total_return": round(row["stock_return"], 8),
            "market_return": round(row["market_return"], 8),
            "sector_return": round(row["sector_return"], 8),
            "expected_return": round(expected, 8),
            "residual": round(residual, 8),
            "residual_z_score": round(residual / sigma, 4),
            "is_anomaly": abs(residual) >= max(0.02, 3 * sigma),
            "evidence_ids": [f"bar_{name}_{dt}" for name in series
                             for dt in [row["previous_date"], row["date"]]],
            "model_id": "factor_model_01",
            "adjustment_ids": (["ca_split"] if row["date"] == SPLIT_DATE else []) +
                              (["ca_dividend"] if row["date"] == "2025-03-03" else []),
        })
    return {
        "model_id": "factor_model_01",
        "formula": "stock_total_return = alpha + beta_market * market_TR_return + "
                   "beta_sector_excess * (sector_TR_return - market_TR_return) + residual",
        "training_from": train[0]["date"], "training_through": train[-1]["date"],
        "fit_as_of": "2025-02-03T09:00:00+03:00",
        "observations": len(train),
        "coefficients": dict(zip(["alpha", "beta_market", "beta_sector_excess"], coefficients)),
        "residual_sigma": sigma,
        "minimum_absolute_residual": 0.02, "sigma_multiplier": 3,
        "limitations": ["Один учебный OLS; порог не откалиброван на реальном рынке.",
                       "Остаток — необъяснённое моделью движение, а не доказанная причина.",
                       "Замороженное окно до периода; без подгонки по результату позиции."],
    }, output


def trade(op_id, dt, side, quantity, price, fee, reason):
    return {
        "operation_id": op_id, "account_id": "account_demo", "asset_id": ASSET,
        "operation_type": side, "executed_at": dt, "broker_available_at": dt,
        "ingested_at": "2025-04-01T06:00:00+03:00",
        "quantity": str(quantity), "price": money(price), "fee": money(fee),
        "currency": "RUB", "status": "executed", "source_id": "src_broker_snapshot",
        "thesis_id": "thesis_dividend", "user_reason": reason,
    }


TRADES = [
    trade("op_buy_1", "2025-02-03T12:00:00+03:00", "buy", 10, 1000, 10, "dividend_thesis"),
    trade("op_buy_2", "2025-02-25T18:40:00+03:00", "buy", 20, 540, 10.8, "increase_position"),
    trade("op_sell_1", "2025-03-20T14:00:00+03:00", "sell", 10, 480, 4.8,
          "rebalance_to_concentration_limit"),
]


def make_financials(series):
    lots = []
    cash = D("100000")
    bought = sold = fees = realized = dividends = taxes = D(0)
    events = []
    for operation in TRADES:
        events.append((operation["executed_at"], "trade", operation))
    events.extend([
        ("2025-02-17T09:00:00+03:00", "split", {}),
        ("2025-03-17T10:00:00+03:00", "dividend", {}),
        ("2025-03-17T10:00:01+03:00", "tax", {}),
    ])
    normalized, timeline = [], []
    for dt, kind, op in sorted(events, key=lambda event: event[0]):
        if kind == "split":
            for lot in lots:
                lot["quantity"] *= 2
                lot["unit_price"] /= 2
                lot["unit_fee"] /= 2
            price = D("500")
        elif kind == "dividend":
            dividends += D("400")
            cash += D("400")
            price = D(str(series[ASSET][dt[:10]]))
        elif kind == "tax":
            taxes += D("52")
            cash -= D("52")
            price = D(str(series[ASSET][dt[:10]]))
        else:
            qty, price, fee = D(op["quantity"]), D(op["price"]), D(op["fee"])
            gross = qty * price
            fees += fee
            if op["operation_type"] == "buy":
                bought += gross
                cash -= gross + fee
                lots.append({"lot_id": op["operation_id"], "quantity": qty,
                             "unit_price": price, "unit_fee": fee / qty})
            else:
                sold += gross
                cash += gross - fee
                remaining, cost = qty, D(0)
                for lot in lots:
                    used = min(remaining, lot["quantity"])
                    cost += used * (lot["unit_price"] + lot["unit_fee"])
                    lot["quantity"] -= used
                    remaining -= used
                    if remaining == 0:
                        break
                assert remaining == 0, "Sale exceeds held quantity"
                realized += gross - fee - cost
            factor = D(2) if dt[:10] < SPLIT_DATE else D(1)
            normalized.append({
                "operation_id": op["operation_id"],
                "quantity_in_end_date_units": str(qty * factor),
                "price_in_end_date_units": money(price / factor),
                "gross_cash": money(gross), "fee": money(fee),
                "split_adjustment_factor": str(factor),
            })
        held = sum((lot["quantity"] for lot in lots), D(0))
        mv = held * price
        equity = cash + mv
        timeline.append({
            "event_id": op.get("operation_id", kind), "at": dt,
            "held_quantity": str(held), "cash": money(cash),
            "position_value": money(mv), "account_equity": money(equity),
            "weight_after_event": round(float(mv / equity), 8),
            "valuation_basis": "execution_price" if kind == "trade" else "synthetic_event_mark",
        })
    held = sum((lot["quantity"] for lot in lots), D(0))
    end_value = held * D(str(series[ASSET][END]))
    basis = sum((lot["quantity"] * (lot["unit_price"] + lot["unit_fee"]) for lot in lots), D(0))
    price_pnl = sold + end_value - bought
    net = price_pnl + dividends - fees - taxes
    # Counterfactual: same gross trade cash flows, a frictionless market TR index.
    units = D(0)
    for op in TRADES:
        index_level = D(str(series["index_market_tr"][op["executed_at"][:10]]))
        flow = D(op["quantity"]) * D(op["price"])
        units += (flow if op["operation_type"] == "buy" else -flow) / index_level
    benchmark_pnl = units * D(str(series["index_market_tr"][END])) + sold - bought
    fin = {
        "currency": "RUB", "cost_basis_method": "FIFO", "opening_quantity": "0",
        "closing_quantity": str(held), "gross_purchases": money(bought),
        "gross_sale_proceeds": money(sold), "end_market_value": money(end_value),
        "price_pnl": money(price_pnl), "gross_dividends": money(dividends),
        "withheld_dividend_tax": money(taxes), "total_fees": money(fees),
        "gross_total_pnl": money(price_pnl + dividends), "net_total_pnl": money(net),
        "realized_price_pnl_after_allocated_fees": money(realized),
        "remaining_cost_basis_including_fees": money(basis),
        "unrealized_price_pnl_after_allocated_entry_fees": money(end_value - basis),
        "net_dividends": money(dividends - taxes),
        "account_closing_cash": money(cash), "account_closing_equity": money(cash + end_value),
        "closing_position_weight": round(float(end_value / (cash + end_value)), 8),
        "net_pnl_divided_by_gross_purchases": round(float(net / bought), 8),
        "ratio_note": "Отношение P&L к сумме покупок; не TWR, IRR или годовая доходность.",
        "stock_buy_and_hold_cash_dividend_return": 0.04,
        "market_total_return": 0.04, "sector_total_return": 0.02,
        "holding_return_note": "Одна покупка в начале, дивиденд хранится деньгами; без реинвестирования, налогов и комиссий.",
        "counterfactual": {
            "method": "Same gross purchases and sales in a frictionless total-return index",
            "execution_assumption": "Индекс доступен по значению закрытия в дату сделки; учебное упрощение.",
            "market_gross_pnl": money(benchmark_pnl),
            "actual_gross_pnl": money(price_pnl + dividends),
            "actual_minus_market_gross_pnl": money(price_pnl + dividends - benchmark_pnl),
            "interpretation": "Сценарное сравнение; не причинное разложение и не доказанная упущенная прибыль.",
        },
        "evidence_ids": [op["operation_id"] for op in TRADES] +
                        ["op_dividend", "op_dividend_tax", "ca_split", "ca_dividend", f"bar_{ASSET}_{END}"],
    }
    assert net == D("-377.60")
    assert realized + (end_value - basis) + dividends - taxes == net
    assert cash + end_value - D("100000") == net
    return fin, normalized, timeline


def main():
    series, bars = make_bars()
    model, returns = fit_and_detect(series)
    fin, normalized, timeline = make_financials(series)
    sources = [
        source("src_market_snapshot", "synthetic_exchange_feed", "2025-04-01T05:00:00+03:00", "market/snapshot"),
        source("src_broker_snapshot", "synthetic_read_only_broker", "2025-04-01T05:00:00+03:00", "broker/snapshot"),
        source("src_split", "issuer_corporate_action", "2025-01-20T09:00:00+03:00", "actions/split"),
        source("src_dividend", "issuer_corporate_action", "2025-01-30T09:00:00+03:00", "actions/dividend"),
    ]
    sources += [source(n["source_id"], n["content_type"], n["published_at"], "news/"+n["news_id"]) for n in NEWS]
    # Snapshot creation time is not historical data availability; each row has its own timestamp.
    sources[0]["historical_availability_field"] = "daily_bars[].provider_available_at"
    sources[1]["historical_availability_field"] = "operations[].broker_available_at"
    dump("01_news.json", {"sources": sources, "documents": NEWS})
    dump("02_market.json", {
        "instruments": [
            {"instrument_id": ASSET, "ticker": "SYNX", "name": "Синтетика, обыкновенная акция",
             "venue": "XSIM", "currency": "RUB", "lot_size": 1,
             "sector": "synthetic_industrials", "valid_from": "2024-01-01"},
            {"instrument_id": "index_market_tr", "name": "Учебный индекс рынка полной доходности",
             "index_type": "total_return", "currency": "RUB"},
            {"instrument_id": "index_sector_tr", "name": "Учебный отраслевой индекс полной доходности",
             "index_type": "total_return", "currency": "RUB"},
        ],
        "benchmark_memberships": [{"asset_id": ASSET, "market_index_id": "index_market_tr",
                                   "sector_index_id": "index_sector_tr", "valid_from": "2024-01-01",
                                   "valid_to": None, "known_at": "2024-01-01T09:00:00+03:00"}],
        "calendar": {"venue": "XSIM", "session_close_local": "18:45:00",
                     "rule": "Учебный календарь: понедельник–пятница, без праздников и остановок торгов."},
        "corporate_actions": [
            {"action_id": "ca_split", "asset_id": ASSET, "type": "split",
             "announced_at": "2025-01-20T09:00:00+03:00", "effective_at": "2025-02-17T09:00:00+03:00",
             "new_shares_per_old_share": "2", "source_id": "src_split"},
            {"action_id": "ca_dividend", "asset_id": ASSET, "type": "cash_dividend",
             "announced_at": "2025-01-30T09:00:00+03:00", "ex_date": "2025-03-03",
             "record_date": "2025-03-04", "eligible_position_as_of": "2025-02-28T18:45:00+03:00",
             "planned_payment_date": "2025-03-17", "cash_per_post_split_share": "10.00",
             "currency": "RUB", "settlement_convention": "synthetic_T_plus_1",
             "source_id": "src_dividend"},
        ],
        "decision_quotes": [
            {"quote_id": "quote_buy_1", "asset_id": ASSET, "observed_at": "2025-02-03T11:59:59+03:00",
             "last_price": "1000.00", "previous_close_adjusted_to_current_units": "1000.00", "source_id": "src_market_snapshot"},
            {"quote_id": "quote_buy_2", "asset_id": ASSET, "observed_at": "2025-02-25T18:39:59+03:00",
             "last_price": "540.00", "previous_close_adjusted_to_current_units": "505.00", "source_id": "src_market_snapshot"},
            {"quote_id": "quote_sell_1", "asset_id": ASSET, "observed_at": "2025-03-20T13:59:59+03:00",
             "last_price": "480.00", "previous_close_adjusted_to_current_units": "490.00", "source_id": "src_market_snapshot"},
        ],
        "daily_bars": bars,
    })
    dump("03_user_actions.json", {
        "accounts": [{"account_id": "account_demo", "owner_id": "user_demo",
                      "base_currency": "RUB", "access": "read_only"}],
        "opening_snapshot": {"snapshot_id": "opening_account", "as_of": "2025-01-31T19:00:00+03:00",
                             "cash": "100000.00", "positions": [], "other_assets": [],
                             "source_id": "src_broker_snapshot"},
        "operations": TRADES + [
            {"operation_id": "op_dividend", "account_id": "account_demo", "asset_id": ASSET,
             "operation_type": "dividend_credit", "executed_at": "2025-03-17T10:00:00+03:00",
             "broker_available_at": "2025-03-17T10:00:00+03:00", "eligible_quantity": "40",
             "amount": "400.00", "currency": "RUB", "corporate_action_id": "ca_dividend",
             "source_id": "src_broker_snapshot", "ingested_at": "2025-04-01T06:00:00+03:00"},
            {"operation_id": "op_dividend_tax", "account_id": "account_demo", "asset_id": ASSET,
             "operation_type": "tax_withholding", "executed_at": "2025-03-17T10:00:01+03:00",
             "broker_available_at": "2025-03-17T10:00:01+03:00", "amount": "52.00",
             "currency": "RUB", "related_operation_id": "op_dividend",
             "source_id": "src_broker_snapshot", "ingested_at": "2025-04-01T06:00:00+03:00"},
        ],
        "theses": [{"thesis_id": "thesis_dividend", "asset_id": ASSET, "version": 1,
                    "template_id": "dividend_payment", "recorded_at": "2025-02-03T11:00:00+03:00",
                    "effective_from": "2025-02-03T11:00:00+03:00", "origin": "user_selected",
                    "statement": "Компания выплатит не менее 10 RUB на акцию после сплита до 31 марта.",
                    "predicate": {"metric": "gross_cash_dividend_per_post_split_share",
                                  "operator": ">=", "threshold": "10.00", "deadline": END},
                    "entry_evidence_ids": ["n_dividend", "ca_dividend"],
                    "invalidation_condition": "Отмена выплаты либо выплата меньше порога к сроку.",
                    "claim_scope": "Выплата дивиденда; тезис не обещает положительный итог позиции."}],
        "rule_versions": [{
            "rule_set_id": "rules_v1", "recorded_at": "2025-02-03T10:30:00+03:00",
            "effective_from": "2025-02-03T10:30:00+03:00", "effective_to": None,
            "origin": "user_confirmed",
            "rules": [
                {"rule_id": "max_weight", "kind": "limit", "threshold": 0.15,
                 "predicate": "position_value_after_trade / account_equity_after_trade <= threshold"},
                {"rule_id": "avoid_jump_buy", "kind": "user_constraint", "threshold": 0.05,
                 "predicate": "on_buy: last_observed_quote / adjusted_previous_close - 1 < threshold"},
                {"rule_id": "thesis_before_buy", "kind": "user_constraint",
                 "predicate": "on_buy: thesis.recorded_at < trade.executed_at"},
                {"rule_id": "avoid_averaging_down", "kind": "user_constraint", "threshold": -0.05,
                 "predicate": "on_add: price / held_average_price_excluding_fees - 1 > threshold"},
                {"rule_id": "hold_to_deadline", "kind": "user_constraint", "deadline": END,
                 "predicate": "no_sale_before_deadline_unless_risk_rebalance",
                 "exception": "reason recorded at trade is rebalance_to_concentration_limit AND weight_after <= 0.15"},
            ],
        }],
        "requests": [{"request_id": "request_01", "asked_at": "2025-04-01T10:00:00+03:00",
                      "text": "Разбери SYNX с 3 февраля по 31 марта. Почему я в минусе, если дивиденды выплатили?",
                      "resolved_asset_id": ASSET, "period_from": START, "period_through": END,
                      "period_policy": "Включая границы; конечная оценка по закрытию 31 марта."}],
    })

    anomaly_by_date = {row["session_date"]: row for row in returns if row["is_anomaly"]}
    for dt in ["2025-02-25", "2025-03-04", "2025-03-10"]:
        assert dt in anomaly_by_date
    add = next(row for row in timeline if row["event_id"] == "op_buy_2")
    sale = next(row for row in timeline if row["event_id"] == "op_sell_1")
    jump = D("540") / D("505") - 1
    rule_checks = [
        {"check_id": "check_weight_initial", "rule_id": "max_weight", "operation_id": "op_buy_1",
         "status": "complied", "observed": timeline[0]["weight_after_event"], "threshold": 0.15,
         "evidence_ids": ["op_buy_1", "opening_account", "quote_buy_1", "rules_v1"]},
        {"check_id": "check_weight", "rule_id": "max_weight", "operation_id": "op_buy_2",
         "status": "violated", "observed": add["weight_after_event"], "threshold": 0.15,
         "evidence_ids": ["op_buy_1", "op_buy_2", "ca_split", "opening_account", "quote_buy_2", "rules_v1"]},
        {"check_id": "check_jump", "rule_id": "avoid_jump_buy", "operation_id": "op_buy_2",
         "status": "violated", "observed": round(float(jump), 8), "threshold": 0.05,
         "as_of": "2025-02-25T18:40:00+03:00", "evidence_ids": ["op_buy_2", "quote_buy_2", "rules_v1"],
         "interpretation": "Покупка после роста; психологический мотив по этим данным неизвестен."},
        {"check_id": "check_entry_thesis", "rule_id": "thesis_before_buy",
         "operation_ids": ["op_buy_1", "op_buy_2"], "status": "complied",
         "evidence_ids": ["thesis_dividend", "op_buy_1", "op_buy_2", "rules_v1"]},
        {"check_id": "check_average", "rule_id": "avoid_averaging_down", "operation_id": "op_buy_2",
         "status": "complied", "observed_price_vs_held_cost": 0.08,
         "evidence_ids": ["op_buy_1", "op_buy_2", "ca_split", "rules_v1"]},
        {"check_id": "check_horizon", "rule_id": "hold_to_deadline", "operation_id": "op_sell_1",
         "status": "complied_by_exception", "weight_after_sale": sale["weight_after_event"],
         "exception": "Recorded risk rebalance; concentration restored to <= 15%.",
         "evidence_ids": ["op_sell_1", "quote_sell_1", "rules_v1"]},
        {"check_id": "check_weight_sale", "rule_id": "max_weight", "operation_id": "op_sell_1",
         "status": "complied", "observed": sale["weight_after_event"], "threshold": 0.15,
         "evidence_ids": ["op_sell_1", "quote_sell_1", "rules_v1"]},
    ]
    thesis_check = {
        "check_id": "check_dividend", "thesis_id": "thesis_dividend",
        "as_of": "2025-03-31T23:59:59+03:00", "status": "supported",
        "eligible_quantity": "40", "observed_gross_per_share": "10.00",
        "actual_payment_date": "2025-03-17", "threshold": "10.00", "deadline": END,
        "evidence_ids": ["op_dividend", "ca_dividend", "ca_split", "op_buy_1", "op_buy_2"],
        "limitation": "Подтверждён только зафиксированный дивидендный тезис, не качество всей инвестиции.",
    }
    # Rules are transparent examples; assert the facts supporting every hand-labelled result.
    assert add["weight_after_event"] > .15 and jump >= D("0.05")
    assert timeline[0]["weight_after_event"] <= .15
    assert sale["weight_after_event"] <= .15
    assert D("540") / D("500") - 1 > D("-0.05")
    assert all("2025-02-03T11:00:00+03:00" < op["executed_at"] for op in TRADES[:2])
    assert D("400") / D("40") >= D(thesis_check["threshold"])
    assert thesis_check["actual_payment_date"] <= thesis_check["deadline"]
    episodes = []
    for row in anomaly_by_date.values():
        dt = row["session_date"]
        if dt == "2025-02-25":
            selected, cutoff = ["n_contract"], "2025-02-25T09:00:00+03:00"
            excluded = [{"news_id": "n_contract_copy", "reason": "duplicate_not_independent_evidence"}]
            status, explanation = "plausible_association", "Контракт опубликован до сессии; причинность не доказана."
        elif dt == "2025-03-04":
            selected, cutoff = ["n_outlook_v1"], "2025-03-04T09:00:00+03:00"
            excluded = [{"news_id": "n_outlook_v2", "reason": "correction_after_cutoff"},
                        {"news_id": "n_opinion", "reason": "opinion_and_after_session"}]
            status, explanation = "plausible_association", "Прогноз снижен до сессии; 5 марта цифра исправлена на 6%."
        else:
            selected, cutoff, excluded = [], dt + "T09:00:00+03:00", []
            status, explanation = "unexplained", "В учебной ленте нет подходящего независимого сообщения."
        episodes.append({
            "episode_id": "episode_" + dt, "session_date": dt,
            "detection_granularity": "daily_close_to_close",
            "onset_precision": "Неизвестно: нет внутридневного ряда; дата не определяет момент начала движения.",
            "evidence_cutoff": cutoff, "cutoff_policy": "Консервативно: только сообщения до начала сессии.",
            "residual": row["residual"], "residual_z_score": row["residual_z_score"],
            "source_ids": ["src_" + item for item in selected],
            "selected_news_ids": selected, "excluded": excluded,
            "attribution_status": status, "explanation": explanation,
            "search_scope": "Только синтетическая лента 01_news.json, а не весь рынок.",
        })
    dump("04_calculated.json", {
        "report_id": "report_01", "request_id": "request_01",
        "financials": fin, "normalized_trades": normalized, "account_timeline": timeline,
        "factor_model": model, "daily_returns": returns, "episodes": episodes,
        "rule_checks": rule_checks, "thesis_checks": [thesis_check],
        "verdict": {"process": "violated_declared_rules", "outcome": "loss",
                    "thesis": "supported", "matrix_cell": "rules_violated__loss",
                    "process_scope": "Только проверенные пользовательские правила; не универсальная оценка разумности.",
                    "evidence_ids": ["check_weight", "check_jump", "check_dividend"]},
    })
    claims = [
        {"claim_id": "claim_pnl", "type": "calculation",
         "text": "Результат позиции −377,60 RUB: движение цены −700,00; дивиденды +400,00; комиссии −25,60; удержанный налог −52,00.",
         "evidence_ids": ["report_01.financials"], "source_ids": ["src_broker_snapshot", "src_market_snapshot", "src_split"]},
        {"claim_id": "claim_dividend", "type": "verified_fact",
         "text": "Дивидендный тезис подтвердился: 17 марта зачислено 400 RUB на 40 акций, по 10 RUB до удержания налога.",
         "evidence_ids": ["check_dividend", "op_dividend"], "source_ids": ["src_broker_snapshot", "src_dividend"]},
        {"claim_id": "claim_process", "type": "rule_result",
         "text": f"После докупки 25 февраля доля бумаги достигла {add['weight_after_event'] * 100:.2f}% при вашем лимите 15%.",
         "evidence_ids": ["check_weight"], "source_ids": ["src_broker_snapshot", "src_market_snapshot"]},
        {"claim_id": "claim_contract", "type": "hypothesis",
         "text": "Рост 25 февраля мог быть связан с опубликованным до сессии контрактом. Одной временной связи недостаточно для установления причины.",
         "evidence_ids": ["episode_2025-02-25", "n_contract"], "source_ids": ["src_n_contract"]},
        {"claim_id": "claim_outlook", "type": "hypothesis",
         "text": "Снижение прогноза выручки могло повлиять на падение 4 марта. На тот момент сообщалось о 4%; 5 марта компания исправила показатель на 6%.",
         "evidence_ids": ["episode_2025-03-04", "n_outlook_v1", "n_outlook_v2"],
         "source_ids": ["src_n_outlook_v1", "src_n_outlook_v2"]},
        {"claim_id": "claim_unknown", "type": "uncertainty",
         "text": "Для аномального движения 10 марта объяснение в доступной учебной ленте не найдено.",
         "evidence_ids": ["episode_2025-03-10"], "source_ids": ["src_market_snapshot"]},
    ]
    knowledge = {
        "knowledge_id": "knowledge_01", "owner_id": "user_demo", "asset_id": ASSET,
        "version": 1, "status": "proposed", "replaces": None,
        "report_id": "report_01", "created_at": "2025-04-01T10:01:00+03:00",
        "period_from": START, "period_through": END,
        "context": "Подтверждённый дивидендный тезис; две покупки, частичная продажа, сплит.",
        "observation": "Подтверждение выплаты не гарантировало прибыль позиции. Доля выросла выше заранее выбранного лимита.",
        "claim_ids": ["claim_pnl", "claim_dividend", "claim_process"],
        "scope": "Один учебный эпизод; не доказательство устойчивой привычки или причинной связи.",
        "reflection_question": "Как вы оценивали размер позиции при докупке 25 февраля?",
        "learning_topic": "Дивидендный гэп и разница между выполнением тезиса и общим результатом.",
        "user_confirmation": "pending",
        "reusable_when": "Пользователь просит сравнить похожие прошлые решения; без автоматического торгового действия.",
    }
    stages = [
        ("resolve_request", ["request_01"], ["asset_synx", "2025-02-03/2025-03-31"]),
        ("snapshot_and_authorize", ["account_demo"], ["input_manifest"]),
        ("ingest_and_version", ["01_news.json", "02_market.json", "03_user_actions.json"], ["immutable_source_rows"]),
        ("normalize_and_validate", ["immutable_source_rows"], ["normalized_trades", "quality_gates"]),
        ("reconstruct_position", ["normalized_trades", "ca_split", "ca_dividend"], ["account_timeline", "financials"]),
        ("fit_prior_factor_model", ["pre_period_daily_bars"], ["factor_model_01"]),
        ("detect_residual_episodes", ["factor_model_01", "daily_bars"], ["daily_returns", "episodes"]),
        ("retrieve_point_in_time_evidence", ["episodes", "01_news.json"], ["selected_news_ids", "excluded_news"]),
        ("evaluate_rules_and_thesis", ["rules_v1", "thesis_dividend", "account_timeline"], ["rule_checks", "check_dividend", "verdict"]),
        ("assemble_evidence_bundle", ["financials", "episodes", "rule_checks", "check_dividend"], ["llm_input"]),
        ("compose_and_validate_card", ["llm_input"], ["claims", "card"]),
        ("persist_and_reflect", ["card", "claims"], ["knowledge_01", "feedback_contract"]),
    ]
    validation = {
        "money_reconciled": True,
        "cash_equity_reconciled": True,
        "no_short_sale": True,
        "all_sources_resolve": True,
        "selected_news_before_cutoff": True,
        "training_precedes_period": True,
        "synthetic_urls_are_placeholders": True,
        "live_source_content_verified": False,
        "llm_called": False,
        "note": "Карточка — вручную заданный эталон с программной проверкой связей и сумм. LLM и поисковый API здесь не запускались.",
    }
    ids = {s["source_id"] for s in sources}
    for claim in claims:
        assert claim["source_ids"] and set(claim["source_ids"]) <= ids
    news_by_id = {n["news_id"]: n for n in NEWS}
    for episode in episodes:
        assert all(news_by_id[n]["published_at"] <= episode["evidence_cutoff"]
                   and news_by_id[n]["provider_available_at"] <= episode["evidence_cutoff"]
                   for n in episode["selected_news_ids"])
    assert model["training_through"] < START
    for fn in ["01_news.json", "02_market.json", "03_user_actions.json", "04_calculated.json"]:
        payload = json.loads((ROOT / fn).read_text(encoding="utf-8"))

        def check_source_links(node):
            if isinstance(node, dict):
                if "source_id" in node:
                    assert node["source_id"] in ids
                if "source_ids" in node:
                    assert set(node["source_ids"]) <= ids
                for value in node.values():
                    check_source_links(value)
            elif isinstance(node, list):
                for value in node:
                    check_source_links(value)

        check_source_links(payload)
    for collection, key in [(bars, "bar_id"), (NEWS, "news_id"), (sources, "source_id")]:
        assert len({row[key] for row in collection}) == len(collection)
    claim_ids = {c["claim_id"] for c in claims}
    assert set(knowledge["claim_ids"]) <= claim_ids
    referenced_ids = {"report_01.financials", "rules_v1", "opening_account", "thesis_dividend"}
    referenced_ids.update(op["operation_id"] for op in TRADES)
    referenced_ids.update(["op_dividend", "op_dividend_tax", "ca_split", "ca_dividend"])
    referenced_ids.update(n["news_id"] for n in NEWS)
    referenced_ids.update(row["bar_id"] for row in bars)
    referenced_ids.update(["quote_buy_1", "quote_buy_2", "quote_sell_1"])
    referenced_ids.update(ep["episode_id"] for ep in episodes)
    referenced_ids.update(c["check_id"] for c in rule_checks + [thesis_check])
    for item in claims + rule_checks + [thesis_check, fin] + returns:
        assert set(item.get("evidence_ids", [])) <= referenced_ids, item
    dump("05_pipeline_and_knowledge.json", {
        "run_id": "run_01", "report_id": "report_01", "as_of": "2025-04-01T10:00:00+03:00",
        "mode": "offline_synthetic_reference",
        "input_manifest": [{"file": fn, "sha256": hashlib.sha256((ROOT / fn).read_bytes()).hexdigest()}
                           for fn in ["01_news.json", "02_market.json", "03_user_actions.json"]],
        "versions": {"calculator": "demo_v1", "rules": "rules_v1", "factor_model": "factor_model_01",
                     "prompt": "reference_card_v1", "llm": None},
        "quality_gates": validation,
        "stages": [{"stage": name, "inputs": inputs, "outputs": outputs} for name, inputs, outputs in stages],
        "llm_input": {
            "request_id": "request_01", "financials_ref": "04_calculated.json#/financials",
            "episodes_ref": "04_calculated.json#/episodes", "rules_ref": "04_calculated.json#/rule_checks",
            "thesis_ref": "04_calculated.json#/thesis_checks",
            "historical_sources_by_episode": [
                {"episode_id": ep["episode_id"], "cutoff": ep["evidence_cutoff"],
                 "documents": [{"file": "01_news.json", "news_id": nid}
                               for nid in ep["selected_news_ids"]]}
                for ep in episodes],
            "entry_thesis_sources": [{"file": "01_news.json", "news_id": "n_dividend",
                                      "cutoff": "2025-02-03T11:00:00+03:00"}],
            "later_updates": [{"file": "01_news.json", "news_id": "n_outlook_v2",
                               "role": "Показывать только как последующее уточнение от 5 марта; "
                                       "не как знание инвестора или рынка до сессии 4 марта."}],
            "instructions": ["Не пересчитывать числа; использовать готовые метрики.",
                             "Каждое утверждение связывать с evidence_ids и source_ids.",
                             "Отделять факт, расчёт, гипотезу и неизвестное.",
                             "Не использовать поздние сведения для оценки раннего решения.",
                             "Уточнения после события показывать отдельно и с датой.",
                             "Не выводить мотивы человека из сделок и не давать торговые рекомендации."],
        },
        "claims": claims,
        "card": {"title": "SYNX: тезис подтвердился, позиция принесла убыток",
                 "claim_ids": [c["claim_id"] for c in claims], "knowledge_id": "knowledge_01",
                 "next_step": "Обсудить логику докупки и открыть материал о дивидендном гэпе."},
        "knowledge": knowledge,
        "feedback_contract": {
            "feedback_id": None, "knowledge_id": "knowledge_01", "user_confirmed": None,
            "correction": None, "claim_id": None, "collected_at": None,
            "status": "not_collected", "use": "Обратная связь хранится отдельно и не переписывает факты или исходный тезис.",
        },
    })
    print(f"Built 5 JSON files; {len(bars)} bars; {len(episodes)} anomalous sessions.")
    print(f"Net P&L: {fin['net_total_pnl']} RUB; closing quantity: {fin['closing_quantity']}.")
    print(f"Counterfactual market gross P&L: {fin['counterfactual']['market_gross_pnl']} RUB.")
    print("Validation passed. No live data, network calls, or LLM generation.")


if __name__ == "__main__":
    main()
