"""
core/net_metering.py
Czyste funkcje (zero I/O): rozliczenie prosumenta w systemie opustów
(ustawa o OZE, art. 4 — instalacje uruchomione przed 1.04.2022, ≤10 kW: 1 do 0,8).

Zasady odwzorowane w kodzie:
  * bilansowanie GODZINOWE na wszystkich fazach: Eb(t) = pobór(t) − oddanie(t);
    tylko godziny z nadwyżką oddania tworzą depozyt, a część poboru pokryta
    oddaniem z tej samej godziny jest rozliczona 1:1 (bez straty 20%) — art. 4 ust. 2b;
  * okres rozliczeniowy (tu: miesiąc): Er = Ebp + 0,8·Ebw + Er(o−1) — art. 4 ust. 3;
    współczynnik 0,8 dotyczy tylko energii oddanej, nie przechodzi ponownie na
    przeniesione nadwyżki;
  * datą wprowadzenia jest OSTATNI DZIEŃ miesiąca oddania; nadwyżka przechodzi na
    kolejne okresy, nie dłużej niż 12 miesięcy od tej daty — art. 4 ust. 5;
  * w pierwszej kolejności rozlicza się najstarszą energię, przed energią oddaną
    w bieżącym okresie — art. 4 ust. 5a;
  * niewykorzystana po 12 miesiącach energia przechodzi na sprzedawcę — art. 4 ust. 11.
"""

import calendar
from datetime import datetime, timedelta, date as date_cls
from typing import Optional

_EPS = 1e-6


def balance_hourly(import_rows: list, export_rows: list) -> dict:
    """
    import_rows / export_rows: [{'date': 'YYYY-MM-DD', 'hour': int, 'kwh': float}]
    (surowe odczyty z liczników — pobór i oddanie mogą być > 0 w tej samej godzinie,
    bo różne fazy bilansują się dopiero w rozliczeniu).

    Zwraca {'YYYY-MM-DD': {'imported_kwh', 'exported_kwh',            # po zbilansowaniu
                           'raw_imported_kwh', 'raw_exported_kwh'}}.
    """
    imp = {}
    exp = {}
    for r in import_rows:
        k = (r["date"], r["hour"])
        imp[k] = imp.get(k, 0.0) + r["kwh"]
    for r in export_rows:
        k = (r["date"], r["hour"])
        exp[k] = exp.get(k, 0.0) + r["kwh"]

    days: dict = {}
    for k in set(imp) | set(exp):
        i = imp.get(k, 0.0)
        e = exp.get(k, 0.0)
        d = days.setdefault(k[0], {
            "imported_kwh": 0.0, "exported_kwh": 0.0,
            "raw_imported_kwh": 0.0, "raw_exported_kwh": 0.0,
        })
        d["raw_imported_kwh"] += i
        d["raw_exported_kwh"] += e
        if i >= e:
            d["imported_kwh"] += i - e
        else:
            d["exported_kwh"] += e - i
    return days


def aggregate_months(daily: dict) -> dict:
    """{'YYYY-MM-DD': {...}} → {'YYYY-MM': {...}} (sumy tych samych pól)."""
    months: dict = {}
    for day, v in daily.items():
        m = months.setdefault(day[:7], {k: 0.0 for k in v})
        for k, val in v.items():
            m[k] += val
    return months


def _month_end(y: int, m: int) -> date_cls:
    return date_cls(y, m, calendar.monthrange(y, m)[1])


def _split(period: str):
    y, m = period.split("-")
    return int(y), int(m)


def _next_period(y: int, m: int):
    return (y + 1, 1) if m == 12 else (y, m + 1)


class _Ledger:
    """Depozyt: wpisy [data_wprowadzenia, pozostało_kWh, ważny_do] w kolejności chronologicznej."""

    def __init__(self, rate: float):
        self.rate = rate
        self.entries: list = []

    def step(self, y: int, m: int, imp: float, exp: float) -> dict:
        month_end = _month_end(y, m)

        expired = 0.0
        for e in self.entries:
            if e[1] > 0 and e[2] < month_end:
                expired += e[1]
                e[1] = 0.0

        need = max(0.0, imp)
        for e in self.entries:
            if need <= _EPS:
                break
            if e[1] <= 0:
                continue
            take = min(e[1], need)
            e[1] -= take
            need -= take

        credit = max(0.0, exp) * self.rate
        use = min(credit, need)
        credit -= use
        need -= use

        if credit > _EPS:
            self.entries.append([month_end, credit, _month_end(y + 1, m)])

        return {
            "covered": max(0.0, imp) - need,
            "purchased": need,
            "expired": expired,
        }

    def live(self, today: date_cls) -> list:
        return [e for e in self.entries if e[1] > 1e-3 and e[2] >= today]


def _run_ledger(monthly_rows: list, rate: float, before_period: Optional[str] = None):
    """Przetwarza kolejne miesiące (rosnąco). before_period — bez tego miesiąca i późniejszych."""
    ledger = _Ledger(rate)
    detail = {}
    for r in sorted(monthly_rows, key=lambda r: r["period"]):
        if before_period and r["period"] >= before_period:
            break
        y, m = _split(r["period"])
        detail[r["period"]] = ledger.step(y, m, r.get("imported_kwh") or 0.0, r.get("exported_kwh") or 0.0)
    return ledger, detail


def compute_deposit(monthly_rows: list, rate: float = 0.8, today: Optional[date_cls] = None) -> dict:
    """
    monthly_rows: [{'period': 'YYYY-MM', 'imported_kwh', 'exported_kwh'}] — wartości PO
    zbilansowaniu godzinowym, ciągła historia (im dłuższa, tym dokładniejszy stan:
    wynik jest wiarygodny od 12 miesięcy po pierwszym miesiącu danych).
    """
    today = today or datetime.now().date()
    ledger, detail = _run_ledger(monthly_rows, rate)

    live = ledger.live(today)
    balance = sum(e[1] for e in live)

    ty, tm = today.year, today.month
    for _ in range(11):
        tm -= 1
        if tm == 0:
            tm = 12
            ty -= 1
    window_from = f"{ty}-{tm:02d}"
    win = [d for p, d in detail.items() if p >= window_from]

    in_30 = today + timedelta(days=30)
    in_90 = today + timedelta(days=90)

    by_expiry_month: dict = {}
    for e in live:
        key = e[2].strftime("%Y-%m")
        by_expiry_month[key] = by_expiry_month.get(key, 0.0) + e[1]

    return {
        "rate": rate,
        "current_balance_kwh":     round(balance, 3),
        "expired_total_kwh":       round(sum(d["expired"] for d in win), 3),
        "covered_by_deposit_kwh":  round(sum(d["covered"] for d in win), 3),
        "purchased_from_grid_kwh": round(sum(d["purchased"] for d in win), 3),
        "expiring_within_30d_kwh": round(sum(e[1] for e in live if e[2] <= in_30), 3),
        "expiring_within_90d_kwh": round(sum(e[1] for e in live if e[2] <= in_90), 3),
        "expiring_by_month":       {k: round(v, 3) for k, v in sorted(by_expiry_month.items())},
        "window_from":             window_from,
    }


def compute_projection(monthly_rows: list, rate: float = 0.8, year: Optional[int] = None,
                       today: Optional[date_cls] = None) -> dict:
    """
    Prognoza do końca roku: miesiące przyszłe = średnia historyczna (po zbilansowaniu)
    tego samego miesiąca z lat ubiegłych, bieżący miesiąc = dotychczasowe + proporcjonalna
    reszta. Depozyt jest symulowany miesiąc po miesiącu tymi samymi zasadami co
    compute_deposit (najstarsze nadwyżki zużywane najpierw, wygasanie po 12 miesiącach).
    """
    now = datetime.now()
    today = today or now.date()
    year = year or today.year
    cur_m = today.month
    by_period = {r["period"]: r for r in monthly_rows}

    hist_by_month: dict = {}
    for r in monthly_rows:
        y, m = _split(r["period"])
        if y < year:
            hist_by_month.setdefault(m, []).append(r)

    def avg(m: int, key: str):
        h = hist_by_month.get(m, [])
        return (sum(x[key] for x in h) / len(h)) if h else None

    dim_cur = calendar.monthrange(year, cur_m)[1]
    remaining_fraction = max(0.0, (dim_cur - today.day) / dim_cur)

    ledger, _ = _run_ledger(monthly_rows, rate, before_period=f"{year}-{cur_m:02d}")

    actual_imp = actual_exp = 0.0
    rest_imp = rest_exp = 0.0
    purchased_rest = expired_rest = covered_rest = 0.0
    months_detail = []

    for m in range(1, 13):
        period = f"{year}-{m:02d}"
        actual = by_period.get(period)
        a_imp = (actual or {}).get("imported_kwh") or 0.0
        a_exp = (actual or {}).get("exported_kwh") or 0.0
        h_imp, h_exp = avg(m, "imported_kwh"), avg(m, "exported_kwh")

        if m < cur_m:
            actual_imp += a_imp
            actual_exp += a_exp
            months_detail.append({"period": period, "type": "actual",
                                  "imported_kwh": round(a_imp, 3), "exported_kwh": round(a_exp, 3)})
            continue

        if m == cur_m:
            actual_imp += a_imp
            actual_exp += a_exp
            p_imp = (h_imp or 0.0) * remaining_fraction
            p_exp = (h_exp or 0.0) * remaining_fraction
            months_detail.append({
                "period": period, "type": "partial",
                "imported_kwh": round(a_imp, 3), "exported_kwh": round(a_exp, 3),
                "projected_rest_imported_kwh": round(p_imp, 3),
                "projected_rest_exported_kwh": round(p_exp, 3),
            })
            month_imp, month_exp = a_imp + p_imp, a_exp + p_exp
        else:
            p_imp, p_exp = h_imp or 0.0, h_exp or 0.0
            months_detail.append({
                "period": period, "type": "forecast",
                "projected_imported_kwh": round(h_imp, 3) if h_imp is not None else None,
                "projected_exported_kwh": round(h_exp, 3) if h_exp is not None else None,
                "has_history": bool(hist_by_month.get(m)),
            })
            month_imp, month_exp = p_imp, p_exp

        rest_imp += p_imp
        rest_exp += p_exp
        res = ledger.step(year, m, month_imp, month_exp)
        purchased_rest += res["purchased"]
        expired_rest += res["expired"]
        covered_rest += res["covered"]

    now_ledger, _ = _run_ledger(monthly_rows, rate)
    balance_now = sum(e[1] for e in now_ledger.live(today))
    new_credit = rest_exp * rate
    available = balance_now + new_credit - expired_rest

    year_end = date_cls(year, 12, 31)
    end_balance = sum(e[1] for e in ledger.live(year_end))
    history_years = sorted({r["period"][:4] for r in monthly_rows if r["period"][:4] < str(year)})

    return {
        "year": year,
        "actual_import_ytd_kwh": round(actual_imp, 3),
        "actual_export_ytd_kwh": round(actual_exp, 3),
        "projected_rest_of_year_import_kwh": round(rest_imp, 3),
        "projected_rest_of_year_export_kwh": round(rest_exp, 3),
        "projected_year_total_import_kwh": round(actual_imp + rest_imp, 3),
        "projected_year_total_export_kwh": round(actual_exp + rest_exp, 3),
        "projected_deposit_end_of_year_kwh": round(end_balance, 3),
        "projected_grid_purchase_kwh": round(purchased_rest, 3),
        "projected_expiring_unused_kwh": round(expired_rest, 3),
        "balance_now_kwh": round(balance_now, 3),
        "projected_new_credit_kwh": round(new_credit, 3),
        "available_until_year_end_kwh": round(available, 3),
        "history_years_available": history_years,
        "months_detail": months_detail,
    }
