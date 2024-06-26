import os
from mininet.node import Node

""" Config File for FRRouting """

def generateFRRConfig(name, asnum, router_id, neighbors, network):
    config = f"""
frr defaults datacenter
!
hostname {name}
password zebra
!
router bgp {asnum}
 bgp router-id  {router_id}
 bgp bestpath as-path multipath-relax
 no bgp network import-check
"""
    for neighbor in neighbors:
        config += f" neighbor {neighbor['ip']} remote-as external\n"

    config += f"""
 address-family ipv4 unicast
  network {router_id}/32
  network {network}
 exit-address-family
!
line vty
!
end
"""
    return config


vtysh_conf = '''
service integrated-vtysh-config
'''

daemons = '''
bgpd=yes

vtysh_enable=yes
zebra_options="  -A 127.0.0.1 -s 90000000"
bgpd_options="   -A 127.0.0.1"
'''


def put_file(host, file_name, content, **kwargs):
    os.makedirs(host.name, exist_ok=True)
    file_dir = "./{}/{}".format(host.name, file_name.split("/")[-1])
    with open(file_dir, mode="w") as f:
        f.write(content.format(**kwargs))
    host.cmdPrint("cp {} {}".format(file_dir, file_name))

def configureFRR(net, n_leaf=2, n_spine=2, m_hosts=2):
    """Configure FRRouting on all routers."""
    all_spine = [{'ip': router.IP(), 'as': router.params['asnum']} for router in net.hosts if 'spine' in router.name]
    all_leaf = [{'ip': router.IP(), 'as': router.params['asnum']} for router in net.hosts if 'leaf' in router.name]
    all_hosts = [{'ip': router.IP(), 'as': 0} for router in net.hosts if 'h' in router.name]
    for router in net.hosts:
        # if 'spine' in self.name:
        #     network = '192.168.1.{}/32'.format(self.name[-1])
        # else:
        #     network = '192.168.1.{}/32'.format(self.name[-1] + 32)
        # put_file(self, "/etc/frr/daemons", daemons)
        # put_file(self, "/etc/frr/vtysh.conf", vtysh_conf)
        # frr_conf = generateFRRConfig(self.name, self.params['asnum'], self.IP(), neighbors=[{'ip': '
        # put_file(self, "/etc/frr/frr.conf", frr_conf, name=self.name,
        #          router_id=self.IP(), asnum=self.params['asnum'],
        #          network=network)
        #
        # self.cmd("/usr/lib/frr/frrinit.sh start")
        # self.cmd('ip address add {} dev {}-eth0'.format(network, self.name))
        if 'spine' in router.name or 'leaf' in router.name:
            # Get Neighbors
            neighbors = []
            if 'spine' in router.name:
                # Spine routers connect to leaf routers
                neighbors = all_leaf
            elif 'leaf' in router.name:
                # Leaf routers connect to spine routers
                neighbors = all_spine
                neighbors.extend(all_hosts)

            if 'spine' in router.name:
                network = '192.168.1.{}/32'.format(router.name[-1])
            else:
                network = '192.168.1.{}/32'.format(int(router.name[-1]) + 32)

            put_file(router, "/etc/frr/daemons", daemons)
            put_file(router, "/etc/frr/vtysh.conf", vtysh_conf)

            config = generateFRRConfig(router.name, router.params['asnum'], router.IP(), neighbors=neighbors, network=network)
            put_file(router, "/etc/frr/frr.conf", config)

            router.cmd("/usr/lib/frr/frrinit.sh start")
            router.cmd('ip address add {} dev {}-eth0'.format(network, router.name))


class LinuxRouter(Node):
    "A Node with IP forwarding enabled."
    def config( self, **params ):
        super( LinuxRouter, self).config( **params )

        # Enable forwarding on the router
        self.cmd( 'sysctl net.ipv4.ip_forward=1' )
        # Enable loose reverse path filtering
        self.cmd( 'sysctl net.ipv4.conf.all.rp_filter=2' )


    def terminate( self ):
        r = self.name
        self.cmd( 'sysctl net.ipv4.ip_forward=0' )
        self.cmd( 'sysctl net.ipv4.conf.all.rp_filter=0' )

        self.cmd( "killall bgpd staticd zebra" )
        super( LinuxRouter, self ).terminate()