# README

```text
.
├── README.md
├── ospf_conf/      # ospf配置文件
├── idc_conf/       # bgp配置文件
├── ospf.py         # ospf测试脚本,矩阵拓扑
├── idc_bgp.py          # bgp测试脚本,spine-leaf拓扑
├── docker_iperf_test.py  # iperf测试脚本(docker)
```

Python编写的Mininet测试脚本，使用路由协议ospf、bgp。

### 0. mininet部署、运行
通过github仓库的安装脚本安装：http://github.com/mininet/mininet.git

### 1. OSPF路由协议
#### 1.1 OSPF协议（Open Shortest Path First）
采用Dijkstra最短路径算法；
采用分布式的链路状态协议（link state protocol）

1. 洪泛法：向该AS中所有路由发送信息
2. 交换的信息：相邻的链路状态（不发送整张路由表）
3. 链路状态改变时，用洪泛法向所有router发送信息

Link-state database：
1. 这个数据库是全网的拓扑结构图，在全网范围内一致（链路状态数据库的同步）
2. 较快地进行更新，收敛快


OSPF划分区域：
1.  洪泛法交换信息时，范围是一个区域，而非整个AS，减少整个网络的通信量
2. **一个区域内部的router只知道该区域的完整网络拓扑，不知道其他区域的网络拓扑**
3. 使用**层次结构的区域划分**， 在上层区域的叫backbone area（主干区域0.0.0.0），作用是联通下层区域

#### 1.2 OSPF无线自组网络
搭建矩形拓扑，所有路由放在backbone area中，实现ospf协议的路由。
```text
node11---node12---node13
  |       |       |
node21---node22---node23
  |       |       |
node31---node32---node33
```
Quagga ospfd守护进程默认hello interval = 10s, dead interval = 40s。

根据ospfd日志文件，测量得到：
- 从ospfd启动到邻居建立连接，时间为50s
- 打断node11---node12，重连时间为4s


### 2. BGP路由协议
#### 2.1 BGP协议（Border Gateway Protocol）
外部网关协议：解决AS之间的路由选择
思路：AS之间交换”可达性“信息
条件：AS之间的路由选择必须考虑有关策略

BGP只是寻找一条能够到达的且比较好的（不会兜圈子），并非要寻找一条最佳路由

**BGP发言人**：
- AS中至少一个router为BGP speaker
- 一般来说，两个BGP speaker通过一个共享网络连接。一般speaker就是BGP边界路由器（也可以不是）

路由信息交换（一个speaker和另一个speaker之间）
- 先建立TCP连接（提供可靠服务）
- 交换BGP报文，建立BGP会话session
- 交换路由信息
- 使用TCP连接交换路由信息的两个speaker，彼此成为neighbor或者peer（对等）


#### 2.2 BGP IDC数据中心网络
搭建Spine-Leaf拓扑，每个路由划分为一个AS，实现BGP协议的路由。
- spine层：2个路由
- leaf层：4个路由（与spine层路由全连接）
- host层：4个host，每个host连接两个leaf路由

在advertisement-interval=10s的情况下，测量得到：
- 收敛时长：15s
