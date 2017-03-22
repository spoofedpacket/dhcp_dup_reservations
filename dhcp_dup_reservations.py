#!/usr/bin/env python3

import json

from urllib.request import Request, urlopen
from sys            import argv, stderr


def pp_json(data):
    pretty_json = json.dumps(data, sort_keys=True, indent=2, separators=(",", ": "))
    print(pretty_json)

def key_by(data, key):
    keyed_data = dict()

    for a_dict in data:
        keyed_data[a_dict[key]] = a_dict

    return keyed_data


# Thanks to Dave and Raj: http://stackoverflow.com/a/6312600/5347993
class RequestWithMethod(Request):
  def __init__(self, *args, **kwargs):
    self._method = kwargs.pop('method', None)
    Request.__init__(self, *args, **kwargs)

  def get_method(self):
    return self._method if self._method else super(RequestWithMethod, self).get_method()


# TODO: Support HTTPS
protocol = "http"

# Template for dhcp API base URLs
base_url_template  = "{0}://{1}/dhcp/{2}"
lease_url_template = "{0}/{1}"

# "Parse" arguments
dhcp_primary   = argv[1]
dhcp_secondary = argv[2]
subnet         = argv[3]

# Get the base urls
dhcp_primary_base_url   = base_url_template.format(protocol, dhcp_primary,   subnet)
dhcp_secondary_base_url = base_url_template.format(protocol, dhcp_secondary, subnet)

# Fetch the current records
with urlopen(dhcp_primary_base_url)   as primary_records_socket:
    primary_records_json   = primary_records_socket.read().decode("utf8")

with urlopen(dhcp_secondary_base_url) as secondary_records_socket:
    secondary_records_json = secondary_records_socket.read().decode("utf8")

# Parse the JSON
primary_records   = json.loads(primary_records_json)
secondary_records = json.loads(secondary_records_json)

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

    # Obtain detail about reservation from primary
    with urlopen(primary_lease_url) as primary_lease_socket:
        primary_detail_lease_json = primary_lease_socket.read().decode("utf8")

    # Parse the detailed lease
    primary_detail_lease = json.loads(primary_detail_lease_json)

    if ip in keyed_secondary_reservations:
        # Obtain detail about reservation from secondary
        with urlopen(secondary_lease_url) as secondary_lease_socket:
            secondary_detail_lease_json = secondary_lease_socket.read().decode("utf8")

        # Parse the secondary detailed lease
        secondary_detail_lease = json.loads(secondary_detail_lease_json)

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

    delete_request = RequestWithMethod(secondary_lease_url,
                                       method="DELETE")

    # Delete the lease
    with urlopen(delete_request) as lease_delete_socket:
        delete_response = lease_delete_socket.read().decode("utf8")

    # Notify about deletion
    print("Deleted reservation for {0} ({1}):\n".format(ip, lease["hostname"]),
          delete_response,
          file=stderr)

for ip, detail_lease in add_lease_on_secondary.items():
    secondary_lease_url = dhcp_secondary_base_url

    # This does not belong
    del detail_lease["subnet"]

    # This does belong
    detail_lease["name"] = detail_lease["hostname"]

    post_data = ""

    # Encode Request
    for k, v in detail_lease.items():
        if post_data:
            post_data += "&"

        post_data += "{0}={1}".format(k, v)

    post_request = RequestWithMethod(secondary_lease_url,
                                     data=post_data.encode("utf8"),
                                     method="POST")

    # Add the lease
    with urlopen(post_request) as lease_post_socket:
        post_response = lease_post_socket.read().decode("utf8")

    # Notify about addition
    print("Added reservation for {0} ({1}):\n".format(ip, lease["hostname"]),
          post_response,
          file=stderr)

exit(0)

# vim: set ts=4 sw=4 et syn=python:
