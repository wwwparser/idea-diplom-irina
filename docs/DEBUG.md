# Отладочный стенд на двух ВМ

Исторический профиль: 24 октября заменён полной шестимашинной схемой. Его семь собственных ресурсов удалены, проверенный дамп сохранён локально. Текущие URL и доказательства находятся в README и ACCEPTANCE.md. Ниже описан промежуточный этап.

После уточнения пользователя от 24 октября подготовлен отдельный сокращённый профиль. Он позволяет отлаживать сервисы в текущих квотах, не дожидаясь разрешения на шесть ВМ. Полная конфигурация диплома сохранена в `terraform/`; отладочная — в `terraform-debug/`, со своим state.

## Созданная инфраструктура

| ВМ | Зона | CPU | RAM, гигабайт ≈ | SSD, гигабайт ≈ | Роли |
|---|---|---|---:|---:|---|
| irina-debug-control | d | 2 vCPU, доля 20% | 8,59 | 42,95 | Бастион, nginx, Zabbix/PostgreSQL, Elasticsearch, Kibana, агент, Filebeat |
| irina-debug-web | e | 2 vCPU, доля 20% | 2,15 | 10,74 | Второй nginx, агент и Filebeat |

Итого 4 vCPU; в конфигурации каждой ВМ установлен `core_fraction=20`. Нужны ровно существующие лимиты по 2 vCPU в каждой зоне. Первоначальная попытка дать control 16 единиц памяти отклонена API: на standard-v3 при 2 vCPU/20% допустим максимум 8. Исправлено без увеличения CPU.

Используется существующая `main-network` (`enpqri1ec01qd9agt1v3`) через Terraform data source. Она и её прежняя подсеть не изменяются. В каталоге диплома созданы только две новые подсети (`10.60.1.0/24` и `10.60.2.0/24`), отдельная таблица маршрутизации, две security groups и две ВМ. Приватный web выходит через ранее созданный NAT gateway диплома. Новая VPC, ALB и расписание снимков в отладочном профиле не создаются. Прежний стенд из шести остановленных ВМ не изменялся.

Control имеет публичный адрес, SSH и веб-интерфейсы разрешены только с административного `/32`. Elasticsearch снаружи закрыт. Web не имеет публичного IP, SSH и HTTP к нему доступны с control. Не подключается default security group с широкими внутренними разрешениями.

## Настройка

Все сервисы устанавливаются нативными пакетами и управляются systemd. Для совместного размещения nginx и Zabbix frontend использует отдельный virtual host `/etc/nginx/sites-available/zabbix` на 8080; сайт работает на 80.

Официальный Elastic APT index вернул `403 Forbidden`. В отладочном профиле используется зеркало `https://mirror.yandex.ru/mirrors/elastic/8` с исходным ключом Elastic и обычной проверкой подписей APT. По индексу закреплена общая версия 8.19.23 для Elasticsearch, Kibana и Filebeat. Переопределения находятся в `ansible/vars/debug.yml`.

```bash
# На рабочем месте; свежий YC_TOKEN берётся из игнорируемого .env.
python scripts/terraform_cloud.py apply --directory terraform-debug
terraform -chdir=terraform-debug output -json > terraform-debug/output.json
python scripts/pin_cloud_hostkeys.py terraform-debug/output.json --known-hosts .local/known_hosts-debug
```

SSH host keys получены из последовательной консоли через аутентифицированный API облака. Проверка host keys не отключается. В Ubuntu WSL:

```bash
python3 scripts/render_inventory.py terraform-debug/output.json \
  --identity /home/yuri/.local/share/diplom-irina/id_ed25519 \
  --inventory ansible/inventory/hosts-debug.yml \
  --ssh-config .local/ssh_config-debug \
  --known-hosts .local/known_hosts-debug

cd ansible
ansible-playbook site.yml -i inventory/hosts-debug.yml \
  -e @vars/debug.yml \
  --vault-password-file /home/yuri/.local/share/diplom-irina/vault-pass
```

При отдельной установке Ansible указать пути к нему и коллекциям из requirements.yml. В рабочей WSL проверочный Ansible находится в `/home/yuri/.cache/irina-check/libs`; переменные окружения `PYTHONPATH`, `PATH`, `ANSIBLE_COLLECTIONS_PATH` и `ANSIBLE_CONFIG` задаются явно. Vault password file в Linux имеет права 0600: файл на NTFS может выглядеть исполняемым и ошибочно распознаваться как password script.

В локальном `.local/service-credentials.json` находятся отдельные случайные пароли, в `ansible/vars/secrets.yml` — зашифрованные Ansible Vault настройки сервисов. Эти файлы, приватный ключ и state игнорируются Git.

## Доступ для отладки

```bash
ssh -N -F .local/ssh_config-debug \
  -L 18080:127.0.0.1:8080 \
  -L 15601:127.0.0.1:5601 \
  -L 19200:127.0.0.1:9200 \
  irina-debug-control.ru-central1.internal
```

Zabbix — `http://127.0.0.1:18080`, пользователь `Admin`; Kibana — `http://127.0.0.1:15601`, пользователь `elastic`. Пароли читать из локального файла, не отправлять через публичный HTTP. Для первичной настройки и проверки предусмотрен `python scripts/finish_debug.py`; он заменяет стандартный пароль Zabbix, регистрирует оба узла и HTTP-сценарии, создаёт data view Kibana. Запускать после установки пакетов и создания тестового трафика.

## Проверено 24 октября 2026

- Обе ВМ имеют статус RUNNING; прежние шесть ВМ остались STOPPED — `evidence/debug-cloud.json`.
- Повторный полный запуск Ansible: control `ok=57 changed=0 failed=0`, web `ok=20 changed=0 failed=0`. После этого в скрипт дампа добавлен явный переход в каталог резервных копий, чтобы он работал независимо от текущего каталога запуска; обновлённый скрипт установлен и проверен.
- Terraform после развёртывания: `No changes. Your infrastructure matches the configuration.`
- Все ожидаемые нативные службы active — `evidence/debug-systemd.json`.
- Получен PostgreSQL dump размером около 4,66 мегабайта. Он успешно восстановлен в отдельную временную базу: найдены оба управляемых узла и две записи пользователей; временная база затем удалена. Основная база не перезаписывалась — `evidence/debug-backup-restore.json`.

## Ограничения итоговой сдачи

Этот профиль — отладка, не завершённый диплом: роли объединены на control, нет облачного ALB, отдельных ВМ для Elastic/Kibana/Zabbix и ежедневных облачных снимков всех дисков. Проверка отказа nginx на двух узлах не подтверждает отказоустойчивость всех сервисов. Для финальной сдачи остаётся полный профиль либо согласованная руководителем адаптация.
