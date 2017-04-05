# dhcp_dup_reservations

## Description

Duplicate DHCP reservations from one foreman-proxy to another. Useful until such time as foreman supports writing to more than one DHCP proxy :)

Based on a script found in the following thread: https://groups.google.com/forum/#!topic/foreman-users/pofaWG8NEiE

Modified to support HTTPS.

## Requirements

* Python (>= 2.7)
* Python modules: requests

## Usage

To sync all records for the subnet 192.172.10.0 from my-dhcp-primary.example.com to my-dhcp-secondary.example.com:

    ./dhcp_dup_reservations.py my-dhcp-primary.example.com my-dhcp-secondary.example.com 192.172.10.0

The script looks in /var/lib/puppet/ssl for the necessary certs and keys as this is the most common setup with puppet and foreman-proxy, although you can modify it to look in a different place by editing the ssl_root variable.

To sync all records for all subnets known to your foreman-proxy, you could call the script in a loop, using curl and jq to parse the JSON (this would be useful as a cron job, for example):

    PRIMARY=`hostname -f`
    SECONDARY="my-dhcp-secondary.example.com"
    SSL_ROOT="/var/lib/puppet/ssl"
 
    for RANGE in `curl -s --cacert ${SSL_ROOT}/certs/ca.pem \
               --cert ${SSL_ROOT}/certs/${PRIMARY}.pem \
               --key ${SSL_ROOT}/private_keys/${PRIMARY}.pem \
               https://${PRIMARY}:8443/dhcp | jq --monochrome-output --raw-output '.[].network'`; do
               dhcp_dup_reservations.py $PRIMARY $SECONDARY $RANGE
    done
