# Перед отдельной Git-публикацией

- Kamil выбирает лицензию и утверждает LICENSE/атрибуцию. Сейчас решение не принято.
- Прочитать SECURITY.md и ограничения; не заявлять production-ready.
- Повторить tests, demo и export verification в чистой временной копии.
- Проверить EXPORT-MANIFEST.json: это полный список candidate files, не runtime.
- Не копировать .env, ключи, .controlled-agent, logs, SQLite, raw, caches или данные исходного проекта.
- Если менялись файлы, пересобрать manifest командой python -B scripts/build_export.py.
- Только после отдельного разрешения создать Git repository/remote, commit, push.
- В POSIX сделать agent.sh executable для прямого ./agent.sh; sh agent.sh работает без executable bit.
- GitHub Actions требует сети у GitHub runners; локальная сборка Actions не запускала.
- Live probes — отдельное разрешение и бюджет; даже успех не означает human acceptance.
- Перед реальными задачами отдельно проверить sandbox/permissions, стоимость и provider contract.
