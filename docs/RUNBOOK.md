# Развёртывание и обслуживание

## Подготовка

Нужны Terraform 1.9+, yc CLI и Linux/Ubuntu WSL с Ansible Core 2.17. Коллекции перечислены в `ansible/requirements.yml`. Применяются подписанные нативные пакеты Ubuntu/Zabbix/Elastic. Для установки и запуска используется один закреплённый образ Ubuntu 22.04 LTS.

Заполнить `terraform/terraform.tfvars` по примеру: cloud/folder ID, существующий network_id, административный IPv4 /32, image_id и публичный SSH-ключ. `preemptible=false` нужен для сдачи. Один snapshot schedule создаёт ежедневные копии всех boot disks; `snapshot_cron` задаёт время UTC. Сейчас используется `6 9 * * *`.

Квоты текущей схемы: шесть дополнительных ВМ к шести прежним, по 1,2 CPU квоты в d/e, память около 10,74 гигабайта в d и 8,59 в e; SSD около 53,69 гигабайта в d и 10,74 в e; HDD около 21,47 гигабайта в e; пять новых SG, четыре подсети, четыре внешних IP с ALB. Для семи поколений шести снимков нужно минимум 42 свободных места; фактический лимит увеличен до 96 с учётом прежних копий.

Получить IAM-токен через yc и сохранить только в локальном `.env` или переменной `YC_TOKEN`. Токен, state, tfvars и планы исключены из Git. Terraform сам `.env` не читает, его загружает обёртка `scripts/terraform_cloud.py`.

```bash
terraform -chdir=terraform init
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
python scripts/terraform_cloud.py plan
# Просмотреть план: только собственные ресурсы, без изменения прежнего стенда.
python scripts/terraform_cloud.py apply
terraform -chdir=terraform output -json > terraform/output.json
python scripts/pin_cloud_hostkeys.py terraform/output.json --known-hosts .local/known_hosts
```

При таймауте создания ALB сначала проверить существующий ресурс и его операцию. Не создавать дубликат вслепую. В этом развёртывании операция продолжилась после исходного таймаута Terraform и завершилась ACTIVE; ресурс сохранил тот же ID и IP. Для последующих операций timeout увеличен до 30 минут.

## SSH и Ansible

Генератор inventory запускать в Linux/WSL, откуда будут выполняться SSH-подключения: в SSH config записываются абсолютные пути. Inventory — JSON, также корректный YAML; хосты представлены FQDN. HostKeyAlias бастиона сохраняет проверку его доверенного FQDN-ключа при изменении публичного IP.

```bash
python3 scripts/render_inventory.py terraform/output.json \
  --identity ~/.local/share/diplom-irina/id_ed25519 \
  --inventory ansible/inventory/hosts.yml \
  --ssh-config .local/ssh_config --known-hosts .local/known_hosts
ansible-galaxy collection install -r ansible/requirements.yml
cd ansible
ansible-playbook site.yml -i inventory/hosts.yml \
  --vault-password-file ~/.local/share/diplom-irina/vault-pass
```

Создать `ansible/vars/secrets.yml` по примеру с четырьмя разными случайными паролями длиной не менее 32 символов, зашифровать Ansible Vault. В `.local/service-credentials.json` для API bootstrap нужны те же `elastic_password`, а также отдельные `zabbix_admin_password` и `reviewer_password`. Этот файл не публикуется. Пароль Vault и SSH-ключ в WSL хранить в Linux filesystem с правами 0600.

Для уже подготовленной среды Юрия предусмотрена обёртка Windows `python scripts/run_ansible.py`. Её пути указывают на закреплённое окружение WSL; при переносе использовать обычную команду Ansible выше. Все apt-задачи ожидают освобождения блокировки пакетов: автоматические обновления не отключаются и lock-файлы не удаляются.

После смены публичных IP обновить output/inventory. Для TLS UI требуется обновить SAN сертификата: сохранить старый публичный сертификат для аудита, удалить только `/etc/nginx/irina-tls/server.crt` на соответствующей ВМ и повторить роль public_ui; затем заново проверить `verify_ui.py` и обновить ссылки/отпечатки.

## Инициализация сервисов и проверки

```bash
python scripts/tunnels.py
# В другом терминале, пока SSH-туннели открыты:
python scripts/initialize_services.py
python scripts/configure_monitoring.py
python scripts/configure_kibana.py
python scripts/verify_ui.py
python scripts/verify_infrastructure.py
python scripts/verify_backups.py
```

Последняя команда требует READY-снимки всех шести текущих дисков. Она создаёт временный диск из снимка web-a в зоне d, подключает к web-b, монтирует файловую систему `ro,noload`, проверяет SHA-256 сайта и удаляет временный диск после отключения. Требуется временный запас дисковой квоты; основные диски не перезаписываются. При неизвестном результате операции сначала проверить её и временный диск `irina-restore-check`, не повторять создание бесконтрольно.

`verify_infrastructure.py` на короткое время останавливает nginx на web-a и в finally запускает его обратно. Это активная проверка учебного стенда, её не следует запускать во время демонстрации руководителю.

## Диагностика

Через `.local/ssh_config` подключиться по FQDN и проверить `systemctl status nginx zabbix-agent filebeat`, на служебных узлах — соответствующие `zabbix-server`, `postgresql`, `elasticsearch`, `kibana`. Журналы: `journalctl -u <service>`, `/var/log/nginx/access.log`, `/var/log/nginx/error.log`.

USE collector: `systemctl status irina-metrics.timer`, `journalctl -u irina-metrics.service`, JSON `/var/lib/irina-metrics/metrics.json`. Агент читает JSON через фиксированный UserParameter, без удалённого исполнения произвольных команд. Пустой/отсутствующий источник метрики вызывает ошибку item, а не подменяется сообщением об отсутствии проблем.

Проверка конфигурации Filebeat:

```bash
sudo filebeat test config --path.home /usr/share/filebeat --path.config /etc/filebeat
sudo nginx -t
sudo ufw status verbose
```

Дамп PostgreSQL создаётся от postgres в 00:30 UTC: `/usr/local/sbin/zabbix-dump`. Каталог `/var/backups/zabbix` имеет права 0700, старые дампы удаляются по семидневной политике. Snapshot schedule срабатывает в 09:06 UTC; проверять READY и подключение всех дисков через yc snapshot-schedule list-disks/list-snapshots.

## Завершение эксплуатации

ВМ непрерываемые и продолжают тарифицироваться. После сдачи сохранить необходимые данные и выбрать остановку либо удаление собственных ресурсов. Остановка ВМ не прекращает оплату дисков, снимков, балансировщика и адресов. Для удаления использовать план `terraform plan -destroy` в `terraform/`, внимательно проверить границы: существующая VPC — data source и удаляться не должна. Старый стенд, его расписание и снимки остаются вне state этого диплома.
