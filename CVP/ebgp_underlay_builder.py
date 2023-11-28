"""
Generate the interface, prefix-list, route-map, and BGP configs for
spines and leafs by parsing the underlay_yaml using the CVP API
"""

import json
import ssl
import yaml
from cvplibrary import CVPGlobalVariables, GlobalVariableNames
from cvplibrary import RestClient

# Using the API to grab the hostname for use throughout the script
tags = CVPGlobalVariables.getValue(GlobalVariableNames.CVP_SYSTEM_LABELS)

for item in tags:
    key, value = item.split(':')
    if key == 'hostname':  # don't forget the double == here
        hostname = value

ssl._create_default_https_context = ssl._create_unverified_context

# Get the underlay_yaml file so we have all the values we need
CONFIGLET = 'underlay_yaml'
CVP_URL = 'https://localhost/cvpservice/'
client = RestClient(
    CVP_URL+'configlet/getConfigletByName.do?name=' + CONFIGLET, 'GET')

if client.connect():
    raw = json.loads(client.getResponse())

underlay = yaml.safe_load(raw['config'])

# This is a constant, so no need to wrap it in a function
SPINE_PEER_GROUP_CONFIG = """   neighbor LEAF_Underlay peer group
   neighbor LEAF_Underlay send-community
   neighbor LEAF_Underlay maximum-routes 12000
   !
   """


def gen_interfaces(host):
    """
    Generate the interface configurations
    """
    config = ""
    for interface in underlay[host]['interfaces']:
        ip = underlay[host]['interfaces'][interface]['ipv4']
        mask = underlay[host]['interfaces'][interface]['mask']
        config += """interface %s
   ip address %s/%s
""" % (interface, ip, mask)
        if interface.startswith('Ethernet'):
            mtu = underlay['global']['MTU']
            config += """   no switchport
   mtu %s
""" % mtu
        config += """!
"""
    return config


def gen_loopback_pl_rm(host):
    """
    Generate prefix-list and route-map to advertise loopbacks
    """
    seq_num = 10
    config = ""
    config += "ip prefix-list LOOPBACK\n"
    for interface in underlay[host]['interfaces']:
        if interface.startswith('loopback'):
            ip = underlay[host]['interfaces'][interface]['ipv4']
            mask = underlay[host]['interfaces'][interface]['mask']
            config += "   seq %s permit %s/%s eq 32\n" % (seq_num, ip, mask)
            seq_num += 10
    config += """!\nroute-map LOOPBACK permit 10
   match ip address prefix-list LOOPBACK
!"""

    return config


def gen_peer_filter():
    """
    Generate AS peer-filter
    """
    config = ""
    config += """peer-filter LEAF-AS-RANGE
   10 match as-rang 65000-65535 accept"""
    return config


def gen_bgp_lo0_listen_range(host):
    """
    Generate the bgp listen range config the loopback0 peers
    """
    if "DC1" in host:
        lo0 = underlay['global']['DC1']['lo0']
    elif "DC2" in host:
        lo0 = underlay['global']['DC2']['lo0']
    return """   bgp listen range %s peer-group LEAF_Underlay peer-filter LEAF-AS-RANGE
   !""" % lo0


def gen_base_bgp_config(host):
    """
    Generate some base BGP config that all switches will use
    """
    asn = underlay[host]['BGP']['ASN']
    lo0 = underlay[host]['interfaces']['loopback0']['ipv4']
    config = """router bgp %s
   router-id %s
   no bgp default ipv4-unicast
   maximum-paths 3
   distance bgp 20 200 200""" % (asn, lo0)
    if "spine" in host:
        config += """bgp listen range 192.168.0.0/16 peer-group LEAF_Underlay peer-filter LEAF-AS-RANGE"""
    if "leaf" in host:
        if "DC1" in host:
            spine_asn = underlay['global']['DC1']['ASN']
        elif "DC2" in host:
            spine_asn = underlay['global']['DC2']['ASN']
        config += """neighbor SPINE_Underlay peer group
   neighbor SPINE_Underlay remote-as %s
   neighbor SPINE_Underlay send-community
   neighbor SPINE_Underlay maximum-routes 12000
   !
   neighbor LEAF_Peer peer group
   neighbor LEAF_Peer remote-as %s
   neighbor LEAF_Peer next-hop-self
   neighbor LEAF_Peer maximum-routes 12000""" % (spine_asn, asn)
    return config


def gen_leaf_peer_group_config(host):
    asn = underlay[host]['BGP']['ASN']
    spine_asn = underlay[host]['BGP']['spine-ASN']
    config = """   neighbor Underlay peer group
   neighbor Underlay remote-as %s
   neighbor Underlay send-community
   neighbor Underlay maximum-routes 12000
   !
   neighbor LEAF_Peer peer group
   neighbor LEAF_Peer remote-as %s
   neighbor LEAF_Peer next-hop-self
   neighbor LEAF_Peer maximum-routes 12000
   !
   neighbor EVPN peer group
   neighbor EVPN remote-as %s
   neighbor EVPN update-source Loopback0
   neighbor EVPN ebgp-multihop
   neighbor EVPN send-community
   neighbor EVPN maximum-routes 0
   !""" % (spine_asn, asn, spine_asn)
    return config


def gen_spine_configs():
    """
    Generate the underlay and overlay configs for the spines
    """
    print("service routing protocols model multi-agent")
    print(gen_interfaces(hostname))
    print(gen_loopback_pl_rm(hostname))
    print(gen_base_bgp_config(hostname))
    print(SPINE_PEER_GROUP_CONFIG)
    print("   redistribute connected route-map LOOPBACK\n   !")
    print("""   address-family ipv4
      neighbor LEAF_Underlay activate
      redistribute connected route-map LOOPBACK""")


def gen_leaf_configs():
    """
    Generate the underlay and overlay configs for the leafs
    """
    mlag_odd_even = underlay[hostname]['MLAG']
    print(gen_interfaces(hostname))
    print(gen_loopback_pl_rm(hostname))
    print(gen_base_bgp_config(hostname))
    print(gen_leaf_peer_group_config(hostname))

    for spine_peer in underlay[hostname]['BGP']['spine-peers']:
        print("   neighbor %s peer group Underlay") % spine_peer
    print("   !")

    if mlag_odd_even == 'Odd':
        print("   neighbor 192.168.255.2 peer group LEAF_Peer\n   !")
    elif mlag_odd_even == 'Even':
        print("   neighbor 192.168.255.1 peer group LEAF_Peer\n   !")

    if 'DC1' in hostname:
        for spine_peer in underlay['global']['DC1']['spine_peers']:
            print("   neighbor %s peer group EVPN") % spine_peer
    elif 'DC2' in hostname:
        for spine_peer in underlay['global']['DC2']['spine_peers']:
            print("   neighbor %s peer group EVPN") % spine_peer
    print("   !")
    print("   redistribute connected route-map LOOPBACK\n   !")
    print("""   address-family evpn
      neighbor EVPN activate
   !
   address-family ipv4
      neighbor Underlay activate
      neighbor LEAF_Peer activate""")


if 'spine' in hostname:
    gen_spine_configs()
elif 'leaf' in hostname:
    gen_leaf_configs()
