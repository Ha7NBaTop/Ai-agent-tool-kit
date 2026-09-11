# Готовый prompt: AI Tool Kit Touch

Скопируйте блок ниже в новый Codex task, открытый в корне репозитория
`Ha7NBaTop/Ai-agent-tool-kit` на ветке `ai-tool-kit-touch`.

---

```text
Ты — единственный active master разработки локального визуального приложения AI Tool Kit Touch.

Не ограничивайся планом: изучи существующий controlled-agent engine, реализуй интерфейс,
offline tests и документацию. Не выполняй live API calls, human acceptance, merge в main,
release или публикацию без отдельного прямого разрешения владельца.

## Исходная точка

- Репозиторий: Ha7NBaTop/Ai-agent-tool-kit
- Рабочая ветка: ai-tool-kit-touch
- Сначала прочитай применимый AGENTS.md, README_RU.md, SECURITY.md,
  docs/ARCHITECTURE.md и существующий код controlled_agent/.
- Существующий security core не переписывай без необходимости. UI должен вызывать его
  публичные сервисы либо тонкий application service, сохраняя path guards, budgets,
  no-fallback routing, single-writer invariant, immutable packets и human gate.
- Не добавляй сведения или данные из других проектов.
- Все edits выполняй через apply_patch.

## Цель продукта

Сделай понятное локальное приложение, похожее по удобству на современный AI-chat,
но предназначенное для управляемой команды AI-агентов.

Пользователь должен без чтения JSON уметь:

1. создать workspace;
2. выбрать одну локальную папку с файлами как контекст;
3. увидеть дерево включённых и исключённых файлов до отправки модели;
4. настроить master-агента и агентов других ролей;
5. визуально увидеть последовательность и связи агентов;
6. общаться с master в основном чате;
7. открыть отдельный чат любого ролевого агента и увидеть его сообщения;
8. наблюдать delegation, tool calls, проверки, расходы и состояние run;
9. безопасно вставить API key в маскированное поле;
10. запустить offline demo одним кликом;
11. отдельно подтвердить live probe или live run;
12. принять или отклонить готовый результат только через отдельный human gate.

Название интерфейса: AI Tool Kit Touch. Не копируй логотипы, графику или тексты ChatGPT.

## Обязательный UX

### 1. Экран первого запуска

Покажи короткий wizard из четырёх шагов:

- `Папка контекста`;
- `Команда агентов`;
- `Провайдер и ключ`;
- `Offline demo / Начать работу`.

Каждый шаг должен иметь понятное описание, безопасные defaults, Back/Next и индикатор
прогресса. Должна быть кнопка `Пропустить API и открыть offline demo`.

### 2. Основной layout

Три изменяемые области:

- слева: workspaces, `Master chat`, список агентов, кнопка добавления роли;
- по центру: выбранный чат, сообщения, composer, streaming/status-индикаторы;
- справа: Context, Architecture, Run, Permissions и Budget inspector.

На узком экране боковые панели превращаются в drawers. Состояние не должно теряться
при переключении между master и agent chats.

### 3. Master chat

- Это основной вход пользователя.
- Master показывает короткий план до запуска.
- Delegation отображается отдельными cards: агент, задача, статус, время, токены.
- Tool call отображается как сворачиваемая запись с именем операции, безопасными arguments,
  результатом и before/after hash; file contents и secrets не показывать автоматически.
- Опасные или live-действия требуют отдельной карточки подтверждения.
- `COMPLETE` агента не отображать как `ACCEPTED`.

### 4. Чаты ролевых агентов

- Каждый агент имеет собственную историю и цвет/иконку роли.
- При переходе в чат видно: роль, модель, reasoning effort, permissions, назначенная задача,
  входной packet и связь с master-run.
- Сообщения master → agent и agent → master видимы с provenance и timestamp.
- Пользователь может задать агенту вопрос напрямую, но direct chat является advisory:
  он не получает дополнительных файловых прав и не обходит master workflow.
- Кнопка `Вернуться к master` всегда доступна.

### 5. Context picker

- Кнопка `Выбрать папку` открывает нативный folder picker, когда он доступен.
- Добавь ручной ввод пути как fallback с немедленной валидацией.
- После выбора покажи дерево файлов с checkbox, размером, типом и причиной исключения.
- По умолчанию исключай `.git`, `.env*`, keys/certificates, runtime state, caches,
  virtual environments, build output, binary/oversized files и известные secret files.
- Поддержи include/exclude patterns, preview итогового списка, число файлов и общий размер.
- Ничего не отправляй провайдеру до явного запуска.
- Не копируй папку пользователя в репозиторий приложения.
- Все пути canonicalize; блокируй traversal, symlink/junction/reparse escape и hidden runtime.

### 6. Визуальный Architecture Builder

Покажи небольшую наглядную схему nodes + arrows. Обязательные типы nodes:

- deterministic master;
- advisory agent (read-only);
- writer agent;
- deterministic checks;
- reviewer agent (read-only);
- human decision.

Node card показывает имя, роль, model ID, reasoning, permissions и статус. По клику открывается
редактор справа. Реализуй добавление, переименование, удаление и изменение порядка агентов,
но не позволяй удалить master/check/human gate из исполняемой архитектуры.

Правила validator:

- master ровно один;
- mutation lane одновременно содержит не более одного writer;
- reviewer не имеет mutation tools;
- checks находятся после writer и до review;
- human decision последний;
- циклы, недостижимые nodes и неизвестные permissions запрещены;
- exact model IDs сохраняются явно;
- silent fallback запрещён;
- все нарушения показываются рядом с node человеческим языком.

MVP может исполнять только безопасный последовательный граф. Дополнительные advisory agents
выполняются последовательно. Не имитируй параллельность, которой в engine нет.

### 7. Agent editor

Для каждой роли:

- display name;
- role type;
- system instructions;
- exact provider/model ID;
- reasoning effort;
- read/write permissions;
- allowed tools;
- context subset;
- input/output/model-call/tool-call budget;
- fallback policy, по умолчанию и для OpenAI routes только `none`;
- кнопка `Проверить конфигурацию` без сети.

Предоставь безопасные templates: Researcher (read-only), Planner (read-only), Writer,
Critical Reviewer (read-only). Template — это editable starting point, не доказательство
вызова соответствующей модели.

### 8. API key setup

Сделай простой modal `Подключить OpenAI`:

- password input с show/hide;
- Paste button через Clipboard API только после user gesture;
- кнопка `Использовать в этой сессии`;
- индикаторы `Ключ введён`, `Live disabled`, `Access unknown`;
- ключ отправляется только локальному backend по loopback и хранится только в памяти процесса;
- не сохраняй key в SQLite, JSON, `.env`, browser storage, history, analytics, logs или errors;
- frontend после передачи очищает input и не держит key в application state;
- никогда не показывай prefix или последние символы ключа;
- поддержи OPENAI_API_KEY как альтернативный environment source;
- persistent setup описывай через OS environment/secret manager, но не реализуй plaintext save;
- кнопка `Забыть ключ` очищает процессную память;
- `Проверить доступ` запускает только отдельный synthetic capped probe после точного confirmation;
- probe показывает requested/resolved model, response ID, usage и ACCESS_OK/BLOCKED;
- API key не даёт автоматического разрешения на live run.

Frontend не вызывает OpenAI напрямую. Все API calls идут через локальный backend.

### 9. Run screen

Покажи timeline:

`Draft → Planned → Agent running → Checking → Packet frozen → Reviewing → Ready for human`.

Для каждого этапа показывай timestamps, agent, model requested/resolved, usage, checks,
packet/manifest ref и ошибку без secret payload. Добавь Stop, Resume и Export report.
Stop должен быть cooperative и не повреждать checkpoint. Resume не повторяет завершённые mutations.

Перед live run покажи review screen:

- какая папка и какие файлы будут доступны;
- какие агенты и exact models будут вызваны;
- permissions и tools каждого агента;
- token/model-call budget;
- что будет отправлено провайдеру;
- отдельный checkbox, approve button и точная confirmation phrase.

### 10. Visual design

- Светлая и тёмная темы, default следует системной.
- Спокойная нейтральная палитра; один accent, отдельные warning/danger colors.
- Хорошая типографика, достаточный contrast, keyboard navigation и visible focus.
- Messages читаемы при длинном тексте; code blocks имеют Copy.
- Empty, loading, error, blocked и offline states должны быть спроектированы явно.
- Никаких внешних CDN, remote fonts, telemetry и marketing widgets.
- Иконки — локальные SVG или CSS, доступные по aria-label.
- Интерфейс русский; подготовь структуру строк для будущего английского перевода.

## Техническая архитектура MVP

Предпочтительный стек без build/install шага:

- Python 3.11+ standard library backend;
- локальный `ThreadingHTTPServer` или эквивалентный stdlib HTTP layer;
- SQLite из standard library для workspaces/chats/configurations/run projections;
- vanilla HTML/CSS/JavaScript без npm и внешних runtime dependencies;
- Server-Sent Events либо bounded polling для событий run;
- существующий `controlled_agent` как единственный execution/security engine.

Если реальная потребность заставляет выбрать другой стек, сначала документируй конкретную причину,
стоимость переносимости и threat-model change. Не устанавливай dependencies без отдельного разрешения.

Предлагаемая структура:

ui_agent/
  __init__.py
  server.py
  api.py
  app_service.py
  workspace_store.py
  context_index.py
  architecture.py
  session_secrets.py
  event_stream.py
  folder_picker.py
web/
  index.html
  app.js
  styles.css
  assets/
ui.cmd
ui.ps1
ui.sh
docs/UI_QUICKSTART_RU.md
docs/UI_ARCHITECTURE.md
docs/UI_SECURITY.md
tests/test_ui_*.py

Дополнительные файлы разрешены при необходимости. Не создавай generated bundles, vendored packages
или minified artifacts без исходников.

## Local server security

- Bind только `127.0.0.1`, не `0.0.0.0`.
- По умолчанию выбирай свободный random port.
- Сгенерируй случайный session token; передай его браузеру через URL fragment,
  сразу удали fragment через `history.replaceState`, дальше отправляй token в header.
- Все `/api/*` endpoints требуют token; state-changing endpoints также проверяют exact Origin/Host.
- Только JSON с строгими schemas, bounded request bodies и method allowlist.
- CSP `default-src 'self'`; запрети framing и MIME sniffing; никакого inline remote code.
- Рендери model/user text через `textContent`, не `innerHTML`; Markdown renderer допустим только
  при строгом escaping и regression tests против XSS.
- Не передавай process environment frontend или модели.
- Не логируй request bodies, key, prompts или file contents по умолчанию.
- UI не расширяет permissions task contract.
- Browser UI — удобный control plane, а не authentication boundary против hostile local OS user.

## Conversation и OpenAI integration

Используй актуальный OpenAI Responses API. Официальный API поддерживает custom function calls,
conversation/previous response state и structured JSON output. Для приватного local-first режима
по умолчанию используй `store:false` и локально сохраняй только необходимые input/output items;
reasoning content считать opaque и не показывать пользователю как chain-of-thought.

Источники для обязательной сверки перед реализацией:

- https://developers.openai.com/api/reference/cli/resources/responses/methods/create
- https://developers.openai.com/api/docs/guides/function-calling

Не придумывай endpoint, model access или provider capabilities. До probe показывай ACCESS_UNKNOWN.
Не выполняй live probe в этой build-задаче.

## Data model

Минимальные сущности:

- Workspace;
- ContextRoot и ContextSelection;
- AgentProfile;
- ArchitectureVersion;
- ChatThread;
- Message с author/provenance/run_id;
- RunProjection;
- ApprovalRequest;
- ProviderSessionStatus без key value;
- immutable refs на engine packets/manifests.

SQLite migrations versioned и deterministic. API key и raw secrets в БД запрещены.
Удаление workspace/chats требует отдельного confirmation; сначала реализуй recoverable archive,
а permanent delete можешь оставить deferred.

## HTTP API MVP

Определи строгие endpoints минимум для:

- health/version;
- list/create/open workspace;
- choose/validate/index context folder;
- get/update context selection;
- list/create/update/archive agent profiles;
- get/update/validate architecture;
- list/open/create chat threads;
- append user message;
- start/stop/resume fake run;
- read/stream run events;
- session-only provider key set/forget/status;
- prepare live preview;
- live probe/run approval, реализованные, но не вызываемые в build;
- owner decision через отдельный endpoint и exact phrase.

Каждый endpoint имеет documented request/response schema, размерный лимит и negative tests.

## Offline demo

Команда:

`python -B -m ui_agent.server --demo`

и launchers:

- Windows: `ui.cmd`;
- PowerShell: `ui.ps1`;
- Linux/macOS: `sh ui.sh`.

Demo автоматически создаёт временный synthetic workspace, открывает UI и показывает:

- master chat;
- Planner → Writer → Check → Reviewer → Human flow;
- переход в chats Planner/Writer/Reviewer;
- context tree с synthetic файлами;
- tool-call timeline;
- fake usage;
- READY_FOR_HUMAN / FAKE_REVIEW_ONLY.

Demo не требует key/сети, не меняет tracked files и очищает temporary workspace после остановки.
Добавь `--no-browser` для CI и печатай локальный URL без secrets.

## Обязательные тесты

Используй unittest и temporary directories. Сохрани все существующие тесты зелёными и добавь минимум:

1. server слушает только loopback;
2. random session token обязателен для API;
3. wrong/missing token блокируется;
4. Origin/Host validation;
5. request body limit;
6. folder picker fallback;
7. context traversal/symlink/junction escape;
8. default secret/runtime exclusions;
9. deterministic context index;
10. oversized/binary file exclusion;
11. API key остаётся только в памяти;
12. key отсутствует в SQLite/logs/responses/browser bootstrap;
13. forget key;
14. live action без всех approvals блокируется до network;
15. fake mode не требует key;
16. architecture rejects two concurrent writers;
17. reviewer mutation rejection;
18. mandatory checks/human nodes;
19. cycle/unreachable-node rejection;
20. direct agent chat не расширяет permissions;
21. master и role chat isolation;
22. provenance and timestamps;
23. message escaping/XSS fixtures;
24. persisted chats после restart;
25. cooperative stop/resume;
26. no duplicate mutations after resume;
27. immutable packet displayed by ref;
28. fake UI end-to-end lifecycle;
29. `--no-browser` clean startup/shutdown;
30. Windows path with spaces;
31. portable temporary copy;
32. export manifest excludes UI runtime/key/context data;
33. existing CLI/demo/tests remain green;
34. golden screenshots or DOM snapshots for onboarding, master, agent chat, architecture and run states.

Не используй real API key и не выполняй live calls. Network mocking должен fail closed.

Запусти:

`python -B -m unittest discover -s tests -v`

Затем скопируй tracked candidate files во временную папку и повтори tests плюс:

`python -B -m ui_agent.server --demo --no-browser --self-test`

Проверь Windows launcher через `ui.cmd --demo --no-browser --self-test`.
POSIX launcher проверь, если среда это позволяет; иначе явно укажи NOT_RUN.

## Visual QA

Если среда имеет browser/screenshot tools, открой локальный demo и визуально проверь минимум:

- onboarding desktop;
- master chat с delegation cards;
- agent chat;
- architecture builder;
- context picker/tree;
- live confirmation modal;
- narrow viewport;
- dark theme;
- keyboard focus.

Сохрани только обезличенные synthetic screenshots в docs/assets/ui/ и включи их в README.
Не добавляй screenshot, если он содержит host path, key, private данные или browser chrome.
Если browser tool отсутствует, выполни DOM/state tests и честно отметь VISUAL_QA_NOT_RUN.

## Acceptance criteria

- Новый пользователь запускает offline demo максимум одной командой.
- Он выбирает папку и видит точный context scope до AI call.
- Он создаёт роли без ручного редактирования JSON.
- Он понимает текущего исполнителя и следующий workflow step.
- Master и каждый agent имеют отдельные доступные chats.
- Один writer и read-only reviewers enforced кодом, не только prompt.
- API key вводится просто, но не сохраняется и не раскрывается.
- Все live operations gated и ACCESS_UNKNOWN до probe.
- UI не предоставляет shell, unrestricted filesystem, Git push, deploy или acceptance модели.
- Offline demo, tests, resume и export работают из временной копии.
- Старый CLI продолжает работать.
- Документация описывает реальные ограничения и не называет продукт production-ready.

## Порядок выполнения

1. Read-only audit текущего engine и тестов.
2. Короткая implementation/traceability matrix.
3. UI threat model и ADR о local server/session key/context storage.
4. Application service между UI и engine.
5. Context picker/indexer.
6. Agent profiles и architecture validator.
7. Chats/provenance/local persistence.
8. Static UI и responsive visual states.
9. Session-only API key UX и live gates без live calls.
10. Fake end-to-end demo.
11. Security, endpoint и UI tests.
12. Temporary-copy smoke и visual QA.
13. Обновление README/docs/export manifest.
14. Финальный read-only review diff.
15. Остановиться до merge, live probe, release и human acceptance.

## Финальный ответ

Начни с фактического статуса. Укажи:

- что реализовано;
- изменённые файлы;
- UI launch command;
- tests и точные результаты;
- temporary-copy smoke;
- visual QA и screenshots либо NOT_RUN;
- security review findings;
- export manifest SHA-256;
- что live calls, merge/release и acceptance не выполнялись;
- известные ограничения;
- одно решение, требуемое от Kamil перед следующим шагом.

Не называй приложение production-ready.
```

---

Этот prompt намеренно задаёт local-first MVP без внешнего frontend toolchain. Он сохраняет
защитные ограничения текущего engine и добавляет визуальную оболочку, а не переносит API key
или unrestricted filesystem access в браузер.
