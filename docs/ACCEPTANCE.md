# Матрица приёмки

Полный стенд проверен 24 октября 2026 года. Доказательства относятся к шести ВМ `irina-*` текущего диплома. Исторические `debug-*` и файлы квот предыдущих дат не используются как доказательство полной реализации.

| Требование задания | Реализация и доказательство |
|---|---|
| Terraform и Ansible | Код в `terraform/`, `ansible/`; validate, повторный playbook и финальный plan — [validation.txt](../evidence/validation.txt) |
| Два одинаковых web в разных зонах | web-a в e, web-b в d; один образ Ubuntu и совпавший SHA-256 сайта — [full-infrastructure.json](../evidence/full-infrastructure.json) |
| Приватные web и Elasticsearch | Публичные IP отсутствуют, SSH идёт через бастион, inventory содержит FQDN — тот же протокол и генератор `scripts/render_inventory.py` |
| Target Group, Backend Group, HTTP router, ALB | Terraform `alb.tf`, health check `/`:80, listener 80; реальный ACTIVE ALB — [alb.json](../evidence/alb.json) |
| Проверка curl -v ALB | [stdout](../evidence/curl-site.stdout.txt), [stderr с HTTP-заголовками](../evidence/curl-site.stderr.txt) |
| Отказ одного nginx | 20/20 HTTP 200 от web-b при остановленном web-a; затем восстановлены оба backend — [full-infrastructure.json](../evidence/full-infrastructure.json) |
| Отдельная ВМ Zabbix, агенты всех ВМ | Шесть узлов, свежие метрики — [full-services.json](../evidence/full-services.json), [full-monitoring.json](../evidence/full-monitoring.json) |
| USE dashboard и thresholds | 176 custom items, шесть страниц, 80 графиков, постоянные пороговые линии и триггеры — [dashboard export](../evidence/zabbix-dashboard.json), [host export](../evidence/zabbix-hosts-export.json), [скриншот](../evidence/zabbix-use.png) |
| Отдельные Elasticsearch и Kibana | Нативные пакеты/systemd, Elasticsearch green — [full-services.json](../evidence/full-services.json) |
| access.log/error.log обоих nginx | Реальные Filebeat события обоих типов и обоих host.name — тот же протокол, [Kibana objects](../evidence/kibana-saved-objects.json), [скриншот](../evidence/kibana-logs.png) |
| VPC, публичные/приватные подсети, NAT | Одна используемая VPC, четыре отдельные подсети диплома, private route через NAT — `network.tf`, описание [DIPLOMA.md](DIPLOMA.md) |
| Security Groups и бастион только SSH | Пять SG, /32 для административных портов, HTTPS для reviewer; UFW сужает общую UI SG; активные агенты без входящего 10050 |
| Ежедневные снимки всех дисков, семь дней | ACTIVE schedule, шесть подключённых дисков, retention 604800 секунд и первые шесть плановых READY snapshots — [full-snapshot-schedule.json](../evidence/full-snapshot-schedule.json) |
| Восстановление данных | PostgreSQL `pg_restore` в тестовую БД, проверка шести узлов; файл сайта из копии диска — [full-backup-restore.json](../evidence/full-backup-restore.json) |
| Непрерываемые ВМ перед сдачей | Проверено через Compute API: `preemptible=false` для всех шести — [full-infrastructure.json](../evidence/full-infrastructure.json) |
| Доступ к сайту, Zabbix и Kibana | Публичные ссылки и доверенные сертификаты — [ACCESS.md](ACCESS.md); HTTPS и вход reviewer проверены — [public-ui.json](../evidence/public-ui.json) |
| Оформление и исходники | Отдельный репозиторий, README, отчёт, runbook, эта матрица, экспорты и скриншоты |

## Ограничения

Проверена остановка одного процесса nginx, а не потеря целой зоны. Zabbix, Elasticsearch и Kibana не кластеризованы — это соответствует минимальной схеме задания. Снимки работающих ВМ crash-consistent; логический дамп обеспечивает отдельный путь восстановления PostgreSQL. Самоподписанные TLS-сертификаты требуют явного доверия, поскольку домен для выпуска публичного сертификата не задан.

Секреты отсутствуют в публикуемых доказательствах. Пароль reviewer передаётся отдельно. Варианты Managed PostgreSQL, autoscaling и HTTPS сайта с доменным сертификатом относятся к дополнительным пунктам задания и в обязательный объём не включены.
