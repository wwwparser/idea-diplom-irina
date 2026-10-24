# Результаты проверок

Полная шестимашинная инфраструктура проверена 24 октября 2026 года. Актуальная матрица — [ACCEPTANCE.md](../docs/ACCEPTANCE.md).

| Доказательство | Содержание |
|---|---|
| deployment.json | Фактические ВМ, ресурсы, один image ID, непрерываемость; прежние ВМ остались STOPPED |
| alb.json, curl-site.* | ACTIVE балансировщик и реальный curl -v |
| full-infrastructure.json | Службы всех ВМ, идентичный SHA-256 сайта, балансировка, остановка и возврат nginx |
| full-monitoring.json | Свежие USE items шести хостов; unsupported/no-data = 0 |
| zabbix-dashboard.json, zabbix-hosts-export.json | Экспорт dashboard и хостов с items, графиками и триггерами |
| full-services.json | Метрики, Elasticsearch green, access/error от двух источников, Kibana data view |
| full-snapshot-schedule.json | ACTIVE ежедневное расписание, retention, шесть дисков и шесть плановых READY snapshots |
| full-backup-restore.json | pg_restore с шестью узлами; SHA-256 файла из восстановленного диска; очистка временных ресурсов |
| public-ui.json | Публичные HTTPS UI, проверенные сертификаты и вход reviewer |
| kibana-saved-objects.json | Две панели access/error и dashboard |
| zabbix-use.png, kibana-logs.png, site.png | Скриншоты реальных веб-интерфейсов |
| validation.txt | Terraform fmt/validate, полный повтор Ansible без изменений, итоговый No changes |

Файлы debug-*, исторические проверки billing/quota, local-checks и записи 18–20 октября описывают промежуточные этапы. Их нельзя использовать как доказательство выполнения полного задания. Секреты и конфигурация с паролями не публикуются.
