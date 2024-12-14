import pytest
from datetime import datetime
from main import *
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message

# 1. Тест корректного времени
def test_parse_time_valid():
    now = datetime.now()
    result = parse_time("12:30")
    assert result is not None
    assert result.hour == 12
    assert result.minute == 30
    assert result.year == now.year
    assert result.month == now.month
    assert result.day == now.day

# 2. Тест граничного случая: полночь
def test_parse_time_midnight():
    now = datetime.now()
    result = parse_time("00:00")
    assert result is not None
    assert result.hour == 0
    assert result.minute == 0
    assert result.year == now.year
    assert result.month == now.month
    assert result.day == now.day

# 3. Тест граничного случая: конец дня
def test_parse_time_end_of_day():
    now = datetime.now()
    result = parse_time("23:59")
    assert result is not None
    assert result.hour == 23
    assert result.minute == 59
    assert result.year == now.year
    assert result.month == now.month
    assert result.day == now.day

# 4. Тест некорректного значения времени
def test_parse_time_invalid_hour():
    result = parse_time("24:00")  # Некорректный час
    assert result is None

def test_parse_time_invalid_minute():
    result = parse_time("12:60")  # Некорректная минута
    assert result is None

# 5. Тест некорректного формата строки
def test_parse_time_invalid_format():
    result = parse_time("12-30")  # Неверный разделитель
    assert result is None

# 6. Тест пустой строки
def test_parse_time_empty_string():
    result = parse_time("")
    assert result is None

@pytest.fixture
def setup_test_db():
    # Создаем временную базу данных в памяти
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            creation_date TEXT,
            remind_time TEXT
        )
    """)
    conn.commit()

    # Возвращаем соединение и курсор для тестов
    return conn, cursor

    conn.close()

def test_reorder_ids_no_data(setup_test_db):
    conn, cursor = setup_test_db

    # Для chat_id = 999 нет напоминаний
    reorder_ids(999)

    # Проверяем, что таблица пуста для chat_id = 999
    cursor.execute("SELECT * FROM reminders WHERE chat_id = 999")
    results = cursor.fetchall()
    assert results == []

def test_reorder_ids_text(setup_db):
    # Разворачиваем фикстуру для получения соединения и курсора
    conn, cursor = setup_db

    # Добавляем несколько напоминаний в таблицу
    cursor.execute("""
    INSERT INTO reminders (chat_id, id, text, remind_time, creation_date)
    VALUES
    (123, 1, 'Напоминание 1', '2024-12-15 14:30', '2024-12-14'),
    (123, 2, 'Напоминание 2', '2024-12-16 15:00', '2024-12-15'),
    (123, 3, 'Напоминание 3', '2024-12-17 16:00', '2024-12-16')
    """)

    # Запускаем функцию перенумерации для чата с ID 123
    reorder_ids(123)

    # Проверяем, что ID напоминаний были перенумерованы правильно
    cursor.execute("SELECT id, text FROM reminders WHERE chat_id = 123 ORDER BY creation_date, remind_time")
    rows = cursor.fetchall()

    assert rows[0][1] == 'Напоминание 1'  # Проверяем текст первого напоминания
    assert rows[1][1] == 'Напоминание 2'  # Проверяем текст второго напоминания
    assert rows[2][1] == 'Напоминание 3'  # Проверяем текст третьего напоминания

    conn.close()

# Тест 1: команда передана с неверным форматом
@pytest.mark.asyncio
async def test_remind_handler_invalid_format():
    message = MagicMock()  # Мок для сообщения
    message.text = "/remind 2023-12-12 12"  # Пропущен текст напоминания
    message.answer = AsyncMock()  # Мок для метода answer

    await remind_handler(message)

    message.answer.assert_called_once_with("Формат команды: /remind YYYY-MM-DD HH:MM текст")

# Тест 2: Некорректная дата в команде
@pytest.mark.asyncio
async def test_remind_handler_invalid_date():
    message = MagicMock()  # Мок для сообщения
    message.text = "/remind 2023-99-99 12:00 Тестовое напоминание"  # Неверный формат даты
    message.answer = AsyncMock()

    await remind_handler(message)

    message.answer.assert_called_once_with("Некорректный формат даты. Используйте YYYY-MM-DD.")

# Тест 3: Напоминание на прошлую дату
@pytest.mark.asyncio
async def test_remind_handler_past_datetime():
    # Создаем дату в прошлом
    past_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    message = MagicMock()
    message.text = f"/remind {past_date} 12:00 Тестовое напоминание"  # Напоминание на прошлую дату
    message.answer = AsyncMock()

    await remind_handler(message)

    message.answer.assert_called_once_with("Нельзя установить напоминание в прошлом.")

# Тест 1: Некорректная дата в команде
@pytest.mark.asyncio
async def test_daily_handler_invalid_date():
    message = MagicMock()  # Мок для сообщения
    message.text = "/daily 2023-12-12 12"  # Пропущен текст напоминания
    message.answer = AsyncMock()

    await daily_handler(message)

    message.answer.assert_called_once_with("Некорректный формат времени. Используйте HH:MM.")

# Тест 2: команда передана с неверным форматом
@pytest.mark.asyncio
async def test_daily_handler_invalid_format():
    message = MagicMock()  # Мок для сообщения
    message.text = "/remind 12:11"  # Пропущен текст напоминания
    message.answer = AsyncMock()  # Мок для метода answer

    await daily_handler(message)

    message.answer.assert_called_once_with("Формат команды: /daily HH:MM текст")

@pytest.fixture
def setup_db():
    conn = sqlite3.connect(':memory:')  # Используем базу данных в памяти для теста
    cursor = conn.cursor()

    # Создаем таблицу
    cursor.execute("""
    CREATE TABLE reminders (
        chat_id INTEGER,
        id INTEGER PRIMARY KEY,
        text TEXT NOT NULL,
        remind_time TEXT NOT NULL,
        creation_date TEXT NOT NULL,
        is_daily INTEGER NOT NULL
    )
    """)
    conn.commit()

    return conn, cursor

