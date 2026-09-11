# Подключение OpenAI API

В этой сборке live calls не выполнялись. Обе exact модели имеют статус ACCESS_UNKNOWN.
Один ключ API project может использоваться для обеих моделей при наличии соответствующих permissions.
Проверяйте доступ фактическим отдельным probe, не названием route или fake-ответом.

Ключ задаётся только через переменную окружения OPENAI_API_KEY средствами вашей ОС/секрет-хранилища.
Не вставляйте ключ в чат, task, CLI-аргумент, .env или репозиторий.
CONTROLLED_AGENT_LIVE_ENABLED=1 — отдельный процессный выключатель live.
doctor проверяет только наличие ключа, не показывает значение и не обращается к сети.

После отдельного разрешения владельца и согласования бюджета:

```powershell
.\agent.ps1 models probe --model gpt-5.6-sol --reasoning high --max-output-tokens 256 --approve-live
.\agent.ps1 models probe --model gpt-6-astra --reasoning high --max-output-tokens 256 --approve-live
```

Подкоманда models probe сама означает live probe (отдельный --live для неё не предусмотрен).
Каждая команда требует переключатель окружения, ключ, approve-live и интерактивную фразу
RUN LIVE probe-ИМЯ-МОДЕЛИ. Каждый probe делает максимум один synthetic request без файлов проекта.
Лимит 256 включает reasoning tokens; incomplete считается неуспешной проверкой и не повторяется.
Результаты пишутся в системный временный каталог controlled-agent-probes, не в дистрибутив.
Не публикуйте этот runtime state. Даже успешный probe не доказывает качество writer/reviewer.

Для реального task: новая копия с новым task_id, network_policy="api.openai.com", положительными budgets;
сначала validate/plan, затем `.\agent.ps1 run TASK_FOLDER --live --approve-live`.
Потребуется RUN LIVE TASK_ID. В API передаются declared task и доступные файлы; проверьте их вручную.
Флаги, env, policy, budgets и phrase обязательны вместе. Условия проверяются до сетевой отправки.

Запрос: exact model, reasoning high, custom function tools (writer) / [] (reviewer), store:false,
parallel_tool_calls:false, max_output_tokens, timeout <=60s, Idempotency-Key.
Ответ с другим model ID, refusal/incomplete, invalid usage, transport ambiguity блокирует workflow.
Idempotency-Key не считается гарантией провайдерского дедуплицирования: автоматических retries нет.
Лимиты токенов не являются денежным spending cap; задайте отдельные лимиты API project.

Официальный контракт, использованный при реализации (доступность аккаунта не проверена):
[Function calling](https://developers.openai.com/api/docs/guides/function-calling),
[Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol),
[Astra](https://developers.openai.com/api/docs/models/gpt-6-astra).
