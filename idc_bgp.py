import os
import time
from mininet.cli import CLI
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel, info
from mininet.topo import Topo
from mininet.node import Node

""" For FRRouting configuration """
# target_dir = "/etc/frr/"
# lib_dir = "/usr/lib/frr/"

""" For Quagga configuration """
target_dir = "/usr/local/etc/"
lib_dir = ""

hostname = os.uname().nodename
prefix_dir = f"/home/{hostname}/mininet-test/DataCenterTopo/idc_conf/"
def generate_zebra_conf(name):
    return f"""
hostname {name}
password en
enable password en
"""

""" Config File for BGP """

def generateBgpConfig(name, asnum, router_id, neighbors, network):
    config = f"""
hostname {name}
password zebra
enable password zebra

router bgp {asnum}
 bgp router-id  {router_id}
 network {network}
"""
    for neighbor in neighbors:
        # config += f" neighbor {neighbor['ip']} interface remote-as external\n"
        config += f" neighbor {neighbor['ip']} remote-as {neighbor['as']}\n"
        config += f" neighbor {neighbor['ip']} timers 5 5\n"

    config += f"""
log file /tmp/{name}.log
"""
    return config

def configureBGP(net, n_leaf=2, n_spine=2, m_hosts=2):
    """Configure FRRouting on all routers."""
    all_spine = [{'name': router.name, 'ip': router.IP(), 'as': router.params['asnum']} for router in net.hosts if 'spine' in router.name]
    all_leaf = [{'name': router.name, 'ip': router.IP(), 'as': router.params['asnum']} for router in net.hosts if 'leaf' in router.name]
    for router in net.hosts:
        if 'spine' in router.name or 'leaf' in router.name:
            # Get Neighbors
            neighbors = []
            if 'spine' in router.name:
                # Spine routers connect to leaf routers
                spine_id = int(router.name[-1])
                for leaf in all_leaf:
                    leaf_id = int(leaf['name'][-1])
                    neighbors.append({'name': leaf['name']+'-eth{}'.format(leaf_id*m_hosts + spine_id - 1),
                                      'ip': f'192.168.{n_leaf*(spine_id-1) + leaf_id}.2', 'as': leaf['as']})
            elif 'leaf' in router.name:
                # Leaf routers connect to spine routers
                # specify eth interface
                leaf_id = int(router.name[-1])
                for spine in all_spine:
                    spine_id = int(spine['name'][-1])
                    neighbors.append({'name': spine['name']+'-eth{}'.format(leaf_id-1),
                                      'ip':  f'192.168.{n_leaf*(spine_id-1) + leaf_id}.1', 'as': spine['as']})
                for h in range(m_hosts):
                    neighbors.append({'name': f'h{m_hosts*(leaf_id-1)+h+1}-eth0',
                                      'ip': f'192.168.{n_leaf*n_spine + (leaf_id-1)*m_hosts + h+1}.2', 'as':f'{64000+m_hosts*(leaf_id-1)+h}'})

            # if 'spine' in router.name:
            #     network = '192.168.1.{}/32'.format(router.name[-1])
            # else:
            #     network = '192.168.1.{}/32'.format(int(router.name[-1]) + 32)

            bgp_conf = f"{prefix_dir}bgp_{router.name}.conf"
            zebra_conf = f"{prefix_dir}zebra_{router.name}.conf"

            router.cmd(f"mkdir -p {prefix_dir}")
            router.cmd(f"mkdir -p {prefix_dir}logs")
            with open(bgp_conf, 'w') as file:
                file.write(generateBgpConfig(router.name, router.params['asnum'], router.IP(), neighbors=neighbors, network='192.0.0.0/8'))
            with open(zebra_conf, 'w') as file:
                file.write(generate_zebra_conf(router.name))

            router.cmd(f"cp {bgp_conf} {target_dir}bgp_{router.name}.conf")
            router.cmd(f"cp {zebra_conf} {target_dir}zebra_{router.name}.conf")
            router.cmdPrint(
                f"{lib_dir}zebra -f {target_dir}zebra_{router.name}.conf -d -z /tmp/{router.name}.api -i /tmp/zebra-{router.name}.pid > {prefix_dir}/logs/{router.name}-zebra-stdout 2>&1")
    time.sleep(1)
    for router in net.hosts:
        if 'spine' in router.name or 'leaf' in router.name:
            router.cmdPrint(
                f"{lib_dir}bgpd -f {target_dir}bgp_{router.name}.conf -d -z /tmp/{router.name}.api -i /tmp/bgpd-{router.name}.pid > {prefix_dir}/logs/{router.name}-bgpd-stdout 2>&1")


class LinuxRouter(Node):
    "A Node with IP forwarding enabled."
    def config( self, **params ):
        super( LinuxRouter, self).config( **params )
        # Enable forwarding on the router
        self.cmd( 'sysctl net.ipv4.ip_forward=1' )


    def terminate( self ):
        self.cmd( 'sysctl net.ipv4.ip_forward=0' )

        self.cmd( "killall bgpd staticd zebra" )
        super( LinuxRouter, self ).terminate()


class SpineLeafTopo(Topo):
    """ Spine-Leaf topology with n leaf switches and m hosts per leaf, bw bandwidth """
    def build(self, n_spine=2, n_leaf=2, m_hosts=2, bw=10, delay='5ms', loss=0, lossy=True):
        spine_switches = []

        # Create spine switches
        for i in range(n_spine):
            spine_switch = self.addNode('spine%s' % (i + 1), cls=LinuxRouter, ip='192.168.{}.1/24'.format(i*n_leaf+1), asnum=65000 + i)
            spine_switches.append(spine_switch)

        # Create leaf switches
        for i in range(n_leaf):
            leaf_switch = self.addNode('leaf%s' % (i + 1), cls=LinuxRouter, ip='192.168.{}.1/24'.format(n_leaf*n_spine + i*m_hosts + 1), asnum=65000 + n_spine + i)
            # Create hosts and connect them to leaf switches
            for j in range(m_hosts):
                host = self.addHost('h%s' % (i * m_hosts + j + 1), ip='192.168.{}.2/24'.format(j+n_leaf*n_spine + i*m_hosts + 1), asnum=64000 + j + 1,
                                    defaultRoute='192.168.{}.1/24'.format(n_leaf*n_spine + i*m_hosts + 1)) #, cpu=.5 / (n_leaf * m_hosts))
                self.addLink(host, leaf_switch,
                                # intfName1 = '{}-eth0'.format(host), params1 = {'ip': '10.0.{}.1/24'.format(j+m_hosts*i)},
                                intfName2 = '{}-eth{}'.format(leaf_switch, j), params2 = {'ip': '192.168.{}.1/32'.format(j+n_leaf*n_spine + i*m_hosts + 1)}
                            ) #, bw=bw, delay=delay, loss=loss if lossy else 0) #, use_htb=True)

            # fully connect between leaf and spine
            for k in range(n_spine):
                self.addLink(leaf_switch, spine_switches[k],
                                intfName1 = '{}-eth{}'.format(leaf_switch, m_hosts + k), params1 = {'ip': '192.168.{}.2/32'.format(k*n_leaf+1)},
                                intfName2 = '{}-eth{}'.format(spine_switches[k], i), params2 = {'ip': '192.168.{}.1/32'.format(k*n_leaf+1)}
                             ) #, bw=bw, delay=delay, loss=loss) #, use_htb=True)



def perfTest(lossy=True):
    n_spine = 1
    n_leaf = 1
    m_hosts = 1
    "Create network and run simple performance test"
    topo = SpineLeafTopo(n_leaf=n_leaf, m_hosts=m_hosts, n_spine=n_spine, bw=10, delay='5ms', loss=10 if lossy else 0, lossy=lossy)
    net = Mininet(topo=topo, controller=None)
    info("Dumping host connections\n")
    dumpNodeConnections(net.hosts)
    for node in net.hosts:
        print(f"Node: {node.name}")
        for intf in node.intfList():
            print(f"  Interface: {intf.name}, IP: {intf.IP()}")

    configureBGP(net)
    net.start()
    CLI(net)
    net.stop()
    os.system('rm -f /tmp/bgpd* /tmp/*.api  /tmp/zebra*')
    os.system("killall -9 bgpd zebra")


if __name__ == '__main__':
    setLogLevel('info')
    perfTest(lossy=False)