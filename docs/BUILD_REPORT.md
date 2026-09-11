# Отчёт локальной сборки — 2026-09-11

READY_FOR_API_PROBE / GIT_PUSHED / NOT_RELEASED / NOT_ACCEPTED. Live calls: 0.
Sol/Astra: ACCESS_UNKNOWN. Независимый реальный critical review: NOT_RUN.

Среда: Windows, Python 3.14.7, стандартная библиотека, без dependency installation.
Реализацию выполнял текущий Codex root. Делегированные Sol/Astra не вызывались.
Проверки использовали scripted fake provider и mocked HTTPS transport, не реальные модели.
Независимый live critical review не выполнялся; fake verdict не является таким review.

## Проверки

- Из корня исходного проекта: `python -m unittest discover -s standalone/controlled-ai-agent-toolkit/tests -v`.
  58 tests, 57 passed, 1 skipped, 0 failures/errors.
- Focused: `python -B -m unittest discover -s standalone/controlled-ai-agent-toolkit/tests -k crash -v`.
  3 tests, 3 passed, 0 skipped/failures/errors.
- Пропуск: создание symlink запрещено правами Windows. Отдельный junction escape test прошёл.
- Fake demo: PASS, READY_FOR_HUMAN / FAKE_REVIEW_ONLY, 4 fake calls, 2 tool calls, idempotent resume.
- В новой временной standalone-копии: `python -m unittest discover -s tests -v`:
  58 tests, 57 passed, 1 skipped, 0 failures/errors.
- В той же копии `python -m controlled_agent.cli demo`, doctor, task validate и plan: PASS.
- `cmd /d /c agent.cmd demo` в копии с пробелами в пути: PASS.
  PowerShell launcher заблокирован execution policy этой машины (отдельно от unittest skip).
  Политика не изменялась; доступен agent.cmd и прямой Python. POSIX launcher здесь не запускался.
- `python -B scripts/smoke_copy.py`: PASS; копия проверена и удалена, исходная поставка чистая.
- `python -B scripts/verify_export.py`: PASS; полный inventory/hash match, запрещённых артефактов нет.
- Optional wheel дважды собран в test temporary directory с одинаковыми bytes;
  после распаковки demo: PASS. pip install не выполнялся.
- Исходный родительский проект и пользовательские файлы не изменялись.
- Standalone toolkit опубликован как Git-репозиторий; package/release и acceptance не выполнялись.

## Что реализовано

Exact Sol/high writer и Astra/high read-only routes, ограниченные custom function tools,
stdlib Responses transport, offline fake workflow, декларативные subprocess checks,
single-master lease, write-ahead resume, budgets, один repair, immutable packets/manifests,
approval-gated synthetic probes, CLI/launchers, portable example/templates, optional wheel backend,
security/API/runbook docs, CI configuration и export hygiene checks.

При проверках исправлены нестабильная сериализация resume request, порядок событий при загрузке
checkpoint, восстановление manifest после terminal checkpoint, ложное распознавание HTTPS как drive path
и избыточное скрытие безопасного PRESENT/MISSING в doctor.
OpenAI-docs skill использован для проверки официального Responses/function-calling контракта;
это не проверка фактического доступа API project.

## Ограничения и передача владельцу

Только UTF-8 и небольшие scopes; checks — equals/contains/sha256, не произвольные тесты проекта.
Нет OS sandbox, сильной проверки личности владельца, подписи manifests или полной DLP.
Противодействие враждебному локальному OS process и production security не заявляются.
Fake provider обслуживает synthetic greeting example. Live compatibility/quality/cost и обе exact модели
остаются ACCESS_UNKNOWN до отдельно разрешённых probes. Hosted Linux/Python 3.11 CI ещё не запускалась.
Не production-ready.

Полный список созданных файлов и их hashes: EXPORT-MANIFEST.json в корне toolkit.
Сам manifest исключён из собственного inventory; его SHA-256 сообщается verify_export.py.
Отчёт не содержит runtime packets, ключей или данных исходного проекта.

Kamil выбрал лицензию MIT. Остаётся отдельно разрешить либо отложить два synthetic probes
с лимитом один request и 256 output tokens на каждый, включая reasoning.
Ключ не передавать в чат. Денежный бюджет и лимиты API project согласовать отдельно.
