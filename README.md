# PTO-bot (Core)

Ядро Telegram-бота PTO-bot: RBAC, справочники, привязка групп к объектам, rate limiting, импорт Excel, SMTP, аудит, расширяемость модульной регистрацией.

## Запуск в Docker

1) Скопировать пример окружения:
cp .env.example .env
2) Поднять инфраструктуру:
docker compose up -d --build
3) Выполнить миграции:
docker compose exec bot alembic upgrade head
Команды ядра
Пользователь:

/start, /sart

/help

/object_search <строка> (только в личке для разрешённых пользователей)

Админ:

/object_list

/object_add key=value ...

/object_del <object_id>

/group_add <object_id> (в группе)

/group_del <object_id> (в группе)

/group_list (в группе или в личке)

/user_add <telegram_user_id> [full name]

/user_del <telegram_user_id>

/user_list

/time <minutes>

/recipient_email <email>

/object_import (документ .xlsx в сообщении или без документа — импорт из bytes запрещён; требуется документ)

Супер-админ:

/admin_add <telegram_user_id>

/admin_del <telegram_user_id>

/admin_list

Git
Инициализация:
git init
git add .
git commit -m "Init core"
