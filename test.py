#!/usr/bin/python3

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel, info
from mininet.cli import CLI
import time
import os


class LinuxRouter(Node):
    "A Node with IP forwarding enabled."

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        # Enable forwarding on the router
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


class NetworkTopo(Topo):
    "A LinuxRouter connecting three IP subnets"

    def build(self, **_opts):
        defaultIP1 = '10.0.3.10/24'  # IP address for r0-eth1
        defaultIP2 = '10.0.3.20/24'
        router1 = self.addNode('r1', cls=LinuxRouter, ip=defaultIP1)
        router2 = self.addNode('r2', cls=LinuxRouter, ip=defaultIP2)

        h1 = self.addHost('h1', ip='10.0.1.100/24', defaultRoute='via 10.0.1.10')  # define gateway
        h2 = self.addHost('h2', ip='10.0.2.100/24', defaultRoute='via 10.0.2.20')

        self.addLink(router1, router2, intfName1='r1-eth1', intfName2='r2-eth1')
        self.addLink(h1, router1, intfName2='r1-eth2',
                     params2={'ip': '10.0.1.10/24'})  # params2 define the eth2 ip address
        self.addLink(h2, router2, intfName2='r2-eth2', params2={'ip': '10.0.2.20/24'})


def run():
    "Test linux router"
    topo = NetworkTopo()
    net = Mininet(controller=None, topo=topo)  # controller is used by s1-s3
    net.start()
    info('*** Routing Table on Router:\n')

    r1 = net.getNodeByName('r1')
    r2 = net.getNodeByName('r2')
    info('starting zebra and ospfd service:\n')

    r1.cmd('zebra -f /usr/local/etc/r1zebra.conf -d -z /tmp/r1zebra.api -i /tmp/r1zebra.interface')
    r2.cmd('zebra -f /usr/local/etc/r2zebra.conf -d -z /tmp/r2zebra.api -i /tmp/r2zebra.interface')
    time.sleep(1)  # time for zebra to create api socket
    r1.cmd('ospfd -f /usr/local/etc/r1ospfd.conf -d -z /tmp/r1zebra.api -i /tmp/r1ospfd.interface')
    r2.cmd('ospfd -f /usr/local/etc/r2ospfd.conf -d -z /tmp/r2zebra.api -i /tmp/r2ospfd.interface')

    CLI(net)
    net.stop()
    os.system("killall -9 ospfd zebra")
    os.system("rm -f /tmp/*.api")
    os.system("rm -f /tmp/*.interface")


if __name__ == '__main__':
    setLogLevel('info')
    run()
