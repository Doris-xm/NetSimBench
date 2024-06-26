"""
Spine-Leaf network topology with Mininet
A performance test
"""
import os
from mininet.cli import CLI
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel, info

from frrouting import startFRR, configureFRR
from topo import SpineLeafTopo

n_spine = 2
n_leaf = 2
m_hosts = 2

def perfTest(lossy=True):
    "Create network and run simple performance test"
    topo = SpineLeafTopo(n_leaf=n_leaf, m_hosts=m_hosts, n_spine=n_spine, bw=10, delay='5ms', loss=10 if lossy else 0, lossy=lossy)
    net = Mininet(topo=topo,
                  host=CPULimitedHost, link=TCLink,
                  autoStaticArp=True)
    net.start()
    info("Dumping host connections\n")
    dumpNodeConnections(net.hosts)

    startFRR(net)
    configureFRR(net)

    # info("Testing network connectivity\n")
    # net.pingAllFull()

    # info("Testing bandwidth between h1 and h4 (lossy=%s)\n" % lossy)
    h1, h2, h3, h4 = net.get('h1', 'h2', 'h3', 'h4')
    # net.iperf((h1, h4), l4Type='UDP')
    # net.iperf((h1, h2))
    # # Debugging
    # h1.cmd('jobs')
    # h4.cmd('jobs')


    CLI(net)
    net.stop()


if __name__ == '__main__':
    try:
        setLogLevel('info')
        # Debug for now
        perfTest(lossy=False)
    except Exception as e:
        print(e)
        # exec " sudo mn -c " to clean up mininet
        os.system("sudo mn -c")
