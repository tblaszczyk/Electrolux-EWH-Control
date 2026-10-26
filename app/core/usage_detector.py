"""
core/usage_detector.py
Detekcja SESJI poboru ciepłej wody (prysznic/kąpiel) na podstawie
spadków temp_current w boiler_history — bez żadnego nowego sprzętu.

Czysto obserwacyjne: NIE wysyła komend, NIE wpływa na decision_logic/
scheduler/pv_manager/control_engine. Jedyne miejsce w core/, które
dotyka bazy — bo to cały sens tego modułu (skan historii + zapis
wykrytych zdarzeń).

Wykrywanie OKNOWE, nie punktowe: pierwsza wersja (punktowa, z oknem
15-min zakotwiczonym w jednym punkcie) rozcinała jedną ciągłą wieczorną
sesję (np. cała rodzina prysznic po prysznicu) na kilka rozłącznych
fragmentów, z których część błędnie trafiała do kategorii "wolny spadek"
i znikała z podsumowań. Zwalidowane na realnej historii: podejście
oknowe — najpierw oznacz KAŻDY odcinek między próbkami jako "aktywny"
gdy tempo spadku przekracza usage_active_rate_c_per_min (naturalne
stygnięcie zbiornika to ~0.07°C/min, dużo wolniej), potem połącz
sąsiadujące aktywne odcinki (z przerwą <= usage_merge_gap_min) w jedną
sesję — daje spójne, dłuższe sesje z realną liczbą "faz" (n_bursts)
zamiast rozdrobnionych, częściowo odrzucanych punktów.
"""

import logging
import statistics
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger("boiler.usage")


# ══════════════════════════════════════════════════════════════
# CZYSTE FUNKCJE — bez dostępu do DB, testowalne w izolacji
# ══════════════════════════════════════════════════════════════

def _segment_runs(rows: list, gap_max_min: float) -> list:
    """
    Dzieli posortowany strumień próbek (ts, temp) na ciągłe odcinki,
    przerywając gdy przerwa między kolejnymi próbkami > gap_max_min.
    Zakłada, że `rows` jest już przefiltrowane do heating=0 i temp>0.
    """
    runs, cur_run, prev_ts = [], [], None
    gap_s = gap_max_min * 60

    for ts, temp in rows:
        if prev_ts is not None and (ts - prev_ts).total_seconds() > gap_s:
            if cur_run:
                runs.append(cur_run)
            cur_run = []
        cur_run.append((ts, temp))
        prev_ts = ts

    if cur_run:
        runs.append(cur_run)
    return runs


def _classify_window(drop_c: float, cfg: dict) -> str:
    """subthreshold | session"""
    min_drop = cfg.get("usage_min_drop_c", 2.0)
    return "subthreshold" if drop_c < min_drop else "session"


def _mark_active(run: list, rate_c_per_min: float) -> list:
    """
    Zwraca listę bool (długość len(run)-1): True dla odcinka [i, i+1]
    jeśli tempo spadku temperatury przekracza rate_c_per_min — sygnatura
    realnego poboru wody, w odróżnieniu od dużo wolniejszego naturalnego
    stygnięcia zbiornika.
    """
    active = [False] * (len(run) - 1)
    for i in range(len(run) - 1):
        t1, temp1 = run[i]
        t2, temp2 = run[i + 1]
        mins = (t2 - t1).total_seconds() / 60.0
        if mins <= 0:
            continue
        rate = (temp1 - temp2) / mins
        if rate >= rate_c_per_min:
            active[i] = True
    return active


def _find_events_in_run(run: list, cfg: dict) -> list:
    """
    Wykrywa sesje poboru wody w jednym ciągłym odcinku "bez grzania":
    1) oznacza każdy odcinek między próbkami jako aktywny/nieaktywny
       (_mark_active), 2) łączy sąsiadujące aktywne odcinki, których
       przerwa nie przekracza usage_merge_gap_min, w jedną sesję,
       3) liczy dla sesji: całkowity spadek (do minimum w oknie sesji),
       czas trwania i n_bursts (liczba odrębnych aktywnych "faz" —
       przybliżony, eksperymentalny wskaźnik liczby osób w sesji).
    """
    merge_gap_s = cfg.get("usage_merge_gap_min", 15) * 60
    subthresh   = cfg.get("usage_subthreshold_min_drop_c", 0.5)

    n = len(run)
    if n < 2:
        return []
    active = _mark_active(run, cfg.get("usage_active_rate_c_per_min", 0.3))

    events = []
    i = 0
    while i < n - 1:
        if not active[i]:
            i += 1
            continue

        w_start = i
        w_end = i  # ostatni aktywny indeks w sesji
        j = i
        while j < n - 1:
            if active[j]:
                w_end = j
                j += 1
            else:
                # sprawdź, czy w zasięgu usage_merge_gap_min jest kolejny aktywny odcinek
                gap_start_ts = run[j + 1][0]
                k = j + 1
                found = False
                while k < n - 1 and (run[k][0] - gap_start_ts).total_seconds() <= merge_gap_s:
                    if active[k]:
                        found = True
                        break
                    k += 1
                if found:
                    j = k
                else:
                    break

        end_idx = min(w_end + 1, n - 1)
        window_samples = run[w_start:end_idx + 1]
        temp_before = run[w_start][1]
        temp_after = min(t for _, t in window_samples)
        drop = temp_before - temp_after
        duration_min = (run[end_idx][0] - run[w_start][0]).total_seconds() / 60.0
        n_bursts = sum(
            1 for x in range(w_start, w_end + 1)
            if active[x] and (x == w_start or not active[x - 1])
        )

        if drop >= subthresh:
            events.append({
                "start_ts":     run[w_start][0].isoformat(),
                "end_ts":       run[end_idx][0].isoformat(),
                "temp_before":  temp_before,
                "temp_after":   temp_after,
                "drop_c":       round(drop, 2),
                "duration_min": round(duration_min, 1),
                "n_bursts":     n_bursts,
                "category":     _classify_window(drop, cfg),
            })

        i = j if j > i else i + 1

    return events


def compute_weekday_baseline(daily_counts: list, baseline_weeks: int = 8) -> list:
    """
    daily_counts: [{"day": "YYYY-MM-DD", "count": int}, ...] posortowane rosnąco po dniu.
    Dla każdego dnia: mediana tej samej wartości weekday z ostatnich
    baseline_weeks tygodni (potrzeba >=4 wcześniejszych próbek).
    Zwraca listę wzbogaconą o baseline_median / ratio / signal.
    Czysta funkcja — brak dostępu do DB/zegara systemowego.
    """
    by_day = {d["day"]: d["count"] for d in daily_counts}
    days_sorted = sorted(by_day.keys())
    out = []

    for idx, day in enumerate(days_sorted):
        d = datetime.fromisoformat(day)
        wd = d.weekday()
        history = []
        for back in range(1, baseline_weeks + 1):
            cand = (d - timedelta(weeks=back)).date().isoformat()
            if cand in by_day:
                history.append(by_day[cand])

        count = by_day[day]
        if len(history) < 4:
            signal, baseline_median, ratio = "insufficient_data", None, None
        else:
            baseline_median = statistics.median(history)
            if baseline_median == 0:
                signal, ratio = ("zero" if count == 0 else "zero_baseline"), None
            else:
                ratio = round(count / baseline_median, 2)
                if count == 0:
                    signal = "zero"
                elif count < baseline_median:
                    signal = "below_baseline"
                else:
                    signal = "normal"

        out.append({
            "day": day, "weekday": wd, "count": count,
            "baseline_median": baseline_median, "ratio": ratio, "signal": signal,
        })

    return out


def classify_duration_experimental(events: list) -> list:
    """
    Samo-kalibrujący, eksperymentalny podział sesji na "short"/"long"
    wg mediany duration_min bieżącej populacji — proxy hipotezy
    "dzieci kąpią się dłużej niż dorośli" (przy jednoosobowych sesjach;
    dla sesji z n_bursts>1 to już raczej długość całej "rundy" rodziny,
    nie jednej osoby — n_bursts jest osobnym, też eksperymentalnym,
    przybliżeniem liczby osób w sesji). Liczone na bieżąco z przekazanej
    listy (nie przechowywane w DB), żeby nie "zastygało" błędnie w miarę
    napływu nowych danych. Niska pewność — oznaczone jako eksperymentalne.
    """
    sessions = [e for e in events if e.get("category") == "session" and e.get("duration_min") is not None]
    median_dur = statistics.median([e["duration_min"] for e in sessions]) if sessions else None

    for e in events:
        e["experimental"] = True
        if e.get("category") == "session" and median_dur is not None:
            e["duration_class"] = "long" if e["duration_min"] > median_dur else "short"
        else:
            e["duration_class"] = None
    return events


# ══════════════════════════════════════════════════════════════
# ORKIESTRACJA — jedyna funkcja dotykająca DB
# ══════════════════════════════════════════════════════════════

def run_scan(cfg: dict, since_ts: Optional[str] = None, until_ts: Optional[str] = None,
             source: str = "daily") -> dict:
    """
    Skanuje boiler_history (opcjonalnie w zakresie since_ts..until_ts,
    None = cała historia — backfill), wykrywa zdarzenia i zapisuje
    do draw_events. Zwraca podsumowanie do logów.
    """
    import data.database as db

    scanned = 0
    runs_found = 0
    by_category = {"session": 0, "subthreshold": 0}
    all_events = []
    cur_rows = []
    prev_ts = None
    gap_s = cfg.get("usage_run_gap_max_min", 5) * 60

    def _flush_run():
        nonlocal runs_found
        if len(cur_rows) < 2:
            return
        runs_found += 1
        for ev in _find_events_in_run(cur_rows, cfg):
            ev["source"] = source
            by_category[ev["category"]] += 1
            all_events.append(ev)

    for ts, temp, heating in db.iter_boiler_history_for_scan(since_ts=since_ts, until_ts=until_ts):
        scanned += 1
        not_heating = not heating and temp is not None and temp > 0
        if not not_heating:
            _flush_run()
            cur_rows, prev_ts = [], None
            continue

        if prev_ts is not None and (ts - prev_ts).total_seconds() > gap_s:
            _flush_run()
            cur_rows = []
        cur_rows.append((ts, temp))
        prev_ts = ts

    _flush_run()

    inserted = db.insert_draw_events_bulk(all_events) if all_events else 0

    result = {
        "scanned_rows": scanned,
        "runs_found": runs_found,
        "events_by_category": by_category,
        "inserted": inserted,
    }
    log.info(f"UsageDetector.run_scan({source}): {result}")
    return result
