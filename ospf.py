import click
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.cli import CLI
import time
import os
# iperf
# 简历ospf时间

hostname = os.uname().nodename
prefix_dir = f"/home/{hostname}/mininet-test/DataCenterTopo/"
# target_dir = "/etc/frr/"
# lib_dir = "/usr/lib/frr/"

target_dir = "/usr/local/etc/"
lib_dir = ""

def generate_zebra_conf(i, j):
    return f"""
hostname node{i:x}{j:x}
password en
enable password en


"""

def generate_ospfd_conf(i, j, get_rank):
    return f"""
!
hostname ospf{i:x}{j:x}
password frr
enable password frr


router ospf
 ospf router-id 1.1.{i}.{j}
 network 10.{get_rank(i,j)}.{0}.0/24 area 0
 network 10.{get_rank(i,j)}.{1}.0/24 area 0
 network 10.{get_rank(i+1,j)}.{0}.0/24 area 0
 network 10.{get_rank(i,j+1)}.{1}.0/24 area 0
debug ospf event
log stdout
"""


class LinuxRouter(Node):
    "A Node with IP forwarding enabled."

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        # Enable forwarding on the router
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super( LinuxRouter, self ).terminate()

def create_node(topo, i, j):
    node_name = f"node{i:x}{j:x}"
    node = topo.addNode(
        node_name,
        cls=LinuxRouter,
        ip=f"10.{i}.{j}.1/24",
    )


    # node.cmdPrint(f"vtysh -f {conf_file}")

    # Enable IP forwarding
    # node.cmdPrint('echo "net.ipv4.ip_forward = 1" | tee -a /etc/sysctl.conf')
    # node.cmdPrint('sysctl -p /etc/sysctl.conf')

    return node

class NetworkTopo(Topo):

    def build(self, **_opts):
        row = 3
        col = 3
        def get_rank(i, j):
            return (i - 1) * col + j

        nodes = {}

        for i in range(1, row + 1):
            for j in range(1, col + 1):
                file_name = f"{prefix_dir}/ospfv3_conf/ospfd_{i:x}{j:x}.conf"
                with open(file_name, 'w') as file:
                    file.write(generate_ospfd_conf(i, j, get_rank))
                file_name = f"{prefix_dir}/ospfv3_conf/zebra_{i:x}{j:x}.conf"
                with open(file_name, 'w') as file:
                    file.write(generate_zebra_conf(i, j))

                nodes[(i, j)] = self.addNode(f"node{i:x}{j:x}", cls=LinuxRouter, ip=f"10.{get_rank(i, j)}.0.1/24")
                # nodes[(i, j)] = create_node(self, i, j)

        '''
        Link rules:
            eth0            eth0
        eth1    eth2 ---- eth1  eth2
            eth3            eth3
             |
             |
            eth0

        IP rules: (3*3 matrix)
        node_11-eth3 -- node_21-eth0:  10.{4}.{0}.2/24 -- 10.{4}.{0}.1/24
        '''

        for i in range(1, row + 1):
            for j in range(1, col + 1):
                if j < col:
                    self.addLink(nodes[(i, j)], nodes[(i, j + 1)], intfName1=f'node{i:x}{j:x}-eth2',
                                intfName2=f'node{i:x}{j + 1:x}-eth1')
                if i < row:
                    self.addLink(nodes[(i, j)], nodes[(i + 1, j)], intfName1=f'node{i:x}{j:x}-eth3',
                                intfName2=f'node{i + 1:x}{j:x}-eth0')

# @click.command()
# @click.option('--row', default=3, help='Number of rows')
# @click.option('--col', default=3, help='Number of columns')
def matrix_net(row, col):
    def get_rank(i, j):
        return (i - 1) * col + j
    topo = NetworkTopo()
    net = Mininet(controller=None, topo=topo)
    for i in range(1, row + 1):
        for j in range(1, col + 1):
            node = net.getNodeByName(f"node{i:x}{j:x}")
            if j < col:
                if i > 1:
                    node.cmdPrint(
                        f"ip addr add 10.{get_rank(i, j)}.{0}.1/24 dev node{i:x}{j:x}-eth0")
                node.cmdPrint(
                    f"ip addr add 10.{get_rank(i, j + 1)}.{1}.2/24 dev node{i:x}{j:x}-eth2")
            if i < row:
                if j > 1:
                    node.cmdPrint(
                        f"ip addr add 10.{get_rank(i, j)}.{1}.1/24 dev node{i:x}{j:x}-eth1")
                node.cmdPrint(
                    f"ip addr add 10.{get_rank(i + 1, j)}.{0}.2/24 dev node{i:x}{j:x}-eth3")
    for i in range(1, row + 1):
        for j in range(1, col + 1):
            node = net.getNodeByName(f"node{i:x}{j:x}")
            node.cmd(f"mkdir -p {prefix_dir}/ospfv3_conf/")
            conf_file = f"{prefix_dir}/ospfv3_conf/ospfd_{i:x}{j:x}.conf"
            zebra_conf = f"{prefix_dir}/ospfv3_conf/zebra_{i:x}{j:x}.conf"
            node.cmd(f"cp {conf_file} {target_dir}ospfd_{i:x}{j:x}.conf")
            node.cmd(f"cp {zebra_conf} {target_dir}zebra_{i:x}{j:x}.conf")
            node.cmdPrint(
                f"{lib_dir}zebra -f {target_dir}zebra_{i:x}{j:x}.conf -d -z /tmp/{node.name}.api -i /tmp/zebra-{node.name}.pid > {prefix_dir}ospfv3_conf/logs/{node.name}-zebra-stdout 2>&1")
            time.sleep(1)
    for i in range(1, row + 1):
        for j in range(1, col + 1):
            node = net.getNodeByName(f"node{i:x}{j:x}")
            node.cmdPrint(
                f"{lib_dir}ospfd -f {target_dir}ospfd_{i:x}{j:x}.conf -d -z /tmp/{node.name}.api -i /tmp/ospfd-{node.name}.pid >  {prefix_dir}ospfv3_conf/logs/{node.name}-ospfd-stdout 2>&1")


    net.start()
    CLI(net)
    net.stop()
    os.system('rm -f /tmp/ospfd-node* /tmp/node*.api  /tmp/zebra-node*')
    os.system("killall -9 ospfd zebra")

if __name__ == '__main__':
    matrix_net(row=3, col=3)
