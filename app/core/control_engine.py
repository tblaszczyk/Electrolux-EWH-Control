"""
core/control_engine.py ★
Serce systemu — jedyne miejsce podejmowania decyzji sterujących.
Pętla co 10 sekund:
  1. Opróżnij kolejkę komend
  2. Odczytaj watchdog
  3. Oblicz Decision
  4. Przelicz stan (state machine)
  5. Wyślij komendę do bojlera (jeśli zmiana)
  6. Zaloguj wszystko

Żaden inny moduł nie wysyła komend do bojlera.
"""

import time
import logging
import threading
from datetime import datetime
from typing import Optional

import data.database as db
from core import boiler_client as _bc_module
from core import inverter_client as _inv_module
from core.decision_logic import compute as compute_decision, Decision
from core.state_machine   import transition as state_transition
from core.pv_manager      import pv_manager
from core.scheduler       import scheduler
from core.watchdog        import watchdog
from service.command_queue  import queue as cmd_queue
from service.runtime_state  import runtime

from core.notifier import notifier

log = logging.getLogger("boiler.engine")

# ══════════════════════════════════════════════════════════════
# CONTROL ENGINE
# ══════════════════════════════════════════════════════════════

class ControlEngine:

    def __init__(self, config: dict, boiler_client, inverter_client):
        self._cfg      = config
        self._boiler   = boiler_client
        self._inverter = inverter_client
        self._running  = False
        self._thread:  Optional[threading.Thread] = None

        # Timery pomocnicze
        self._last_data_log:    float = 0.0
        self._last_valid_temp:  float = 0.0
        self._last_pv_poll:     float = 0.0
        self._last_boiler_poll: float = 0.0

        # Konfiguracja histerezy w pv_manager i watchdog
        # histereza przekazywana przez cfg do pv_manager.update()
        watchdog.set_timeout(config.get("watchdog_timeout_s", 30))

        log.info("ControlEngine: zainicjalizowany")

    # ── Start / Stop ──────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        scheduler.reload()
        runtime.set_state("STARTING")

        self._thread = threading.Thread(
            target=self._loop, name="control-engine", daemon=True
        )
        self._thread.start()
        log.info("ControlEngine: uruchomiony")

    def stop(self) -> None:
        self._running = False
        log.info("ControlEngine: zatrzymany")

    # ── Główna pętla ──────────────────────────────────────────

    def _loop(self) -> None:
        loop_s = self._cfg.get("control_loop_s", 10)

        while self._running:
            t_start = time.time()
            try:
                self._tick()
            except Exception as e:
                log.error(f"ControlEngine tick error: {e}", exc_info=True)
            elapsed = time.time() - t_start
            sleep_s = max(0.0, loop_s - elapsed)
            time.sleep(sleep_s)

    def _tick(self) -> None:
        now = time.time()

        # ── 0. Sprawdź czy system jest włączony ───────────────
        # Zawsze przetwarzaj kolejkę (żeby obsłużyć SET_SYSTEM_ENABLED)
        self._process_commands()

        if not runtime.system_enabled:
            return  # System OFF — nie wykonuj dalszych akcji

        # ── 1. Poll bojlera ────────────────────────────────────
        if now - self._last_boiler_poll >= self._cfg.get("boiler_poll_s", 20):
            self._poll_boiler()
            self._last_boiler_poll = now

        # ── 2. Poll inwertera ──────────────────────────────────
        if now - self._last_pv_poll >= self._cfg.get("inverter_poll_s", 30):
            self._poll_inverter()
            self._last_pv_poll = now

        # ── 4. Oblicz decyzję ─────────────────────────────────
        decision = self._compute()

        # ── 5. Przejście stanu ────────────────────────────────
        old_state = runtime.current_state
        new_state = state_transition(
            current_state=old_state,
            decision=decision,
            boiler_temp=runtime.boiler_last_temp,
            boiler_target=runtime.boiler_last_target,
        )

        if new_state != old_state:
            runtime.set_state(new_state)
            db.log_event(
                category="STATE_CHANGE",
                message=f"{old_state} → {new_state}",
                state_from=old_state,
                state_to=new_state,
                mode=decision.mode,
                reason=decision.reason,
            )

        # ── 6. Zapisz decyzję w runtime ───────────────────────
        runtime.record_decision(
            mode=decision.mode,
            temp=decision.target_temp,
            power=decision.power_limit,
            reason=decision.reason,
        )

        # ── 7. Wyślij komendę do bojlera ──────────────────────
        self._execute(decision, new_state)

        # ── 8. Zapis historii (co 60s) ────────────────────────
        if now - self._last_data_log >= self._cfg.get("data_log_interval_s", 60):
            self._log_history(new_state, decision)
            self._last_data_log = now

    # ── Polling bojlera ───────────────────────────────────────

    def _poll_boiler(self) -> None:
        status = self._boiler.get_status()
        if status and status.get("online"):
            watchdog.boiler_ok()
            runtime.update_boiler(
                temp_current=float(status.get("temp_current", 0)),
                temp_target= float(status.get("temp_target",  0)),
                power_w=     int(status.get("power_w",    0)),
                heating=     bool(status.get("heating",   False)),
                online=      True,
            )
            log.debug(
                f"Bojler: {status.get('temp_current')}°C / "
                f"target={status.get('temp_target')}°C / "
                f"power={status.get('power_w')}W"
            )
        else:
            runtime.update_boiler(
                temp_current=runtime.boiler_last_temp,
                temp_target= runtime.boiler_last_target,
                power_w=     0,
                heating=     False,
                online=      False,
            )
            db.log_event(
                category="COMM_ERROR",
                message="Brak odpowiedzi od bojlera",
            )
        notifier.track(
            "boiler_offline", bad=not (status and status.get("online")), after_s=300,
            title="Bojler2: brak łączności z bojlerem",
            msg="Sterownik bojlera nie odpowiada od ponad 5 minut (sprawdź zasilanie i Wi-Fi).",
            ok_title="Bojler2: bojler znów odpowiada", ok_msg="Łączność ze sterownikiem bojlera przywrócona.")

    # ── Polling inwertera ─────────────────────────────────────

    def _poll_inverter(self) -> None:
        data = self._inverter.get_data()
        if data.get("online"):
            pv_power = float(data.get("pv_power", 0))
            pv_info  = pv_manager.update(pv_power, self._cfg)
            watchdog.pv_ok()
            runtime.update_pv(
                pv_power=    pv_power,
                power_level= 1 if pv_info["active"] else 0,
                today_kwh=   float(data.get("today_kwh", 0)),
                online=      True,
            )
            runtime.pv_info = pv_info
            log.debug(
                f"PV: {pv_power:.0f}W active={pv_info['active']} "
                f"power={pv_info['power_w']}W reason={pv_info['reason']}"
            )
        else:
            runtime.update_pv(
                pv_power=0.0, power_level=0, today_kwh=runtime.pv_today_kwh, online=False
            )
            runtime.pv_info = {"active": False, "power_w": 0, "reason": "PV offline"}

    # ── Przetwarzanie kolejki ─────────────────────────────────

    def _process_commands(self) -> None:
        commands = cmd_queue.drain()
        for cmd in commands:
            log.info(f"Engine: komenda {cmd.type} od '{cmd.username}': {cmd.payload}")
            try:
                if cmd.type == "SET_MANUAL":
                    temp  = int(cmd.payload["temp"])
                    power = int(cmd.payload["power_limit"])
                    runtime.set_manual(temp, power)
                    db.log_event(
                        category="USER_ACTION",
                        message=f"SET_MANUAL: {temp}°C, {power}W",
                        mode="MANUAL",
                    )

                elif cmd.type == "SET_AUTO":
                    runtime.set_auto()
                    db.log_event(category="USER_ACTION", message="SET_AUTO")

                elif cmd.type == "SET_IDLE_MODE":
                    mode = cmd.payload["mode"]
                    runtime.set_idle_mode(mode)
                    db.log_event(
                        category="USER_ACTION",
                        message=f"SET_IDLE_MODE: {mode}",
                    )

                elif cmd.type == "RELOAD_SCHEDULE":
                    scheduler.reload()
                    db.log_event(
                        category="SYSTEM", message="Harmonogram wczytany ponownie"
                    )

                elif cmd.type == "SET_SYSTEM_ENABLED":
                    enabled = bool(cmd.payload.get("enabled", True))
                    runtime.set_system_enabled(enabled)
                    if not enabled:
                        # Natychmiast wyślij wyłączenie do bojlera
                        self._boiler.set_target(20, 0)
                        db.log_event(
                            category="USER_ACTION",
                            message="SYSTEM OFF — bojler wyłączony",
                            mode="OFF",
                        )
                    else:
                        db.log_event(
                            category="USER_ACTION",
                            message="SYSTEM ON — wznowienie",
                        )
                        self._last_boiler_poll = 0.0
                        self._last_pv_poll = 0.0

            except Exception as e:
                log.error(f"Engine: błąd przetwarzania komendy {cmd.type}: {e}")

    # ── Obliczanie decyzji ────────────────────────────────────

    def _compute(self) -> Decision:
        pv_info = getattr(runtime, 'pv_info', {"active": False, "power_w": 0, "target_temp": 65, "reason": ""})
        if not watchdog.pv_alive() and not runtime.pv_online:
            pv_info = {"active": False, "power_w": 0, "target_temp": 65, "reason": "PV offline"}

        schedule_slot = scheduler.get_active_slot()

        decision = compute_decision(
            boiler_temp=    runtime.boiler_last_temp,
            boiler_online=  watchdog.boiler_alive(),
            manual_mode=    runtime.current_mode == "MANUAL",
            manual_temp=    runtime.manual_temp,
            manual_power=   runtime.manual_power_limit,
            schedule_slot=  schedule_slot,
            pv_active=      pv_info.get("active", False),
            pv_power_w=     pv_info.get("power_w", 0),
            pv_target_temp= pv_info.get("target_temp", self._cfg.get("pv_target_temp", 65)),
            pv_reason=      pv_info.get("reason", ""),
            idle_mode=      runtime.idle_mode,
            max_temp=       self._cfg.get("max_temp_c", 75),
        )
        log.debug(f"Engine decision: {decision}")
        return decision

    # ── Wykonanie ─────────────────────────────────────────────

    def _execute(self, decision: Decision, state: str) -> None:
        """Wyślij komendę do bojlera jeśli coś się zmieniło."""

        # W stanach krytycznych nie wysyłaj
        if state in ("ERROR", "NO_COMMUNICATION", "OFF"):
            return

        # IDLE=off lub PV nieaktywne → wyślij wyłączenie jeśli bojler jeszcze grzeje
        if (decision.mode == "IDLE" and decision.target_temp == 0) or            (decision.mode == "PV" and decision.power_limit == 0):
            last = runtime.last_command_sent
            if last and last.get("power_w", 0) > 0:
                self._boiler.set_target(temp_c=20, power_w=0)
                runtime.record_command(20, 0)
            return

        # Sprawdź czy coś się zmieniło od ostatniej komendy
        last = runtime.last_command_sent
        if (last and
            last.get("temp")    == decision.target_temp and
            last.get("power_w") == decision.power_limit):
            return   # bez zmian

        # Wyślij
        ok = self._boiler.set_target(
            temp_c=  decision.target_temp,
            power_w= decision.power_limit,
        )
        if ok:
            runtime.record_command(decision.target_temp, decision.power_limit)
            db.log_event(
                category="COMMAND",
                message=(
                    f"set_target: {decision.target_temp}°C, "
                    f"{decision.power_limit}W | {decision.reason}"
                ),
                mode=decision.mode,
                reason=decision.reason,
            )
        else:
            log.error(
                f"Engine: set_target nieudane "
                f"({decision.target_temp}°C, {decision.power_limit}W)"
            )

    # ── Zapis historii ────────────────────────────────────────

    def _log_history(self, state: str, decision: Decision) -> None:
        # Jeśli temp==0 (błędny odczyt) użyj ostatniej dobrej wartości
        temp = runtime.boiler_last_temp
        if temp <= 0:
            temp = self._last_valid_temp
        elif self._last_valid_temp > 0 and (temp - self._last_valid_temp) > 5.0:
            # Peak — nagły wzrost >5°C w ciągu 60s → odrzuć
            log.warning(
                f"_log_history: peak temp odrzucony "
                f"({self._last_valid_temp}→{temp}°C, delta={temp-self._last_valid_temp:.1f}°C)"
            )
            temp = self._last_valid_temp
        else:
            self._last_valid_temp = temp

        db.insert_boiler_history(
            temp_current= temp,
            temp_target=  decision.target_temp,
            power_w=      decision.power_limit if decision.power_limit > 0 else runtime.boiler_last_power_w,
            state=        state,
            mode=         decision.mode,
            pv_power_w=   runtime.pv_last_power,
            heating=      temp < decision.target_temp and decision.power_limit > 0,
        )
