"""Initialize the full six-VM Zabbix, Elasticsearch and Kibana deployment."""
import sys
from finish_debug import main,ROOT

if __name__=='__main__':
    sys.argv[1:]=['--inventory',str(ROOT/'ansible/inventory/hosts.yml'),
                  '--evidence',str(ROOT/'evidence/full-services.json'),*sys.argv[1:]]
    main()
