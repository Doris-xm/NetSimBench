import subprocess
import re

def get_docker_containers():
    # 获取所有docker容器ID和名称
    result = subprocess.run(['docker', 'ps', '--format', '{{.ID}} {{.Names}}'], capture_output=True, text=True)
    containers = result.stdout.strip().split('\n')
    return [line.split() for line in containers if 'node_1_' in line]

def get_ipv6_address(container_name):
    # 使用 `ip a` 命令获取指定容器的IPv6地址
    result = subprocess.run(['docker', 'exec', container_name, 'ip', 'a'], capture_output=True, text=True)
    output = result.stdout
    # 提取IPv6地址
    for line in output.split('\n'):
        if 'inet6' in line and 'scope global' in line:
            ipv6_address = line.strip().split()[1].split('/')[0]
            return ipv6_address
    return None

def run_iperf_server(container_name):
    # 在指定容器中启动iperf服务
    subprocess.run(['docker', 'exec', '-d', container_name, 'iperf', '-s', '-V'])

def run_iperf_client(container_name, target_ip):
    # 在指定容器中运行iperf客户端测试
    result = subprocess.run(['docker', 'exec', container_name, 'iperf', '-V', '-c', target_ip], capture_output=True, text=True)
    return result.stdout

def main():
    containers = get_docker_containers()
    node_1_1_ip = None
    container_ips = {}

    # 获取所有容器的IPv6地址
    for container_id, container_name in containers:
        ip = get_ipv6_address(container_id)
        if container_name == 'mini-dtn-node_1_1':
            node_1_1_ip = ip
        container_ips[container_name] = ip
    print(container_ips)
    # 启动iperf服务器
    for container_name, ip in container_ips.items():
        if container_name != 'mini-dtn-node_1_1':
            if container_name != 'mini-dtn-node_1_1':
                run_iperf_server(container_name)

            # 运行iperf客户端测试
        if node_1_1_ip:
            for container_name, ip in container_ips.items():
                if container_name != 'mini-dtn-node_1_1':
                    print(f"Testing from mini-dtn-node_1_1 to {container_name}")
                    output = run_iperf_client('mini-dtn-node_1_1', ip)
                    print(output)

        if __name__ == "__main__":
            main()