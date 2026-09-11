# Перед следующей Git-публикацией или release

- Убедиться, что LICENSE содержит утверждённую Kamil лицензию MIT и корректную атрибуцию.
- Прочитать SECURITY.md и ограничения; не заявлять production-ready.
- Повторить tests, demo и export verification в чистой временной копии.
- Проверить EXPORT-MANIFEST.json: это полный список candidate files, не runtime.
- Не копировать .env, ключи, .controlled-agent, logs, SQLite, raw, caches или данные исходного проекта.
- Если менялись файлы, пересобрать manifest командой python -B scripts/build_export.py.
- Выполнять следующие commit/push/release только после явного разрешения владельца.
- В POSIX сделать agent.sh executable для прямого ./agent.sh; sh agent.sh работает без executable bit.
- GitHub Actions требует сети у GitHub runners; локальная сборка Actions не запускала.
- Live probes — отдельное разрешение и бюджет; даже успех не означает human acceptance.
- Перед реальными задачами отдельно проверить sandbox/permissions, стоимость и provider contract.
