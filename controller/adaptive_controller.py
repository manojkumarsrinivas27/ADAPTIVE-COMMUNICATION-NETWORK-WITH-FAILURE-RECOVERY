import os
import socket
import sys
import time

import networkx as nx
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import arp, ether_types, ethernet, ipv4, packet
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event
from ryu.topology.api import get_switch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import protocol


def fmt(path):
    return ">".join(str(p) for p in path) if path else "none"


class AdaptiveController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    ADAPTIVE = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datapaths = {}
        self.graph = nx.Graph()
        self.hosts = {}
        self.flows = {}
        self.log_path = os.environ.get("CONTROLLER_LOG", "results/logs/controller.csv")
        os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)
        with open(self.log_path, "w") as f:
            f.write("time,event,detail\n")
        if self.ADAPTIVE:
            hub.spawn(self.alert_loop)

    def record(self, name, detail=""):
        with open(self.log_path, "a") as f:
            f.write("%.6f,%s,%s\n" % (time.time(), name, detail))
        self.logger.info("%s %s", name, detail)

    def add_flow(self, dp, priority, match, actions):
        parser = dp.ofproto_parser
        ofp = dp.ofproto
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=priority, match=match, instructions=inst))

    def delete_flow(self, dp, match):
        parser = dp.ofproto_parser
        ofp = dp.ofproto
        dp.send_msg(parser.OFPFlowMod(
            datapath=dp,
            command=ofp.OFPFC_DELETE,
            out_port=ofp.OFPP_ANY,
            out_group=ofp.OFPG_ANY,
            match=match,
        ))

    def send_packet(self, dp, port, data):
        parser = dp.ofproto_parser
        ofp = dp.ofproto
        dp.send_msg(parser.OFPPacketOut(
            datapath=dp,
            buffer_id=ofp.OFP_NO_BUFFER,
            in_port=ofp.OFPP_CONTROLLER,
            actions=[parser.OFPActionOutput(port)],
            data=data,
        ))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        self.datapaths[dp.id] = dp
        self.graph.add_node(dp.id)
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, parser.OFPMatch(), actions)
        self.record("SWITCH_UP", str(dp.id))

    @set_ev_cls(event.EventSwitchLeave)
    def switch_leave_handler(self, ev):
        dpid = ev.switch.dp.id
        if not self.ADAPTIVE:
            return
        self.datapaths.pop(dpid, None)
        if dpid in self.graph:
            self.graph.remove_node(dpid)
            self.record("SWITCH_DOWN", str(dpid))
            self.reroute_affected()

    @set_ev_cls(event.EventLinkAdd)
    def link_add_handler(self, ev):
        link = ev.link
        s, d = link.src.dpid, link.dst.dpid
        self.graph.add_edge(
            s, d,
            ports={s: link.src.port_no, d: link.dst.port_no},
            weight=1 + 0.001 * (s + d),
        )
        self.record("LINK_UP", "%d-%d" % (s, d))
        if self.ADAPTIVE:
            self.optimise_flows()

    @set_ev_cls(event.EventLinkDelete)
    def link_delete_handler(self, ev):
        if not self.ADAPTIVE:
            return
        link = ev.link
        s, d = link.src.dpid, link.dst.dpid
        if self.graph.has_edge(s, d):
            self.graph.remove_edge(s, d)
            self.record("LINK_DOWN", "%d-%d via=lldp" % (s, d))
            self.reroute_affected()

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        if not self.ADAPTIVE:
            return
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        port_no = msg.desc.port_no
        down = msg.desc.state & ofp.OFPPS_LINK_DOWN or msg.desc.config & ofp.OFPPC_PORT_DOWN
        if not down:
            return
        removed = [(u, v) for u, v, data in self.graph.edges(data=True)
                   if data["ports"].get(dp.id) == port_no]
        for u, v in removed:
            self.graph.remove_edge(u, v)
            self.record("LINK_DOWN", "%d-%d via=port_status" % (u, v))
        if removed:
            self.reroute_affected()

    def is_edge_port(self, dpid, port):
        for _, _, data in self.graph.edges(data=True):
            if data["ports"].get(dpid) == port:
                return False
        return True

    def edge_ports(self, dpid):
        switches = get_switch(self, dpid)
        if not switches:
            return []
        return [p.port_no for p in switches[0].ports
                if p.port_no < ofproto_v1_3.OFPP_MAX and self.is_edge_port(dpid, p.port_no)]

    def port_toward(self, u, v):
        return self.graph[u][v]["ports"][u]

    def path_valid(self, path):
        return all(self.graph.has_edge(a, b) for a, b in zip(path, path[1:]))

    def compute_path(self, key):
        a, b = key
        if a not in self.hosts or b not in self.hosts:
            return None
        sa, sb = self.hosts[a][0], self.hosts[b][0]
        if sa == sb:
            return [sa]
        try:
            return nx.shortest_path(self.graph, sa, sb, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def install_direction(self, src_ip, dst_ip, path):
        for i, dpid in enumerate(path):
            dp = self.datapaths.get(dpid)
            if dp is None:
                continue
            if i + 1 < len(path):
                out = self.port_toward(dpid, path[i + 1])
            else:
                out = self.hosts[dst_ip][1]
            parser = dp.ofproto_parser
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=src_ip, ipv4_dst=dst_ip)
            self.add_flow(dp, 10, match, [parser.OFPActionOutput(out)])

    def install_path(self, key, path):
        a, b = key
        self.install_direction(a, b, path)
        self.install_direction(b, a, list(reversed(path)))

    def remove_rules(self, key, dpids):
        a, b = key
        for src, dst in ((a, b), (b, a)):
            for dpid in dpids:
                dp = self.datapaths.get(dpid)
                if dp is None:
                    continue
                parser = dp.ofproto_parser
                self.delete_flow(dp, parser.OFPMatch(eth_type=0x0800, ipv4_src=src, ipv4_dst=dst))

    def reroute(self, key, tag="REROUTE"):
        old = self.flows.get(key)
        new = self.compute_path(key)
        if new:
            self.install_path(key, new)
        if old:
            keep = set(new or [])
            self.remove_rules(key, [d for d in old if d not in keep])
        self.flows[key] = new
        self.record(tag if new else "NO_PATH", "%s-%s old=%s new=%s" % (key[0], key[1], fmt(old), fmt(new)))

    def reroute_affected(self):
        for key in list(self.flows):
            path = self.flows[key]
            if path is not None and not self.path_valid(path):
                self.record("FLOW_AFFECTED", "%s-%s path=%s" % (key[0], key[1], fmt(path)))
                self.reroute(key)

    def optimise_flows(self):
        for key in list(self.flows):
            best = self.compute_path(key)
            if best is not None and best != self.flows[key]:
                self.reroute(key, "RESTORE" if self.flows[key] is not None else "RECOVER")

    def learn(self, ip, mac, dpid, port):
        if not self.is_edge_port(dpid, port):
            return
        if self.hosts.get(ip) != (dpid, port, mac):
            self.hosts[ip] = (dpid, port, mac)
            self.record("HOST_LEARNED", "%s dpid=%d port=%d" % (ip, dpid, port))

    def flood_edges(self, data, skip=None):
        for dpid, dp in self.datapaths.items():
            for port in self.edge_ports(dpid):
                if skip == (dpid, port):
                    continue
                self.send_packet(dp, port, data)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        in_port = msg.match["in_port"]
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None or eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        arp_pkt = pkt.get_protocol(arp.arp)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if arp_pkt:
            self.handle_arp(dp, in_port, arp_pkt, msg)
        elif ip_pkt:
            self.handle_ip(dp, in_port, eth, ip_pkt, msg)

    def handle_arp(self, dp, in_port, a, msg):
        self.learn(a.src_ip, a.src_mac, dp.id, in_port)
        if a.opcode == arp.ARP_REQUEST:
            if a.dst_ip in self.hosts:
                mac = self.hosts[a.dst_ip][2]
                reply = packet.Packet()
                reply.add_protocol(ethernet.ethernet(dst=a.src_mac, src=mac, ethertype=ether_types.ETH_TYPE_ARP))
                reply.add_protocol(arp.arp(
                    opcode=arp.ARP_REPLY,
                    src_mac=mac,
                    src_ip=a.dst_ip,
                    dst_mac=a.src_mac,
                    dst_ip=a.src_ip,
                ))
                reply.serialize()
                self.send_packet(dp, in_port, reply.data)
            else:
                self.flood_edges(msg.data, skip=(dp.id, in_port))
        elif a.opcode == arp.ARP_REPLY and a.dst_ip in self.hosts:
            dpid, port, _ = self.hosts[a.dst_ip]
            if dpid in self.datapaths:
                self.send_packet(self.datapaths[dpid], port, msg.data)

    def handle_ip(self, dp, in_port, eth, ip, msg):
        self.learn(ip.src, eth.src, dp.id, in_port)
        if ip.src not in self.hosts or ip.dst not in self.hosts:
            return
        key = tuple(sorted((ip.src, ip.dst)))
        if self.flows.get(key) is None:
            path = self.compute_path(key)
            if path is None:
                if key not in self.flows:
                    self.flows[key] = None
                    self.record("NO_PATH", "%s-%s" % key)
                return
            self.install_path(key, path)
            self.flows[key] = path
            self.record("PATH_INSTALLED", "%s-%s path=%s" % (key[0], key[1], fmt(path)))
        path = self.flows[key]
        route = path if ip.src == key[0] else list(reversed(path))
        if dp.id not in route:
            return
        i = route.index(dp.id)
        if i + 1 < len(route):
            out = self.port_toward(dp.id, route[i + 1])
        else:
            out = self.hosts[ip.dst][1]
        self.send_packet(dp, out, msg.data)

    def alert_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", protocol.CONTROLLER_ALERT_PORT))
        while True:
            data, addr = sock.recvfrom(4096)
            try:
                ptype, _, _, _, payload = protocol.unpack(data)
            except ValueError:
                continue
            if ptype != protocol.ALERT:
                continue
            dst = payload.decode(errors="ignore")
            key = tuple(sorted((addr[0], dst)))
            self.record("ALERT_RECEIVED", "%s>%s" % (addr[0], dst))
            path = self.flows.get(key)
            if path is not None and not self.path_valid(path):
                self.reroute(key, "ALERT_REROUTE")
            elif path is None and key in self.flows:
                self.reroute(key, "ALERT_RECOVER")
            elif path is not None:
                # Path looks valid to the controller, but the application still
                # sees loss: re-install the flow rules to be safe.
                self.reroute(key, "ALERT_REFRESH")
            else:
                self.record("ALERT_PATH_OK", "%s-%s" % key)
