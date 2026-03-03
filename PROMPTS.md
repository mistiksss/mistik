# Поэтапные промпты для исправления проблем Telegram-бота

> Каждый промпт — самостоятельная инструкция.  
> Пункты 1–3 из аудита уже исправлены в текущем коде; пункт 4 уже имеет fallback-хендлер.  
> Ниже — промпты для оставшихся реальных проблем (5–12) и дополнительных улучшений.

---

## Промпт 1 — Файл зависимостей (пункт 12 аудита)

```
Создай файл requirements.txt в корне проекта со всеми зависимостями, необходимыми для работы бота.
Проект использует:
- aiogram 3.x (последняя стабильная версия 3.x)
- SQLAlchemy (с async, последняя стабильная 2.x)
- aiosqlite (для sqlite+aiosqlite://)

Укажи конкретные версии с оператором ~= (совместимые релизы), например:
aiogram~=3.15
sqlalchemy~=2.0
aiosqlite~=0.20

Не добавляй лишних зависимостей. Файл должен быть минималистичным.
```

---

## Промпт 2 — Константы текста кнопок (пункт 10 аудита)

```
В проекте Telegram-бота тексты кнопок reply-клавиатуры захардкожены
в двух местах: в keyboards/reply.py (определение кнопок) и в handlers/user.py
и handlers/admin.py (фильтры F.text == "...").
Если текст кнопки изменится в одном месте, но не в другом — хендлер перестанет
срабатывать.

Задача:
1. В файле config.py (после существующих констант SOLUTION_TYPES и SUBJECTS)
   добавь блок констант для текстов кнопок главного меню и админ-меню:

   class ButtonText:
       PROFILE = "Профиль"
       LEADERBOARD = "Лидерборд"
       UPLOAD_SOLUTION = "Загрузить решение"
       BROWSE_SOLUTIONS = "Смотреть решения"
       SUPPORT = "Поддержка"
       ADMIN_PANEL = "Админ-панель"
       BACK_TO_MAIN = "↩️ В главное меню"
       ADD_ADMIN = "➕ Добавить админа"
       BAN_USER = "🚫 Забанить пользователя"
       SKIP = "Пропустить"

2. В keyboards/reply.py замени все захардкоженные строки кнопок
   на константы из ButtonText. Импортируй ButtonText из config.

3. В handlers/user.py замени все фильтры вида F.text == "Профиль"
   на F.text == ButtonText.PROFILE и т.д. Также замени проверку
   message.text.strip().lower() == "пропустить" на
   message.text.strip() == ButtonText.SKIP (кнопка отдаёт точный текст).
   Импортируй ButtonText из config.

4. В handlers/admin.py аналогично замени все F.text == "Админ-панель",
   "➕ Добавить админа", "🚫 Забанить пользователя", "↩️ В главное меню"
   на соответствующие константы ButtonText. Импортируй ButtonText из config.

Убедись, что после замены все фильтры используют строго те же строки,
что и кнопки. Не меняй логику хендлеров, только источник строк.
```

---

## Промпт 3 — Middleware проверки прав админа (пункт 6 аудита)

```
В проекте aiogram 3.x бота проверка прав админа дублируется в каждом хендлере
admin.py через вспомогательные функции _ensure_admin_message и _ensure_admin_callback.
При добавлении нового хендлера легко забыть проверку.

Задача:
1. Создай пакет middlewares/ с файлами __init__.py и admin_check.py.

2. В admin_check.py реализуй middleware AdminCheckMiddleware
   (наследуется от aiogram.BaseMiddleware), который:
   - Импортирует database.requests как db.
   - В методе __call__ получает event (Message или CallbackQuery).
   - Извлекает telegram_id из event.from_user.id.
   - Вызывает await db.is_admin(telegram_id).
   - Если не админ: для Message — await event.answer("Недостаточно прав.");
     для CallbackQuery — await event.answer("Недостаточно прав.", show_alert=True);
     возвращает без вызова handler.
   - Проверяет, не забанен ли пользователь (await db.get_user_by_telegram_id),
     если забанен — аналогично отвечает "Ваш аккаунт заблокирован." и возвращает.
   - Если всё ок — вызывает return await handler(event, data).

3. В handlers/admin.py:
   - Удали функции _ensure_admin_message и _ensure_admin_callback.
   - Подключи middleware к admin_router:
     router.message.middleware(AdminCheckMiddleware())
     router.callback_query.middleware(AdminCheckMiddleware())
   - Удали все вызовы _ensure_admin_message / _ensure_admin_callback
     из хендлеров. Хендлеры должны сразу выполнять бизнес-логику.

4. Убедись, что middleware корректно работает и с Message, и с CallbackQuery.
   Используй isinstance для определения типа event.
```

---

## Промпт 4 — Middleware обработки ошибок БД (пункт 5 аудита)

```
В проекте aiogram 3.x бота при недоступности базы данных или ошибке SQLAlchemy
исключение не перехватывается в хендлерах — пользователь не получает ответа.

Задача:
1. В пакете middlewares/ создай файл db_error.py.

2. Реализуй middleware DatabaseErrorMiddleware (aiogram.BaseMiddleware):
   - В __call__ оборачивает вызов handler(event, data) в try/except.
   - Ловит исключения sqlalchemy.exc.SQLAlchemyError и общие Exception
     (но не CancelledError и KeyboardInterrupt).
   - При ошибке:
     а) Логирует исключение через logging.exception("Database/handler error").
     б) Определяет тип event (Message или CallbackQuery).
     в) Отправляет пользователю: "Произошла временная ошибка. Попробуйте позже."
        Для CallbackQuery используй event.answer(..., show_alert=True).
        Для Message — event.answer(...).
     г) Не поднимает исключение дальше (не роняет процесс).

3. В bot.py подключи DatabaseErrorMiddleware на уровне диспетчера
   (dp.message.outer_middleware / dp.callback_query.outer_middleware),
   чтобы он работал для ВСЕХ роутеров, и пользовательских, и админских.
   Импортируй из middlewares.db_error.

Важно: этот middleware должен быть outer_middleware (внешним), чтобы ловить
ошибки из всех внутренних middleware и хендлеров. Не используй inner middleware.
```

---

## Промпт 5 — Middleware троттлинга (пункт 7 аудита)

```
В проекте aiogram 3.x бота отсутствует защита от спама — пользователь может
отправлять неограниченное количество сообщений и callback.

Задача:
1. В пакете middlewares/ создай файл throttling.py.

2. Реализуй middleware ThrottlingMiddleware(BaseMiddleware):
   - Принимает параметры rate_limit: float = 0.5 (секунды между сообщениями
     от одного пользователя).
   - Хранит dict[int, float] — маппинг user_id -> timestamp последнего запроса.
     Используй простой словарь (для одного процесса этого достаточно).
   - В __call__:
     а) Извлекает user_id из event.from_user.id.
     б) Проверяет, прошло ли rate_limit секунд с момента последнего запроса.
     в) Если нет — игнорирует (return без вызова handler).
        Для CallbackQuery можно вызвать event.answer("Слишком быстро, подождите.")
     г) Если да — обновляет timestamp и вызывает handler.
   - Периодически (например, каждые 100 вызовов) чистит записи старше 60 секунд,
     чтобы словарь не рос бесконечно.

3. В bot.py подключи ThrottlingMiddleware на уровне диспетчера:
   dp.message.middleware(ThrottlingMiddleware(rate_limit=0.5))
   dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=0.3))

Не используй сторонние библиотеки. Достаточно time.monotonic() для timestamps.
```

---

## Промпт 6 — Оптимизация get_user_rank (пункт 8 аудита)

```
В файле database/requests.py функция get_user_rank загружает ВСЕ telegram_id
незабаненных пользователей в память и ищет нужного в цикле Python.
При большом количестве пользователей это неэффективно.

Задача — переписать get_user_rank, чтобы ранг считался на стороне БД:

1. Замени текущую реализацию get_user_rank на запрос, который:
   - Считает количество незабаненных пользователей, у которых
     (approved_solutions_count, rating_points) строго лучше, чем у целевого.
   - Ранг = это количество + 1.

   Реализация:
   а) Сначала получи approved_solutions_count и rating_points целевого пользователя
      по telegram_id (один запрос).
   б) Если пользователь не найден или забанен — верни None.
   в) Выполни COUNT пользователей, где is_banned=False AND
      (approved_solutions_count > target_count
       OR (approved_solutions_count == target_count AND rating_points > target_points)
       OR (approved_solutions_count == target_count AND rating_points == target_points
           AND created_at < target_created_at))
   г) Верни count + 1.

2. Используй два запроса в одной сессии (async with async_session() as session).
   Не используй оконные функции (ROW_NUMBER), так как SQLite может не поддерживать
   их в старых версиях aiosqlite. Вместо этого используй подход с COUNT.

3. Сигнатура функции остаётся: async def get_user_rank(telegram_id: int) -> int | None.
   Поведение: возвращает позицию (1-based) или None, если пользователь не найден
   или забанен.

Не меняй другие функции в файле. Не меняй вызовы get_user_rank в хендлерах.
```

---

## Промпт 7 — Индексы БД для лидерборда и решений (пункт 9 аудита)

```
В файле database/models.py отсутствуют составные индексы для запросов
лидерборда и фильтрации решений, что может замедлить работу при росте таблиц.

Задача:
1. В модели User добавь составной индекс для лидерборда.
   Используй __table_args__:

   __table_args__ = (
       Index(
           "ix_users_leaderboard",
           "is_banned",
           approved_solutions_count.desc(),
           rating_points.desc(),
           "created_at",
       ),
   )

   Примечание: SQLAlchemy может не поддерживать .desc() в Index напрямую.
   В этом случае используй обычный индекс без desc():
   Index("ix_users_leaderboard", "is_banned", "approved_solutions_count",
         "rating_points", "created_at")

2. В модели Solution добавь составной индекс для запроса одобренных решений
   с фильтрами:

   __table_args__ = (
       Index("ix_solutions_approved_browse", "status", "solution_type",
             "subject", "created_at"),
   )

   Уже существующий index=True на status можно оставить (он используется
   для count pending).

3. Импортируй Index из sqlalchemy, если ещё не импортирован.

4. Не меняй существующие поля и связи моделей. Только добавь __table_args__.
```

---

## Промпт 8 — DRY: общая функция отправки контента решения

```
В файле handlers/user.py функции _send_solution_for_review и
_send_solution_to_admins содержат дублированную логику отправки контента
решения (выбор между photo/document/text и формирование caption/text).

Задача:
1. Создай вспомогательную async-функцию _send_solution_content:

   async def _send_solution_content(
       bot: Bot,
       chat_id: int,
       solution: "Solution",
       caption: str,
       reply_markup: InlineKeyboardMarkup | None = None,
   ) -> None:

   Логика:
   - Если solution.content_type == "photo":
     await bot.send_photo(chat_id=chat_id, photo=solution.content_value,
                          caption=_truncate(caption, 1024), reply_markup=reply_markup)
   - Если solution.content_type == "document":
     await bot.send_document(chat_id=chat_id, document=solution.content_value,
                             caption=_truncate(caption, 1024), reply_markup=reply_markup)
   - Иначе (text):
     content_text = f"{caption}\n\n<b>Текст решения:</b>\n{escape(solution.content_value)}"
     await bot.send_message(chat_id=chat_id, text=_truncate(content_text, 4096),
                            reply_markup=reply_markup)

2. Перепиши _send_solution_for_review, чтобы использовала _send_solution_content:
   - Получает solution, формирует caption через _solution_card_text,
     формирует keyboard через solution_review_keyboard.
   - Вызывает await _send_solution_content(bot, chat_id, solution, caption, keyboard).

3. Перепиши _send_solution_to_admins, чтобы в цикле по админам вызывала
   _send_solution_content внутри try/except TelegramBadRequest:
   - Формирует header через _moderation_text, keyboard через moderation_keyboard.
   - Для каждого admin_id: try: await _send_solution_content(bot, admin_id, solution,
     header, keyboard) except TelegramBadRequest: continue.

4. Не меняй сигнатуры _send_solution_for_review и _send_solution_to_admins.
   Не меняй вызовы этих функций в хендлерах.
```

---

## Промпт 9 — Middleware регистрации пользователя (DRY)

```
В handlers/user.py проверка регистрации и бана дублируется в каждом хендлере
через _ensure_registered_message и _ensure_registered_callback.

Задача:
1. В пакете middlewares/ создай файл registration_check.py.

2. Реализуй RegistrationCheckMiddleware(BaseMiddleware):
   - В __call__ получает event (Message или CallbackQuery).
   - Извлекает telegram_id из event.from_user.id.
   - Вызывает user = await db.get_user_by_telegram_id(telegram_id).
   - Если user is None:
     Для Message — await event.answer("Сначала пройдите регистрацию: /start")
     Для CallbackQuery — await event.answer("Сначала пройдите регистрацию: /start",
                                             show_alert=True)
     return (не вызывать handler).
   - Если user.is_banned:
     Аналогично отвечает "Ваш аккаунт заблокирован." и return.
   - Если всё ок — кладёт пользователя в data["db_user"] = user
     и вызывает return await handler(event, data).

3. В handlers/user.py:
   - Подключи middleware к user_router:
     router.message.middleware(RegistrationCheckMiddleware())
     router.callback_query.middleware(RegistrationCheckMiddleware())
   - НО: хендлеры cmd_start, cmd_cancel, registration_nickname,
     registration_nickname_fallback, registration_avatar НЕ ДОЛЖНЫ проходить
     через эту проверку (незарегистрированный пользователь должен иметь к ним доступ).
     Решение: вынеси эти хендлеры в отдельный Router без middleware,
     или в middleware проверяй state — если текущее состояние относится к
     RegistrationState или команда /start или /cancel, пропускай проверку.

     Рекомендуемый подход: в middleware проверяй, является ли event сообщением
     с командой /start или /cancel (через event.text.startswith("/")),
     или проверяй FSM state через data.get("state") на принадлежность к RegistrationState.
     Если да — пропускай и вызывай handler.

4. В хендлерах, где раньше вызывался _ensure_registered_message/callback,
   вместо этого получай пользователя из параметра: db_user = kwargs.get("db_user")
   или через аннотацию в хендлере.
   Удали вызовы _ensure_registered_message/callback и сами эти функции.

ВАЖНО: это рефакторинг средней сложности. Если слишком сложно с исключениями
для /start и registration state, допустимо оставить _ensure_registered_* как есть,
но вынести их в общий модуль utils.py и импортировать оттуда.
```

---

## Промпт 10 — Замена rated_solutions_json на отдельную таблицу (рекомендательно)

```
В модели User поле rated_solutions_json хранит JSON-строку {solution_id: stars}.
При большом количестве оценок строка растёт. Для масштабируемости лучше
вынести рейтинги в отдельную таблицу.

Задача:
1. В database/models.py добавь новую модель Rating:

   class Rating(Base):
       __tablename__ = "ratings"

       id: Mapped[int] = mapped_column(primary_key=True)
       user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
       solution_id: Mapped[int] = mapped_column(ForeignKey("solutions.id", ondelete="CASCADE"))
       stars: Mapped[int] = mapped_column(Integer)
       created_at: Mapped[datetime] = mapped_column(
           DateTime(timezone=True), server_default=func.now()
       )

       __table_args__ = (
           UniqueConstraint("user_id", "solution_id", name="uq_user_solution_rating"),
       )

   Импортируй UniqueConstraint из sqlalchemy.

2. Поле rated_solutions_json в модели User — НЕ УДАЛЯЙ сразу (для обратной
   совместимости), но помечь как deprecated (в комментарии).

3. В database/requests.py перепиши функцию rate_solution:
   - Вместо чтения/записи rated_solutions_json используй таблицу Rating.
   - Проверяй существование оценки: select(Rating).where(
       Rating.user_id == rater.id, Rating.solution_id == solution_id).
   - Если запись есть — "Вы уже оценили это решение."
   - Если нет — создай Rating(user_id=rater.id, solution_id=solution_id, stars=stars)
     и обнови solution.ratings_sum, solution.ratings_count, solution.author.rating_points.
   - Удали вспомогательную функцию _ratings_map (она больше не нужна).
   - Импортируй Rating из database.models.

4. Не забудь, что при init_db() таблица ratings будет создана автоматически
   через Base.metadata.create_all (уже вызывается в bot.py -> on_startup).

5. Не меняй сигнатуру rate_solution и не меняй хендлеры.
```

---

## Промпт 11 — FSM-хранилище Redis (пункт 11 аудита, рекомендательно)

```
Сейчас бот использует MemoryStorage по умолчанию для FSM.
При перезапуске процесса все состояния пользователей теряются.

Задача (выполнять только если планируется продакшн-деплой):
1. Добавь зависимость: aioredis (или redis[hiredis]) в requirements.txt.

2. В config.py добавь поле redis_url в Settings:
   redis_url: str
   И в инициализации: redis_url=os.getenv("REDIS_URL", "")

3. В bot.py:
   - Если settings.redis_url не пустой, создай RedisStorage:
     from aiogram.fsm.storage.redis import RedisStorage
     storage = RedisStorage.from_url(settings.redis_url)
   - Иначе оставь storage = MemoryStorage() (для локальной разработки).
   - Передай storage в Dispatcher: dp = Dispatcher(storage=storage)

4. Не меняй states.py и логику хендлеров — FSM API одинаков для всех хранилищ.

Примечание: aiogram 3.x использует пакет redis (не aioredis отдельно).
Добавь в requirements.txt: redis~=5.0
Импорт: from aiogram.fsm.storage.redis import RedisStorage
```

---

## Промпт 12 — Защита initial_admin от удаления (дополнительно из аудита)

```
В admin.py есть защита от бана INITIAL_ADMIN_ID, но нет защиты от удаления
из таблицы admins.

Задача:
1. В database/requests.py добавь функцию remove_admin:

   async def remove_admin(telegram_id: int) -> bool:
       if telegram_id == settings.initial_admin_id:
           return False
       async with async_session() as session:
           stmt = select(Admin).where(Admin.telegram_id == telegram_id)
           result = await session.execute(stmt)
           admin = result.scalar_one_or_none()
           if admin is None:
               return False
           await session.delete(admin)
           await session.commit()
           return True

2. Если в будущем появится хендлер удаления админа — использовать эту функцию
   вместо прямого удаления.

3. В ensure_initial_admin функция add_admin уже идемпотентна (проверяет
   существование), так что при каждом запуске initial admin гарантированно
   создаётся, если его нет.

Это небольшое изменение, но оно закрывает потенциальную дыру.
```

---

## Рекомендуемый порядок применения

1. **Промпт 1** — requirements.txt (базовая гигиена, нужно для CI/CD)
2. **Промпт 2** — Константы кнопок (уменьшает риск рассинхронизации)
3. **Промпт 7** — Индексы БД (быстро, не ломает логику)
4. **Промпт 6** — Оптимизация get_user_rank (производительность)
5. **Промпт 8** — DRY: общая функция отправки (чистота кода)
6. **Промпт 3** — Middleware админа (архитектура)
7. **Промпт 4** — Middleware ошибок БД (надёжность)
8. **Промпт 5** — Throttling (безопасность)
9. **Промпт 9** — Middleware регистрации (DRY, сложный рефакторинг)
10. **Промпт 10** — Таблица Rating (масштабируемость)
11. **Промпт 12** — Защита initial admin (безопасность)
12. **Промпт 11** — Redis FSM (только для продакшна)
