#!/usr/bin/env python3

import json
import requests
import logging

from sys            import argv, stderr

# Send SSL cn deprecation warnings to syslog
logging.captureWarnings(True)

def pp_json(data):
    pretty_json = json.dumps(data, sort_keys=True, indent=2, separators=(",", ": "))
    print(pretty_json)

def key_by(data, key):
    keyed_data = dict()

    for a_dict in data:
        keyed_data[a_dict[key]] = a_dict

    return keyed_data

protocol = "https"

# Template for dhcp API base URLs
base_url_template  = "{0}://{1}:8443/dhcp/{2}"
lease_url_template = "{0}/{1}"

# "Parse" arguments
dhcp_primary   = argv[1]
dhcp_secondary = argv[2]
subnet         = argv[3]

# SSL paths
ssl_root  = "/var/lib/puppet/ssl/"
ca_path   = ssl_root + "certs/ca.pem"
cert_path = ssl_root + "certs/" + dhcp_primary + ".pem"
key_path  = ssl_root + "private_keys/" + dhcp_primary + ".pem"

# Get the base urls
dhcp_primary_base_url   = base_url_template.format(protocol, dhcp_primary,   subnet)
dhcp_secondary_base_url = base_url_template.format(protocol, dhcp_secondary, subnet)

primary_records_resp = requests.get(dhcp_primary_base_url, verify=ca_path, cert=(cert_path, key_path))
secondary_records_resp = requests.get(dhcp_secondary_base_url, verify=ca_path, cert=(cert_path, key_path))

# Parse the JSON
primary_records   = json.loads(primary_records_resp.text)
secondary_records = json.loads(secondary_records_resp.text)

# We just care about the reservations
primary_reservations   = primary_records[  "reservations"]
secondary_reservations = secondary_records["reservations"]

# Key for faster lookup
keyed_primary_reservations   = key_by(primary_reservations,   "ip")
keyed_secondary_reservations = key_by(secondary_reservations, "ip")

# Items to change in secondary
delete_ip_on_secondary = dict()
add_lease_on_secondary = dict()

for ip, lease in keyed_secondary_reservations.items():
    if ip not in keyed_primary_reservations:
        # Queue for deletion
        delete_ip_on_secondary[ip] = lease

for ip, lease in keyed_primary_reservations.items():
    primary_lease_url   = lease_url_template.format(dhcp_primary_base_url, ip)
    secondary_lease_url = lease_url_template.format(dhcp_primary_base_url, ip)

    primary_detail_lease_resp = requests.get(primary_lease_url, verify=ca_path, cert=(cert_path, key_path))

    # Parse the detailed lease
    primary_detail_lease = json.loads(primary_detail_lease_resp.text)

    if ip in keyed_secondary_reservations:
        # Obtain detail about reservation from secondary
        secondary_detail_lease_resp = requests.get(secondary_lease_url, verify=ca_path, cert=(cert_path, key_path))

        # Parse the detailed lease
        secondary_detail_lease = json.loads(secondary_detail_lease_resp.text)

        # Continue if they are the same
        if set(primary_detail_lease.items()) == set(secondary_detail_lease.items()):
            continue

        # Queue for update
        delete_ip_on_secondary[ip] = lease
        add_lease_on_secondary[ip] = primary_detail_lease
    else:
        # Queue for addition
        add_lease_on_secondary[ip] = primary_detail_lease

for ip, lease in delete_ip_on_secondary.items():
    secondary_lease_url = lease_url_template.format(dhcp_secondary_base_url, ip)

    delete_response = requests.delete(secondary_lease_url, verify=ca_path, cert=(cert_path, key_path))

    # Notify about deletion
    print("Deleted reservation for {0} ({1}):\n".format(ip, lease["hostname"]),
          delete_response.text,
          file=stderr)

for ip, detail_lease in add_lease_on_secondary.items():
    secondary_lease_url = dhcp_secondary_base_url

    # This does not belong
    del detail_lease["subnet"]

    # Remove nextServer. Leave it up to the remote smart proxy and/or DHCP server to set this.
    # This was added due to the remote smart proxy adding double quotes around the next-server
    # value (which was in hex) leading to incorrect values for next-server being offered to the client.
    del detail_lease["nextServer"]

    # This does belong
    detail_lease["name"] = detail_lease["hostname"]

    post_data = ""

    # Encode Request
    for k, v in detail_lease.items():
        if post_data:
            post_data += "&"

        post_data += "{0}={1}".format(k, v)

    # Add the lease
    post_response = requests.post(secondary_lease_url, data=post_data, verify=ca_path, cert=(cert_path, key_path))

    # Notify about addition
    print("Added reservation for {0} ({1}):\n".format(ip, lease["hostname"]),
          post_response.text,
          file=stderr)

exit(0)

# vim: set ts=4 sw=4 et syn=python:
