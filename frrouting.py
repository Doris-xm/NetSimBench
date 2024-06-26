import os


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

def configureFRR(net, n_leaf=2, n_spine=2, m_hosts=2):
    """Configure FRRouting on all routers."""
    os.makedirs('frr_configs', exist_ok=True)
    for link in net.links:
        print(link.intf1.node.name, link.intf2.node.name)
        for router in link.intf1.node, link.intf2.node:
            if 'spine' in router.name or 'leaf' in router.name:
                router_name = router.name
                router_id = int(router_name[-1])
                neighbors = []
                if 'spine' in router_name:
                    # Spine routers connect to leaf routers
                    for leaf_id in range(1, n_leaf + 1):
                        neighbors.append({'ip': f'10.0.{leaf_id}.1', 'as': 200 + leaf_id})
                elif 'leaf' in router_name:
                    # Leaf routers connect to spine routers
                    for spine_id in range(1, n_spine + 1):
                        neighbors.append({'ip': f'10.0.{router_id}.{spine_id}', 'as': 100 + spine_id})

                config = generateFRRConfig(router_name, 100 + router_id, neighbors)
                config_path = f'./frr_configs/{router_name}.conf'
                with open(config_path, 'w') as f:
                    f.write(config)
                router.cmd(f'vtysh -f {config_path}')