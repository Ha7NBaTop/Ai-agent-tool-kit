# Переносимый controlled AI-agent toolkit

Самостоятельная папка: скопируйте её целиком, установите Python 3.11+ отдельно и запустите:

```powershell
.\agent.ps1 demo
.\agent.ps1 doctor
.\agent.ps1 task validate examples/hello-safe-edit
.\agent.ps1 plan examples/hello-safe-edit
```

Если PowerShell блокирует скрипты, используйте `python -B -m controlled_agent.cli demo`;
launcher не меняет execution policy. Для Linux/macOS: `sh agent.sh demo`.
Также доступен `.\agent.cmd demo` для Windows с запрещёнными PowerShell-скриптами.

Demo работает без ключа и сети, во временной папке. Fake-writer действительно вызывает локальные
функции записи, затем master запускает проверки, замораживает packet и вызывает fake-reviewer.
Повторный запуск не повторяет изменения. Это FAKE_REVIEW_ONLY, не реальный Sol/Astra review.

Для сохранения результата примера: `.\agent.ps1 run examples/hello-safe-edit --fake`.
Это создаст output и .controlled-agent в папке примера: не включайте их в публикацию.
Предпочтительно сначала скопировать examples/hello-safe-edit в отдельную рабочую папку.

Реальный API-клиент реализован, но live calls и probes при сборке не выполнялись.
Доступ к gpt-5.6-sol/high и gpt-6-astra/high: ACCESS_UNKNOWN.
Покупка ключа сама по себе не доказывает доступность конкретной модели в API project.

Документы: [быстрый старт](docs/QUICKSTART_RU.md), [API](docs/API_SETUP_RU.md),
[архитектура](docs/ARCHITECTURE.md), [модель угроз](docs/THREAT_MODEL.md),
[публикация](docs/RELEASE_CHECKLIST_RU.md), [отчёт](docs/BUILD_REPORT.md).

Лицензию выбирает Kamil; до решения открытая лицензия не предоставлена.
Standalone toolkit размещён в GitHub; package/release и human acceptance не выполнялись.
