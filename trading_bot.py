"""
Торговый бот — шаблон для создания своей стратегии.

Откройте этот файл и измените только две секции:
  1. НАСТРОЙКИ — ваши данные для подключения
  2. СТРАТЕГИЯ — ваша торговая логика

Всё, что ниже линии «НЕ МЕНЯТЬ», трогать не нужно.
"""

# ╔═══════════════════════════════════════════════════════════════════╗
# ║                                                                   ║
# ║                    1. НАСТРОЙКИ ПОДКЛЮЧЕНИЯ                       ║
# ║                                                                   ║
# ║   Заполните поля ниже вашими данными из Trading Simulator         ║
# ║                                                                   ║
# ╚═══════════════════════════════════════════════════════════════════╝

API_BASE_URL = "http://trading-sim.culab.ru/api" # URL платформы (обычно менять не нужно)
API_TOKEN    = "YOUR_TOKEN_HERE"                  # Ваш токен (вставьте из личного кабинета)
SESSION_ID   = "YOUR_SESSION_ID_HERE"             # ID сессии (вставьте из списка сессий или скопируйте с url сайта с графиком)

# Список тикеров для торговли и количество акций за одну сделку для каждого
TICKERS = {
    "SBER": 1,   # Тикер: количество акций за сделку
    "GAZP": 1,   # Добавьте сколько нужно тикеров
}


# ╔═══════════════════════════════════════════════════════════════════╗
# ║                                                                   ║
# ║                    2. ВАША СТРАТЕГИЯ                              ║
# ║                                                                   ║
# ║   Здесь вы решаете: покупать, продавать или ждать.                ║
# ║   Меняйте логику внутри функции decide() как хотите.             ║
# ║                                                                   ║
# ╚═══════════════════════════════════════════════════════════════════╝

# --- Параметры стратегии (можете добавлять свои) ---

MA_SHORT = 10       # Короткая скользящая средняя (быстрая, реагирует на изменения)
MA_MID   = 60       # Средняя скользящая средняя
MA_LONG  = 300      # Длинная скользящая средняя (медленная, показывает тренд)


def decide(prices, position, bid, ask, trade_amount):
    """
    Функция принятия решения. Вызывается для каждого тикера при появлении новой цены.

    Что приходит на вход:
        prices       — список всех прошлых цен (от старых к новым)
        position     — сколько акций у вас сейчас в портфеле (0 = ничего нет)
        bid          — цена, по которой можно ПРОДАТЬ прямо сейчас
        ask          — цена, по которой можно КУПИТЬ прямо сейчас
        trade_amount — сколько акций покупать/продавать за раз

    Что нужно вернуть (одно из трёх):
        ("BUY",  количество, цена)  — купить акции по цене ask
        ("SELL", количество, цена)  — продать акции по цене bid
        ("HOLD", 0, 0)             — ничего не делать, подождать
    """

    # Считаем скользящие средние
    ma_short = moving_average(prices, MA_SHORT)
    ma_mid   = moving_average(prices, MA_MID)
    ma_long  = moving_average(prices, MA_LONG)

    # Если данных пока мало — ждём
    if ma_short is None or ma_mid is None or ma_long is None:
        return "HOLD", 0, 0

    # ── Правило на ПОКУПКУ ──
    # Короткая средняя выше средней и длинной → цена растёт → покупаем
    if ma_short > ma_mid and ma_short > ma_long:
        if position == 0:  # Покупаем только если ещё ничего не держим
            return "BUY", trade_amount, ask

    # ── Правило на ПРОДАЖУ ──
    # Короткая средняя ниже средней и длинной → цена падает → продаём
    if ma_short < ma_mid and ma_short < ma_long:
        if position > 0:  # Продаём только если есть что продавать
            return "SELL", min(trade_amount, position), bid

    # Ни одно правило не сработало — ждём
    return "HOLD", 0, 0


# ╔═══════════════════════════════════════════════════════════════════╗
# ║                                                                   ║
# ║   ══════════════ НЕ МЕНЯТЬ НИЖЕ ЭТОЙ ЛИНИИ ══════════════        ║
# ║                                                                   ║
# ║   Ниже — техническая часть: подключение к серверу, получение      ║
# ║   цен, отправка сделок. Менять не нужно.                          ║
# ║                                                                   ║
# ╚═══════════════════════════════════════════════════════════════════╝

import time
import random
import logging
from collections import deque

import requests

# ─────────────────────────── ЛОГИРОВАНИЕ ─────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bot")

# ─────────────────────────── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ─────────────

POLL_INTERVAL = 60  # Секунд между опросами (цены обновляются раз в минуту)


def moving_average(prices, window):
    """Скользящая средняя по последним `window` значениям."""
    if len(prices) < window:
        return None
    total = 0.0
    it = iter(reversed(prices))
    for _ in range(window):
        total += next(it)
    return total / window


def get_position(portfolio, ticker):
    """Количество акций тикера в портфеле."""
    for item in portfolio.get("items", []):
        if item["ticker"] == ticker:
            return item["quantity"]
    return 0


# ─────────────────────────── API-КЛИЕНТ ──────────────────────────

class APIClient:
    def __init__(self, base_url, token):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": base_url.replace("/api", "/"),
            "Origin": base_url.replace("/api", ""),
        })

    def get_price_history(self, session_id, ticker):
        r = self.session.get(
            f"{self.base}/session_moment/history/{ticker}",
            params={"session_id": session_id},
        )
        r.raise_for_status()
        return r.json()

    def get_current_price(self, session_id, ticker):
        r = self.session.get(
            f"{self.base}/trade/get-current-price-of-instrument",
            params={"session_id": session_id, "instrument_ticker": ticker},
        )
        r.raise_for_status()
        return r.json()

    def get_portfolio(self, session_id):
        r = self.session.get(
            f"{self.base}/trade/portfolio",
            params={"session_id": session_id},
        )
        r.raise_for_status()
        return r.json()

    def buy(self, session_id, ticker, price, amount):
        r = self.session.post(
            f"{self.base}/trade/buy",
            params={
                "session_id": session_id,
                "instrument_ticker": ticker,
                "price": price,
                "amount": amount,
            },
        )
        r.raise_for_status()
        return r.json()["money_amount"]

    def sell(self, session_id, ticker, price, amount):
        r = self.session.post(
            f"{self.base}/trade/sell",
            params={
                "session_id": session_id,
                "instrument_ticker": ticker,
                "price": price,
                "amount": amount,
            },
        )
        r.raise_for_status()
        return r.json()["money_amount"]


# ─────────────────────────── ГЛАВНЫЙ ЦИКЛ ───────────────────────

def main():
    api = APIClient(API_BASE_URL, API_TOKEN)

    # Состояние для каждого тикера: история цен и текущая позиция
    ticker_prices = {}    # ticker -> deque цен
    ticker_positions = {} # ticker -> количество акций

    # Загружаем историю цен и позиции для всех тикеров
    portfolio = api.get_portfolio(SESSION_ID)

    for ticker in TICKERS:
        ticker_prices[ticker] = deque()

        log.info("Загрузка истории цен для %s ...", ticker)
        try:
            history = api.get_price_history(SESSION_ID, ticker)
            for m in history:
                ticker_prices[ticker].append(float(m["p_mid"]))
            log.info("  %s: загружено %d точек", ticker, len(ticker_prices[ticker]))
        except requests.HTTPError as e:
            if e.response.status_code in (403, 404):
                log.info("  %s: история недоступна — начинаем с нуля", ticker)
            else:
                raise

        ticker_positions[ticker] = get_position(portfolio, ticker)
        log.info("  %s: текущая позиция %d акций", ticker, ticker_positions[ticker])

    last_day = None
    last_index = None

    log.info("Бот запущен. Тикеры: %s. Опрос каждые %d сек.", ", ".join(TICKERS), POLL_INTERVAL)
    log.info("─" * 60)

    while True:
        try:
            # Получаем цену первого тикера для проверки time_index
            first_ticker = next(iter(TICKERS))
            quote = api.get_current_price(SESSION_ID, first_ticker)

            cur_day = quote["current_day"]
            cur_index = quote["current_index"]

            # Пропускаем, если индекс не изменился
            if cur_day == last_day and cur_index == last_index:
                time.sleep(POLL_INTERVAL + random.uniform(-5, 5))
                continue

            last_day = cur_day
            last_index = cur_index

            # Обрабатываем каждый тикер
            for ticker, trade_amount in TICKERS.items():
                try:
                    q = api.get_current_price(SESSION_ID, ticker) if ticker != first_ticker else quote
                    bid = float(q["bid_price"])
                    ask = float(q["ask_price"])
                    mid = (bid + ask) / 2.0

                    ticker_prices[ticker].append(mid)
                    position = ticker_positions[ticker]

                    log.info(
                        "День %d  Индекс %3d | %s mid=%.2f | Позиция: %d",
                        cur_day, cur_index, ticker, mid, position,
                    )

                    # Вызываем стратегию для этого тикера
                    action, amount, price = decide(
                        ticker_prices[ticker], position, bid, ask, trade_amount,
                    )

                    if action == "BUY" and amount > 0:
                        try:
                            balance = api.buy(SESSION_ID, ticker, price, amount)
                            ticker_positions[ticker] += amount
                            log.info(
                                "  >>> BUY %d x %s @ %.2f | Баланс: %.2f",
                                amount, ticker, price, balance,
                            )
                        except requests.HTTPError as e:
                            log.warning("  !!! %s: ошибка покупки: %s", ticker, e.response.text)

                    elif action == "SELL" and amount > 0:
                        try:
                            balance = api.sell(SESSION_ID, ticker, price, amount)
                            ticker_positions[ticker] -= amount
                            log.info(
                                "  <<< SELL %d x %s @ %.2f | Баланс: %.2f",
                                amount, ticker, price, balance,
                            )
                        except requests.HTTPError as e:
                            log.warning("  !!! %s: ошибка продажи: %s", ticker, e.response.text)

                except requests.HTTPError as e:
                    log.warning("  !!! %s: ошибка получения цены: %s", ticker, e.response.text)

        except requests.HTTPError as e:
            code = e.response.status_code
            if code == 404:
                log.info("Торговый день закончился. Ожидание следующего дня...")
            elif code == 403:
                log.info("Сессия на паузе. Ожидание...")
            else:
                log.error("HTTP ошибка %d: %s", code, e.response.text)
        except requests.ConnectionError:
            log.warning("Нет соединения с сервером. Повтор через %d сек...", POLL_INTERVAL)

        time.sleep(POLL_INTERVAL + random.uniform(-5, 5))


if __name__ == "__main__":
    main()
