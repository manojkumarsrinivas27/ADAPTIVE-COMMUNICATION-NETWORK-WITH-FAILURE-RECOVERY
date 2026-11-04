import time

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import Node, OVSKernelSwitch, RemoteController

SERVER_IP = "10.0.0.2"
ALERT_IP = "10.0.0.100"
CLIENT_HOSTS = ["h1", "h3", "h4"]


def build_network(delay="5ms", loss=0, bw=10, controller_ip="127.0.0.1", controller_port=6653):
    net = Mininet(controller=None, switch=OVSKernelSwitch, link=TCLink, autoSetMacs=True)
    net.addController("c0", controller=RemoteController, ip=controller_ip, port=controller_port)

    switches = {}
    for name in ("s1", "s2", "s3", "s4"):
        switches[name] = net.addSwitch(name, protocols="OpenFlow13", failMode="secure")

    hosts = {}
    for name, ip in (("h1", "10.0.0.1"), ("h2", "10.0.0.2"), ("h3", "10.0.0.3"), ("h4", "10.0.0.4")):
        hosts[name] = net.addHost(name, ip=ip + "/24")

    net.addLink(hosts["h1"], switches["s1"], bw=bw)
    net.addLink(hosts["h3"], switches["s1"], bw=bw)
    net.addLink(hosts["h4"], switches["s1"], bw=bw)
    net.addLink(hosts["h2"], switches["s4"], bw=bw)

    core = {"bw": bw, "delay": delay}
    if loss:
        core["loss"] = loss
    net.addLink(switches["s1"], switches["s2"], **core)
    net.addLink(switches["s2"], switches["s4"], **core)
    net.addLink(switches["s1"], switches["s3"], **core)
    net.addLink(switches["s3"], switches["s4"], **core)

    root = Node("root", inNamespace=False)
    intf = net.addLink(root, switches["s1"]).intf1
    root.setIP(ALERT_IP, prefixLen=24, intf=intf)

    net.start()
    return net


def main():
    setLogLevel("info")
    net = build_network()
    time.sleep(5)
    net.pingAll()
    CLI(net)
    net.stop()


if __name__ == "__main__":
    main()
