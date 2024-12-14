import asyncio
import sqlite3

from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import Router

from datab import cursor, conn

API_TOKEN = "8048477049:AAGiv4SbbY7sSHPUMgglkO729UMPvibLe4c"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


def parse_time(time_str: str):
    """Парсит строку времени в формате "HH:MM" и возвращает объект datetime
     с текущей датой.

        Функция принимает строку времени в формате "HH:MM" и пытается
        преобразовать ее в объект `datetime`. Если преобразование успешно,
        возвращается объект 'datetime' с текущей датой и переданным временем.
        В случае ошибки (например, если строка не соответствует формату или
        время некорректно), функция возвращает `None`.

        Аргумент:
            time_str (str): Строка времени в формате "HH:MM".



        Возвращаемое значение:
            datetime|None: Объект `datetime` с текущей датой и переданным
            временем, если формат верный.
            Возвращает `None`, если строка не может быть преобразована в
            допустимый формат времени.

        Исключение:
            ValueError: Если время в строке не соответствует формату "HH:MM"
             или не является допустимым временем.

        Пример:
            >>> parse_time("12:30")
            datetime.datetime(2024, 12, 13, 12, 30, 0)

            >>> parse_time("25:00")
            None

        """
    try:
        now = datetime.now()
        return datetime.strptime(time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
    except ValueError:
        return None


def reorder_ids(chat_id: int):
    """Перенумеровывает идентификаторы напоминаний для указанного чата, упорядочивая их по дате и времени создания.

      Функция выполняет выборку всех напоминаний из базы данных для заданного чата, сортирует их по
      дате создания ('creation_date'), времени напоминания ('remind_time') и идентификатору строки ('rowid').
      Затем переназначает уникальные идентификаторы (ID) для каждого напоминания в последовательности, начиная с 1.
      Это полезно, если напоминания были удалены, и необходимо обновить ID остальных напоминаний.

      Аргумент:
          chat_id (int): Идентификатор чата, для которого нужно перенумеровать напоминания.
      Возвращаемое значение:
           None
      Исключение:
           None

      Пример:
          >>> reorder_ids(1289)
          Напоминания для чата с ID 1289 будут перенумерованы в порядке их создания.

      """
    cursor.execute("""
            SELECT rowid, creation_date, remind_time FROM reminders
            WHERE chat_id = ?
            ORDER BY creation_date, remind_time, rowid
        """, (chat_id,))
    rows = cursor.fetchall()

    new_id = 1
    for row in rows:
        rowid = row[0]

        cursor.execute("UPDATE reminders SET id = ? WHERE chat_id = ? AND rowid = ?", (new_id, chat_id, rowid))

        new_id += 1

    conn.commit()


def get_next_id_for_chat(chat_id: int) -> int:
    """Возвращает следующий доступный идентификатор (ID) для напоминания в указанном чате.

        Эта функция выполняет запрос к базе данных, чтобы получить максимальный идентификатор (`id`)
        среди всех напоминаний, относящихся к определенному чату. Если в базе данных для этого чата нет напоминаний,
        функция возвращает 1. В противном случае возвращается максимальный
        идентификатор + 1, что соответствует следующему доступному ID.

        Аргумент:
            chat_id (int): Идентификатор чата, для которого нужно получить следующий доступный ID.

        Возвращаемое значение:
            int: Следующий доступный идентификатор для нового напоминания в данном чате.

        Исключение:
            None

        Пример:
            >>> get_next_id_for_chat(1289)
            5  # если максимальный id для чата 1289 равен 4, то функция вернет 5.

        """
    cursor.execute("SELECT MAX(id) FROM reminders WHERE chat_id = ?", (chat_id,))
    max_id = cursor.fetchone()[0]
    if max_id is None:
        return 1
    else:
        return max_id + 1


@router.message(Command("start"))
async def start_handler(message: Message):
    """Обработчик команды /start, который отправляет пользователю информацию о доступных командах бота.

        Когда пользователь отправляет команду `/start`, бот предоставляет список доступных команд
        (/remind, /daily, /weekly, /list, /delete, /complete, /notcomplete, /stats) и их назначение.
        Это помогает пользователю понять, какие действия он может выполнить с помощью бота.

        Аргумент:
            message (Message): Сообщение, отправленное пользователем, содержащее команду `/start`.

        Возвращаемое значение:
            None: Бот отвечает пользователю с сообщением о результате выполнения команды.

        Исключение:
            None

        Пример:
            1. Пользователь отправляет команду `/start`.
            2. Бот отвечает с приветственным сообщением и списком команд.

        """
    await message.answer(
        "Привет! Я бот-напоминалка. Вот что я умею:\n"
        "/remind YYYY-MM-DD HH:MM текст — создать разовое напоминание\n"
        "/daily HH:MM текст — создать ежедневное напоминание\n"
        "/weekly DAY HH:MM текст — создать напоминание на день недели (0-6, где 0 — понедельник)\n"
        "/list — показать все напоминания\n"
        "/delete ID — удалить напоминание по ID\n"
        "/complete ID — отметить напоминание как выполненное\n"
        "/notcomplete ID — отметить напоминание как невыполненное\n"
        "/stats YYYY-MM-DD — статистика за выбранную дату"
    )


@router.message(Command("remind"))
async def remind_handler(message: Message):
    """Обработчик команды /remind, который создает разовое напоминание для пользователя.

        Когда пользователь отправляет команду `/remind` с указанием даты (`date_str`: в формате `YYYY-MM-DD`),
        времени (`time_str`: в формате `HH:MM`) и текста (`text`), бот создает разовое напоминание, которое будет
        активироваться в указанное время. В случае ошибок в формате данных или если время напоминания установлено в
        прошлом, бот отправляет соответствующее сообщение.
        Если формат данных некорректен, бот отправляет пользователю сообщение с инструкциями.
        Если команда успешно выполнена, бот сохраняет напоминание в базе данных и подтверждает установку напоминания.

        Аргумент:
            message (Message): Сообщение от пользователя, содержащее команду `/remind`, за которой следует дата, время
            и текст напоминания.

        Возвращаемое значение:
            None: Бот отвечает пользователю с сообщением о результате выполнения команды.

        Исключение:
            None

        Пример:
            >>> '/remind 2024-12-15 14:30 Напомни о встрече'
            >>> remind_handler(message)
            "Разовое напоминание установлено на 2024-12-15 14:30: Напомни о встрече. Напоминание установлено!"

        """
    args = message.text.split(' ', 3)
    if len(args) < 4:
        await message.answer("Формат команды: /remind YYYY-MM-DD HH:MM текст")
        return

    date_str, time_str, text = args[1], args[2], args[3]

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        await message.answer("Некорректный формат даты. Используйте YYYY-MM-DD.")
        return

    try:
        remind_time = datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await message.answer("Некорректный формат времени. Используйте HH:MM.")
        return

    remind_datetime = datetime(
        year=date_obj.year,
        month=date_obj.month,
        day=date_obj.day,
        hour=remind_time.hour,
        minute=remind_time.minute
    )

    now = datetime.now()
    if remind_datetime < now:
        await message.answer("Нельзя установить напоминание в прошлом.")
        return

    creation_date = datetime.now().date()
    new_id = get_next_id_for_chat(message.chat.id)

    cursor.execute(
        "INSERT INTO reminders (chat_id, id, text, remind_time, creation_date, is_daily) VALUES (?, ?, ?, ?, ?, ?)",
        (message.chat.id, new_id, text, remind_datetime, creation_date, 0))
    conn.commit()
    # reorder_ids(message.chat.id)

    await message.answer(
        f"Разовое напоминание установлено на {date_obj.strftime('%Y-%m-%d')} {remind_time.strftime('%H:%M')}: {text}\n"
        "Напоминание установлено!"
    )


@router.message(Command("daily"))
async def daily_handler(message: Message):
    """Обрабатывает команду /daily и создает ежедневное напоминание.

        Эта функция принимает команду, извлекает время и текст напоминания, проверяет правильность формата времени,
        и если время невалидное или раньше текущего, то корректирует его, добавляя сутки. Напоминание сохраняется
        в базе данных с флагом "ежедневное", и ID напоминания обновляется. После этого пользователю отправляется
        сообщение о том, что напоминание установлено.

        Аргумент:
            message (Message): Объект сообщения, который содержит текст команды, информацию о чате и пользователя.

        Возвращаемое значение:
            None: Бот отвечает пользователю с сообщением о результате выполнения команды.

        Исключение:
            None

        Пример:
            Пример использования команды /daily:

            >>> '/daily 15:30 Покупка продуктов'
            >>> daily_handler(message)
            'Ежедневное напоминание установлено на 2024-12-13 15:30: Покупка продуктов Напоминание установлено!'

        """
    args = message.text.split(' ', 2)
    if len(args) < 3:
        await message.answer("Формат команды: /daily HH:MM текст")
        return
    date_str_time_str, text = args[1], args[2]

    remind_time = parse_time(date_str_time_str)
    if not remind_time:
        await message.answer("Некорректный формат времени. Используйте HH:MM.")
        return

    now = datetime.now()
    if remind_time < now:
        remind_time += timedelta(days=1)

    creation_date = datetime.now().date()
    new_id = get_next_id_for_chat(message.chat.id)
    cursor.execute(
        "INSERT INTO reminders (chat_id, id, text, remind_time, creation_date, is_daily) VALUES (?, ?, ?, ?, ?, ?)",
        (message.chat.id, new_id, text, remind_time, creation_date, 1))
    conn.commit()
    # reorder_ids(message.chat.id)
    await message.answer(
        f"Ежедневное напоминание установлено на {remind_time.strftime('%Y-%m-%d %H:%M')}: {text}\n"
        "Напоминание установлено!"
    )


@router.message(Command("weekly"))
async def weekly_handler(message: Message):
    """Обрабатывает команду `/weekly`, создавая еженедельное напоминание на определённый день недели и время.

        Эта функция проверяет параметры команды, получает день недели (где день недели от 0 до 6) и время, а затем
        сохраняет напоминание в базе данных.
        В случае некорректного ввода, бот отправит пользователю соответствующее сообщение.Если команда выполнена
        успешно, бот отправит сообщение, подтверждающее установку напоминания.Если время напоминания меньше текущегo
        времени,оно будет установлено на следующий цикл недели. Напоминание будет повторяться еженедельно в заданный
        день недели и время.

        Аргумент:
            message (Message): Сообщение, полученное от пользователя, содержащее команду `/weekly` и параметры.

        Возвращаемое значение:
            None: Бот отвечает пользователю с сообщением о результате выполнения команды.

        Исключение:
            None

        Пример:
            Пример использования команды /weekly:

            >>> '/weekly 2 14:30 Помыть машину'
            >>> daily_handler(message)
            'Еженедельное напоминание на среду в 14:30 добавлено: Помыть машину Напоминание установлено!'

        """
    args = message.text.split(' ', 3)
    if len(args) < 4:
        await message.answer("Формат команды: /weekly DAY HH:MM текст\nDAY — день недели (0-6, где 0 — понедельник).")
        return
    try:
        day = int(args[1])
        if not 0 <= day <= 6:
            await message.answer("Некорректный день недели. Используйте числа от 0 (понедельник) до 6 (воскресенье).")
            return
    except ValueError:
        await message.answer("Некорректный день недели. Используйте числа от 0 до 6.")
        return

    time_str, text = args[2], args[3]
    remind_time = parse_time(time_str)
    if not remind_time:
        await message.answer("Некорректный формат времени. Используйте HH:MM.")
        return

    now = datetime.now()
    current_week_day = now.weekday()
    delta_days = (day - current_week_day) % 7
    candidate_time = now.replace(hour=remind_time.hour, minute=remind_time.minute, second=0, microsecond=0) + timedelta(
        days=delta_days)
    if candidate_time <= now:
        candidate_time += timedelta(weeks=1)

    creation_date = datetime.now().date()
    new_id = get_next_id_for_chat(message.chat.id)
    cursor.execute(
        "INSERT INTO reminders (chat_id, id, text, remind_time, creation_date, is_daily, week_day) VALUES\
         (?, ?, ?, ?, ?, ?, ?)",
        (message.chat.id, new_id, text, candidate_time, creation_date, 0, day))
    conn.commit()
    # reorder_ids(message.chat.id)

    days_ru = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
    await message.answer(
        f"Еженедельное напоминание на {days_ru[day]} в {time_str} добавлено: {text}\n"
        "Напоминание установлено!"
    )


@router.message(Command("list"))
async def list_handler(message: Message):
    """Обрабатывает команду `/list`, выводя все активные напоминания для пользователя.

        Эта функция запрашивает все напоминания, связанные с данным чатом, из базы данных и отправляет их в виде списка
        с информацией о каждом напоминании, включая ID, текст, дату и время, а также статус выполнения.
        Если у пользователя нет активных напоминаний, бот отправит сообщение: "У тебя нет активных напоминаний."

        Аргумент:
            message (Message): Сообщение, полученное от пользователя, содержащего команду `/list`.

        Возвращаемое значение:
            None: Бот отвечает пользователю с сообщением о результате выполнения команды.

        Исключение:
            None

        Пример:
            >>> '/list'
            'Твои напоминания:
            ID: 1 | Дата: 2024-12-10 | Время: 14:30: Помыть машину (ежедневное)
            ID: 2 | Дата: 2024-12-12 | Время: 09:00: Встретиться с другом (день недели: среда)'

        """
    chat_id = message.chat.id
    cursor.execute(
        "SELECT id, text, remind_time, is_daily, week_day, completed FROM reminders WHERE chat_id = ? ORDER BY id",
        (chat_id,))
    reminders = cursor.fetchall()
    if not reminders:
        await message.answer("У тебя нет активных напоминаний.")
        return

    days_ru = ['понедельник', 'вторник', 'среда', 'четверг', 'пятницу', 'субботу', 'воскресенье']
    response = "Твои напоминания:\n"
    for reminder_id, text, remind_time, is_daily, week_day, completed in reminders:
        remind_dt = datetime.strptime(remind_time, "%Y-%m-%d %H:%M:%S")
        time_str = remind_dt.strftime("%H:%M")
        date_str = remind_dt.strftime("%Y-%m-%d")
        daily_str = " (ежедневное)" if is_daily else ""
        week_day_str = f" (день недели: {days_ru[week_day]})" if week_day is not None else ""
        completed_str = " (выполнено)" if completed else " (не выполнено)"
        response += f"ID: {reminder_id} | Дата: {date_str} | Время: {time_str}: {text}{daily_str}{week_day_str}\
        {completed_str}\n"

    await message.answer(response)


@router.message(Command("delete"))
async def delete_handler(message: Message):
    """Обрабатывает команду /delete, чтобы удалить напоминание по заданному ID.

        Эта команда позволяет пользователю удалить напоминание, указанное по ID.
        Проверяет что ID предоставлен, является числом, иначе отправляет сообщение об ошибке.
        По выданному ID переходит к базе данных, удаляет напоминание с таким идентификатором и с помощью 'reorder_ids'
        упорядочивает остальные напоминания.

        Параметр:
            message (Message): Объект сообщения Telegram, содержащий команду и ее аргументы.

        Возвращаемое значение:
        None: Отправляется ответ пользователю через `message.answer`.

        Исключение:
            None

        Пример:
        >>> '/delete 123'
        >>> delete_handler(message)
        'Напоминание с ID 123 удалено.'
    """
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Формат команды: /delete ID")
        return
    try:
        reminder_id = int(args[1])
        chat_id = message.chat.id
        cursor.execute("DELETE FROM reminders WHERE chat_id = ? AND id = ?", (chat_id, reminder_id))
        conn.commit()
        if cursor.rowcount > 0:
            reorder_ids(chat_id)
            await message.answer(f"Напоминание с ID {reminder_id} удалено.")
        else:
            await message.answer("Напоминание с таким ID не найдено.")
    except ValueError:
        await message.answer("ID должен быть числом.")


@router.message(Command("complete"))
async def complete_handler(message: Message):
    """Обрабатывает команду /complete, чтобы отметить напоминание как выполненное.

        Эта команда позволяет пользователю изменить статус еще невыполненного напоминания на выполненное по
        отправленному ID. Команда проводит работу с базой данных, изменяет completed = 0 на completed = 1. Проверяет
        что ID предоставлен, является числом, информация с таким ID существует, иначе отправляет сообщение об ошибке.

        Параметр:
            message (Message): Объект сообщения Telegram, содержащий команду и ее аргументы.

        Возвращаемое значение:
            None: Отправляется ответ пользователю через `message.answer`.

        Исключение:
            None

        Пример:
            >>> '/complete 123'
            >>> complete_handler(message)
            'Напоминание с ID 123 отмечено как выполненное ✅.'

        """
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Формат команды: /complete ID")
        return
    try:
        reminder_id = int(args[1])
        chat_id = message.chat.id

        cursor.execute("SELECT completed, triggered FROM reminders WHERE chat_id = ? AND id = ?", (chat_id, reminder_id))
        row = cursor.fetchone()
        if not row:
            await message.answer("Напоминание с таким ID не найдено.")
            return

        now_date = datetime.now().date()
        cursor.execute("UPDATE reminders SET completed = 1, completion_date = ? WHERE chat_id = ? AND id = ?",
                       (now_date, chat_id, reminder_id))
        conn.commit()
        await message.answer(f"Напоминание с ID {reminder_id} отмечено как выполненное ✅.")

    except ValueError:
        await message.answer("ID должен быть числом.")


@router.message(Command("notcomplete"))
async def notcomplete_handler(message: Message):
    """Обрабатывает команду /notcomplete, чтобы отметить напоминание как невыполненное.

        Эта команда позволяет пользователю изменить статус уже выполненного напоминания на невыполненное по отправленному
         ID. Команда проводит работу с базой данных, изменяет completed = 1 на completed = 0.Проверяет что ID
        предоставлен, является числом, существует информация с таким ID, иначе отправляет сообщение об ошибке.

        Аргумент:
            message (Message): Объект сообщения Telegram, содержащий команду и ее аргументы.

        Возвращаемое значение:
            None

        Исключение:
            None

        Примеры:
            >>> '/notcomplete 123'
            >>> notcomplete_handler(message)
            `Напоминание с ID 123 отмечено как невыполненное ❌.`

        """
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Формат команды: /notcomplete ID")
        return
    try:
        reminder_id = int(args[1])
        chat_id = message.chat.id

        cursor.execute("SELECT completed, triggered FROM reminders WHERE chat_id = ? AND id = ?", (chat_id, reminder_id))
        row = cursor.fetchone()
        if not row:
            await message.answer("Напоминание с таким ID не найдено.")
            return

        cursor.execute("UPDATE reminders SET completed = 0, completion_date = NULL WHERE chat_id = ? AND id = ?",
                       (chat_id, reminder_id))
        conn.commit()
        await message.answer(f"Напоминание с ID {reminder_id} отмечено как невыполненное ❌.")

    except ValueError:
        await message.answer("ID должен быть числом.")


@router.message(Command("stats"))
async def stats_handler(message: Message):
    """Обработчик команды /stats для отображения статистики напоминаний за указанный день.

        Команда анализирует напоминания, установленные пользователем, и предоставляет следующую статистику:
        - Общее количество напоминаний за выбранную дату.
        - Процент выполненных напоминаний.
        - Процент невыполненных напоминаний.

        Аргумент:
            message (Message): Объект сообщения Telegram, содержащий команду и аргументы.

        Возвращаемое значение:
            None

        Исключение:
            None

        Пример:
            >>> '/stats 2023-12-01'
            'Cтатистика за 2023-12-01:
            Всего задач: 5
            Выполнено: 80.00%
            Невыполнено: 20.00%'

        """
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Формат команды: /stats YYYY-MM-DD")
        return
    date_str = args[1]
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        await message.answer("Некорректный формат даты. Используйте YYYY-MM-DD.")
        return

    chat_id = message.chat.id

    cursor.execute("""
        SELECT id, text, creation_date, remind_time, is_daily, week_day, completed, completion_date
        FROM reminders
        WHERE chat_id = ?
    """, (chat_id,))
    reminders = cursor.fetchall()

    total_count = 0
    completed_count = 0

    for reminder_id, text, creation_date, remind_time_str, is_daily, week_day, completed, completion_date in reminders:
        creation_date_obj = datetime.strptime(creation_date, "%Y-%m-%d").date()
        remind_dt = datetime.strptime(remind_time_str, "%Y-%m-%d %H:%M:%S")
        remind_date = remind_dt.date()

        occurs_today = False

        if is_daily == 0 and week_day is None:
            # Одноразовое напоминание
            if remind_date == date_obj:
                occurs_today = True
        elif is_daily == 1:
            # Ежедневное напоминание происходит каждый день, начиная с creation_date
            if creation_date_obj <= date_obj:
                occurs_today = True
        elif week_day is not None:
            # Еженедельное напоминание
            if creation_date_obj <= date_obj and date_obj.weekday() == week_day:
                occurs_today = True

        if occurs_today:
            total_count += 1
            if completed == 1:
                if (is_daily == 1 or week_day is not None):
                    if completion_date is not None and datetime.strptime(completion_date, "%Y-%m-%d").date() == date_obj:
                        completed_count += 1
                else:
                    # Для одноразовых, если completed=1, то задача выполнена.
                    completed_count += 1

    if total_count == 0:
        await message.answer(f"На {date_str} нет напоминаний.")
        return

    completed_percentage = (completed_count / total_count) * 100
    uncompleted_count = total_count - completed_count
    uncompleted_percentage = (uncompleted_count / total_count) * 100

    await message.answer(
        f"Статистика за {date_str}:\n"
        f"Всего задач: {total_count}\n"
        f"Выполнено: {completed_percentage:.2f}%\n"
        f"Невыполнено: {uncompleted_percentage:.2f}%"
    )


async def reminder_worker():
    """Асинхронный воркер для обработки и отправки напоминаний.

        Этот воркер работает в бесконечном цикле и проверяет текущую дату и время, а также день недели,
        выбирает из базы данных напоминания, которые нужно отправить пользователям:
        - Напоминания с датой/временем меньше или равным текущему моменту.
        - Исключает напоминания, которые уже помечены как выполненные (`completed=1`) или уже отправленные (`triggered=1`).
        Отправляет напоминания пользователям через Telegram и обновляет их статус:
        - Для ежедневных напоминаний (`is_daily=1`) переносит дату напоминания на следующий день.
        - Для еженедельных напоминаний (`week_day`) переносит дату на следующую неделю.
        - Для одноразовых напоминаний помечает их как `triggered=1`.
        Обновляет статистику задач в базе данных:
        - Увеличивает общее количество задач за текущий день (`total`).
        Цикл повторяется каждые 30 секунд.

        Аргумент:
            None

        Возвращаемое значение:
            None

        Пример:
            async def on_startup(dispatcher: Dispatcher):
                asyncio.create_task(reminder_worker())

        """
    while True:
        now = datetime.now()
        current_week_day = now.weekday()

        cursor.execute("""
            SELECT chat_id, id, text, remind_time, is_daily, week_day, completed, triggered
            FROM reminders
            WHERE (week_day IS NULL OR week_day = ?)
            AND remind_time <= ?
            AND completed = 0
            AND triggered = 0
        """, (current_week_day, now))
        reminders = cursor.fetchall()

        for chat_id, reminder_id, text, remind_time, is_daily, week_day, completed, triggered in reminders:
            try:
                await bot.send_message(chat_id, f"Напоминание: {text}\nОтметь состояние задачи:\n/complete\
{reminder_id}\n/notcomplete {reminder_id}")

                remind_dt = datetime.strptime(remind_time, "%Y-%m-%d %H:%M:%S")

                if is_daily:
                    next_time = remind_dt + timedelta(days=1)
                    cursor.execute(
                        "UPDATE reminders SET remind_time = ?, completed = 0, completion_date = NULL WHERE chat_id = ?"
                        " AND id = ?",
                        (next_time, chat_id, reminder_id))
                elif week_day is not None:
                    next_time = remind_dt + timedelta(weeks=1)
                    cursor.execute(
                        "UPDATE reminders SET remind_time = ?, completed = 0, completion_date = NULL WHERE chat_id = ?"
                        " AND id = ?",
                        (next_time, chat_id, reminder_id))
                else:
                    cursor.execute(
                        "UPDATE reminders SET triggered = 1 WHERE chat_id = ? AND id = ?",
                        (chat_id, reminder_id))

                cursor.execute("""
                    INSERT INTO statistics (chat_id, date, total, completed)
                    VALUES (?, ?, 1, 0)
                    ON CONFLICT(chat_id, date) DO UPDATE SET total = total + 1
                """, (chat_id, now.date()))
                conn.commit()

            except Exception as e:
                print(f"Ошибка при отправке напоминания ({chat_id}, {reminder_id}): {e}")

        await asyncio.sleep(30)


async def on_startup(dispatcher: Dispatcher):
    """Функция инициализации, которая вызывается при запуске бота.

        Эта функция запускает асинхронную фоновую задачу, которая будет выполняться параллельно с другими операциями бота.
        В этой функции создается фоновая задача для функции `reminder_worker()`.

        Аргументы:
            dispatcher (Dispatcher): Объект диспетчера, который управляет обработчиками событий и команд бота.

        Возвращаемое значение:
            None

        Исключение:
            None

        """
    asyncio.create_task(reminder_worker())


async def main():
    """Основная функция для запуска бота.

        Эта функция регистрирует функцию `on_startup` как обработчик событий при старте диспетчера и
        запускает процесс polling для обработки входящих сообщений от Telegram через диспетчер.

        Аргумент:
            None

        Возвращаемое значение:
            None

        Исключение:
            None

        Пример:
            Если эта функция находится в файле `main.py`, бот запускается при вызове:
            if __name__ == "__main__":
                asyncio.run(main())

        """
    dp.startup.register(on_startup)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
