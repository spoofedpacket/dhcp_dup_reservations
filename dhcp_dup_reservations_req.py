#!/usr/bin/env python3

import requests

resp = requests.get('https://localhost:8443/dhcp', verify='/var/lib/puppet/ssl/certs/ca.pem', cert=('/var/lib/puppet/ssl/certs/localhost.pem', '/var/lib/puppet/ssl/private_keys/localhøst.pem'))

print(resp.status_code)
print(resp.text)
