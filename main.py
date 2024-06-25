"""
Spine-Leaf network topology with Mininet
"""
import os

from mininet.cli import CLI
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost, Node
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel, info

n_spine = 2
n_leaf = 2
m_hosts = 2
class LinuxRouter(Node):
    "A Node with IP forwarding enabled."

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

class SpineLeafTopo(Topo):

    """ Spine-Leaf topology with n leaf switches and m hosts per leaf, bw bandwidth """
    def build(self, bw=10, delay='5ms', loss=0, lossy=True):
        spine_switches = []

        # Create spine switches
        for i in range(n_spine):
            spine_switch = self.addSwitch('spine%s' % (i + 1))
            spine_switches.append(spine_switch)

        # Create leaf switches
        for i in range(n_leaf):
            leaf_switch = self.addSwitch('leaf%s' % (i + 1))
            # Create hosts and connect them to leaf switches
            for j in range(m_hosts):
                host = self.addHost('h%s' % (i * m_hosts + j + 1)) #, cpu=.5 / (n_leaf * m_hosts))
                self.addLink(host, leaf_switch) #, bw=bw, delay=delay, loss=loss if lossy else 0) #, use_htb=True)
                self.addLink(leaf_switch, host) #, bw=bw, delay=delay, loss=loss if lossy else 0) #, use_htb=True)

            # fully connect between leaf and spine
            for spine in spine_switches:
                self.addLink(leaf_switch, spine) #, bw=bw, delay=delay, loss=loss) #, use_htb=True)
                self.addLink(spine, leaf_switch) #, bw=bw, delay=delay, loss=loss) #, use_htb=True)



def generateFRRConfig(router_name, router_id, neighbors):
    "Generate FRRouting configuration"
    config = f"""
frr defaults traditional
hostname {router_name}
log file /var/log/frr/{router_name}.log
service integrated-vtysh-config
!
router bgp {router_id}
 bgp router-id {router_id}.{router_id}.{router_id}.{router_id}
"""
    for neighbor in neighbors:
        config += f" neighbor {neighbor['ip']} remote-as {neighbor['as']}\n"

    config += """
!
line vty
"""
    return config

def startFRR(net):
    "Start FRRouting on all routers"
    for router in net.hosts:
        if 'spine' in router.name or 'leaf' in router.name:
            router.cmd('/usr/lib/frr/frrinit.sh start')

def configureFRR(net):
    """ Configure FRRouting on all routers """
    for link in net.links:
        print(link.intf1.node.name, link.intf2.node.name)
        for router in link.intf1.node, link.intf2.node:
            if 'spine' in router.name or 'leaf' in router.name:
                router_name = router.name
                router_id = router_name[-1]
                neighbors = []
                if 'spine' in router_name:
                    # Spine routers connect to leaf routers
                    neighbors = [{'ip': '10.0.0.%s' % (int(router_id) * m_hosts + i + 1), 'as': '200'} for i in range(n_leaf)]
                elif 'leaf' in router_name:
                    # Leaf routers connect to spine routers
                    neighbors = [{'ip': '10.0.0.%s' % (int(router_id) * m_hosts + i + 1), 'as': '100'} for i in range(n_spine)]

                config = generateFRRConfig(router_name, 100 + int(router_id), neighbors)
                config_path = f'./frr_configs/{router_name}.conf'
                with open(config_path, 'w') as f:
                    f.write(config)
                router.cmd(f'vtysh -f {config_path}')

def perfTest(lossy=True):
    "Create network and run simple performance test"
    topo = SpineLeafTopo(bw=10, delay='5ms', loss=10 if lossy else 0, lossy=lossy)
    net = Mininet(topo=topo,
                  host=CPULimitedHost, link=TCLink,
                  autoStaticArp=True)
    net.start()
    info("Dumping host connections\n")
    dumpNodeConnections(net.hosts)

    # startFRR(net)
    # configureFRR(net)

    info("Testing network connectivity\n")
    # net.pingAll()
    h1, h2 = net.getNodeByName('h1', 'h2')
    net.ping([h1, h2])
    # h1.cmd('ping -c 1 %s' % h2.IP())

    info("Check ifconfig on all routers\n")
    # for router in net.hosts:
    #     if 'spine' in router.name or 'leaf' in router.name:
    #         print(router.name)
    #         print(router.cmd('ifconfig'))

    # info("Testing bandwidth between h1 and h4 (lossy=%s)\n" % lossy)
    # h1, h4 = net.getNodeByName('h1', 'h4')
    # net.iperf((h1, h4), l4Type='UDP')
    # # Debugging
    # h1.cmd('jobs')
    # h4.cmd('jobs')

    # Cli xterm

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
