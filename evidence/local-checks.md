# Локальные проверки 17 октября 2026

Проверки относятся к локальным конфигурациям. SSH к ВМ, создание платных ресурсов и облачные функциональные проверки не выполнялись.

| Проверка | Среда и результат |
|---|---|
| `terraform init -backend=false -input=false` | Terraform 1.9.8 Windows; установлен подписанный провайдер Yandex 0.233.0, создан lock-файл |
| `terraform fmt -check -recursive` | Успешно, код возврата 0 |
| `terraform validate -no-color` | `Success! The configuration is valid.`, код 0 |
| Ansible syntax check | Ubuntu WSL; ansible-core 2.17.14, collections из requirements.yml; код 0, playbook распознан |
| YAML/Python parsing | 18 файлов YAML загружены через PyYAML; два Python-файла разобраны через AST |
| Inventory | 6 FQDN-хостов; публичный IP отсутствует в inventory; ProxyCommand сформирован; IP вместо FQDN и недопустимый SSH user отклоняются |
| Shell backup | `sh -n ansible/roles/monitoring/files/zabbix-dump` в Ubuntu WSL, код 0 |
| Статическая страница | Временный HTTP-сервер на loopback; HTTP 200; ответ побайтно совпадает с index.html и декодируется UTF-8 |
| Локальные ссылки | Ссылки README/docs на локальные файлы существуют |

Синтаксическая проверка Ansible использовала сгенерированный тестовый inventory в `.tools/inventory-check.yml` и **пример** секретов через `-e secrets_file=<абсолютный путь к ansible/vars/secrets.example.yml>`. Роли не применялись. Библиотеки проверки установлены отдельно от системного Python WSL в `/home/yuri/.cache/irina-check`; никаких сервисов на ВМ это не устанавливало.

Terraform executable скачан с releases.hashicorp.com, SHA-256 архива проверен по опубликованному SHA256SUMS перед запуском. `.tools` игнорируется Git. Это проверка целостности по источнику, не независимая проверка подписи HashiCorp.

Результат не подтверждает доступность конкретного образа в облаке, квоты, применимость групп безопасности в живой сети, успешность установки пакетов и API bootstrap. Эти пункты проверяются по docs/ACCEPTANCE.md.
