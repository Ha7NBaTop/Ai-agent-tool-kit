# Быстрый старт

1. Скопируйте всю standalone-папку, а не только controlled_agent.
2. Откройте терминал в копии. Нужен Python 3.11+ на PATH; pip и virtualenv не нужны.
3. Выполните `python -B -m controlled_agent.cli doctor` и `python -B -m controlled_agent.cli demo`.
4. Выполните `python -B -m unittest discover -s tests -v`.
5. Проверьте дистрибутив: `python -B scripts/verify_export.py`.

Если execution policy запрещает .ps1, используйте `.\agent.cmd demo` или прямой Python.
Глобальную или процессную execution policy инструмент не изменяет.

Demo ничего не оставляет в поставке. Для своего задания скопируйте templates/task.json в новую
папку рядом с целевыми файлами, задайте owner/objective/allowlists/checks и уникальный task_id.
target_root — относительный путь от task.json, остальные пути — от target_root; используйте /.
Абсолютные пути, .., ссылки, .env, runtime state, секреты и запись в task/controller запрещены.

```powershell
.\agent.ps1 task validate examples/hello-safe-edit
.\agent.ps1 plan examples/hello-safe-edit
.\agent.ps1 run examples/hello-safe-edit --fake
```

Последняя команда изменяет только пример и создаёт runtime state. Для чистого экспорта работайте с копией примера.
Fake provider знает только этот greeting-сценарий; для других задач используйте свои scripted test responses
или отдельно согласованный live run.

Check profile: argv=["@python","@builtin-check"], cwd=".", timeout 1..30,
allowed_exit_codes=[0], assertions с path, operation equals/contains/sha256, expected.
Profile — декларация, не способ передать программу. Master всегда повторяет checks после writer.

Возобновление: та же run-команда с тем же contract, кодом/config и mode. Завершённые записи не повторяются.
После неоднозначного API-вызова run блокируется; сначала разберите checkpoint и расход в API project,
затем вручную подготовьте новое задание, если это безопасно. Не удаляйте журнал для обхода бюджета.
Wall-time включает простой между запусками.

READY_FOR_HUMAN не означает ACCEPTED. Отдельная команда владельца:
`python -B -m controlled_agent.cli decide TASK_FOLDER --owner OWNER --decision ACCEPTED --mode fake`.
Она запросит точную фразу; это локальное подтверждение, а не проверка личности.
Не выполняйте acceptance автоматически.
