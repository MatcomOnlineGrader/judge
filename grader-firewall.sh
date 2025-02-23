#!/bin/sh
iptables -F
iptables -A OUTPUT -m owner --uid-owner 0 -j ACCEPT
iptables -A OUTPUT -j DROP
