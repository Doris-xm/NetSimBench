from mininet.topo import Topo

from frrouting import LinuxRouter

privateDirs = ['/etc/frr', '/var/run/frr']
class SpineLeafTopo(Topo):

    """ Spine-Leaf topology with n leaf switches and m hosts per leaf, bw bandwidth """
    def build(self, n_spine=2, n_leaf=2, m_hosts=2, bw=10, delay='5ms', loss=0, lossy=True):
        spine_switches = []

        # Create spine switches
        for i in range(n_spine):
            spine_switch = self.addNode('spine%s' % (i + 1), cls=LinuxRouter,
                                        privateDirs=privateDirs, asnum=65000 + i)
            spine_switches.append(spine_switch)

        # Create leaf switches
        for i in range(n_leaf):
            leaf_switch = self.addNode('leaf%s' % (i + 1), cls=LinuxRouter,
                                       privateDirs=privateDirs, asnum=65000 + n_spine + i)
            # Create hosts and connect them to leaf switches
            for j in range(m_hosts):
                host = self.addHost('h%s' % (i * m_hosts + j + 1)) #, cpu=.5 / (n_leaf * m_hosts))
                self.addLink(host, leaf_switch) #, bw=bw, delay=delay, loss=loss if lossy else 0) #, use_htb=True)
                # self.addLink(leaf_switch, host) #, bw=bw, delay=delay, loss=loss if lossy else 0) #, use_htb=True)

            # fully connect between leaf and spine
            for spine in spine_switches:
                self.addLink(leaf_switch, spine) #, bw=bw, delay=delay, loss=loss) #, use_htb=True)
                # self.addLink(spine, leaf_switch) #, bw=bw, delay=delay, loss=loss) #, use_htb=True)

