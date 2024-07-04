import os
import threading
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
 network {router_id}/24
 
"""
    for neighbor in neighbors:
        # config += f" neighbor {neighbor['ip']} interface remote-as external\n"
        config += f" neighbor {neighbor['ip']} remote-as {neighbor['as']}\n"
        config += f" neighbor {neighbor['ip']} ebgp-multihop 255\n neighbor {neighbor['ip']} advertisement-interval 10\n"
    config += f"""
log file /tmp/{name}.log
"""
    return config

def configureBGP(net, n_leaf=2, n_spine=2, m_hosts=2, host_links=2):
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
                # for h in range(m_hosts*host_links):
                #     neighbors.append({'name': f'h{m_hosts*(leaf_id-1)+h+1}-eth0',
                #                       'ip': f'192.168.{n_leaf*n_spine + (leaf_id-1)*m_hosts + h+1}.1', 'as':'64000+h+1'})

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
                f"{lib_dir}zebra -d -f {target_dir}zebra_{router.name}.conf -z /tmp/{router.name}.api -i /tmp/zebra-{router.name}.pid > {prefix_dir}/logs/{router.name}-zebra-stdout 2>&1")
    time.sleep(1)
    for router in net.hosts:
        if 'spine' in router.name or 'leaf' in router.name:
            router.cmdPrint(
                f"{lib_dir}bgpd -d -f {target_dir}bgp_{router.name}.conf -z /tmp/{router.name}.api -i /tmp/bgpd-{router.name}.pid > {prefix_dir}/logs/{router.name}-bgpd-stdout 2>&1")


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
    def build(self, n_spine=2, n_leaf=4, m_hosts=4, host_links=2, bw=10, delay='5ms', loss=0, lossy=True):
        spine_switches = []

        # Create spine switches
        for i in range(n_spine):
            spine_switch = self.addNode('spine%s' % (i + 1), cls=LinuxRouter, ip='192.168.{}.1/24'.format(i*n_leaf+1), asnum=65000 + i)
            spine_switches.append(spine_switch)

        leaf_switches = {}
        # Create leaf switches
        for i in range(n_leaf):
            leaf_switch = self.addNode('leaf%s' % (i + 1), cls=LinuxRouter, ip='192.168.{}.2/24'.format(i + 1), asnum=65000 + n_spine + i)
            # Create hosts and connect them to leaf switches
            # fully connect between leaf and spine
            for k in range(n_spine):
                self.addLink(leaf_switch, spine_switches[k],
                                intfName1 = '{}-eth{}'.format(leaf_switch, k), params1 = {'ip': '192.168.{}.2/24'.format(k*n_leaf+i+1)},
                                intfName2 = '{}-eth{}'.format(spine_switches[k], i), params2 = {'ip': '192.168.{}.1/24'.format(k*n_leaf+i+1)}
                             ) #, bw=bw, delay=delay, loss=loss) #, use_htb=True)
            leaf_switches[i+1] = leaf_switch

        for j in range(m_hosts):
            host = self.addHost(f'h{j+1}',
                                ip=f'192.168.{n_leaf*n_spine + j*host_links+1}.1/24',
                                asnum=64000 + j + 1,
                                defaultRoute=f'via 192.168.{n_leaf*n_spine + j*host_links+1}.2')
            leaf_switch1 = leaf_switches[(j)%n_leaf+1]
            leaf_switch2 = leaf_switches[(j+1)%n_leaf+1]
            self.addLink(host, leaf_switch1,
                         intfName1 = '{}-eth0'.format(host), params1 = {'ip': f'192.168.{n_leaf*n_spine + j*host_links+1}.1/24'},
                         # intfName2='{}-eth{}'.format(leaf_switch, j),
                         params2={'ip': f'192.168.{n_leaf*n_spine + j*host_links+1}.2/24'}
                         )  # , bw=bw, delay=delay, loss=loss if lossy else 0) #, use_htb=True)
            self.addLink(host, leaf_switch2,
                        intfName1='{}-eth1'.format(host), params1={'ip': f'192.168.{n_leaf*n_spine + j*host_links+2}.1/24'},
                        # intfName2='{}-eth{}'.format(leaf_switch, j),
                        params2={'ip': f'192.168.{n_leaf*n_spine + j*host_links+2}.2/24'}
                        )


def iperfTest(net):
    "Run iperf between h1 and h2"
    h1, h2 = net.get('leaf1', 'leaf4')
    print("Starting iperf server...")
    h1.cmd('iperf -s &')
    print("Starting iperf client...")
    iperf_output = h2.cmd('iperf -c', h1.IP())
    print(iperf_output)

def log_spine_routes(node,name):
    # len = -1
    last_content = ""
    while True:
        content = node.cmd("route -n\n")
        # len = content.count("255.255.255.0")
        write = content
        if content != last_content:
            with open(f"{prefix_dir}{name}_routes.log", "a") as log_file:
                log_file.write(f"{time.time()} \n {write}\n")
        else:
            with open(f"{prefix_dir}{name}_routes.log", "a") as log_file:
                log_file.write(f"{time.time()} \n\n")
        last_content = content


        time.sleep(1)

def run(lossy=True):
    n_spine = 2
    n_leaf = 4
    m_hosts = 4
    host_links = 2
    "Create network and run simple performance test"
    """
    n_leaf: number of leaf switches
    m_hosts: number of hosts per leaf
    n_spine: number of spine switches
    host_links: a host links to how many leaf switches
    """
    topo = SpineLeafTopo(n_leaf=n_leaf, m_hosts=m_hosts,host_links=host_links, n_spine=n_spine, bw=10, delay='5ms', loss=10 if lossy else 0, lossy=lossy)
    net = Mininet(topo=topo, controller=None)
    info("Dumping host connections\n")
    dumpNodeConnections(net.hosts)
    for node in net.hosts:
        if 'h' in node.name:
            node.setDefaultRoute(f'via 192.168.{n_leaf*n_spine + (int(node.name[1:])-1)*host_links+1}.2')
            print(f"Node: {node.name} default route: {f'via 192.168.{n_leaf*n_spine + (int(node.name[1:])-1)*host_links+1}.2'}")
        print(f"Node: {node.name}")
        for intf in node.intfList():
            print(f"  Interface: {intf.name}, IP: {intf.IP()}")

    configureBGP(net, n_leaf=n_leaf, n_spine=n_spine, m_hosts=m_hosts, host_links=host_links)
    net.start()
    # 开一个线程，每1秒log spine1 的路由
    spine1 = net.getNodeByName('spine2')
    # spine2 = net.getNodeByName('spine2')
    # leaf1 = net.getNodeByName('leaf1')
    # leaf2 = net.getNodeByName('leaf2')
    # leaf3 = net.getNodeByName('leaf3')
    # leaf4 = net.getNodeByName('leaf4')

    # 创建并启动日志线程
    log_thread1 = threading.Thread(target=log_spine_routes, args=(spine1,'spine2'))
    # log_thread2 = threading.Thread(target=log_spine_routes, args=(spine2,'spine2'))
    # log_thread3 = threading.Thread(target=log_spine_routes, args=(leaf1, 'leaf1'))
    # log_thread4 = threading.Thread(target=log_spine_routes, args=(leaf2, 'leaf2'))
    # log_thread5 = threading.Thread(target=log_spine_routes, args=(leaf3, 'leaf3'))
    # log_thread6 = threading.Thread(target=log_spine_routes, args=(leaf4, 'leaf4'))

    log_thread1.daemon = True  # 设置为守护线程，这样在主程序退出时该线程也会退出
    # log_thread2.daemon = True  # 设置为守护线程，这样在主程序退出时该线程也会退出
    # log_thread3.daemon = True  # 设置为守护线程，这样在主程序退出时该线程也会退出
    # log_thread4.daemon = True  # 设置为守护线程，这样在主程序退出时该线程也会退出
    # log_thread5.daemon = True  # 设置为守护线程，这样在主程序退出时该线程也会退出
    # log_thread6.daemon = True  # 设置为守护线程，这样在主程序退出时该线程也会退出
    log_thread1.start()
    # log_thread2.start()
    # log_thread3.start()
    # log_thread4.start()
    # log_thread5.start()
    # log_thread6.start()


    CLI(net)

    net.stop()
    os.system(f'rm -f /tmp/bgpd* /tmp/*.api  /tmp/zebra* /tmp/*.log {prefix_dir}logs/*')
    os.system("killall -9 bgpd zebra")


if __name__ == '__main__':
    setLogLevel('info')
    run(lossy=False)