import networkx as nx
import numpy as np
import itertools


class ConnectivityConstrainer:
    def __init__(self, max_parallel_paths, max_nodes, share_dag=False) -> None:
        self.max_parallel_paths = max_parallel_paths
        self.max_nodes = max_nodes
        self.complete_dag = []
        self.paths = []
        self.dag = None
        self.share_dag = share_dag

        complete_dag = nx.DiGraph()
        complete_dag.add_nodes_from([i for i in range(self.max_nodes)])
        add_edges_densly(complete_dag)

        self.paths = list(nx.all_simple_edge_paths(complete_dag, 0, max(complete_dag.nodes)))
        self.complete_dag = complete_dag

    def get_random_dag(self):
        if len(self.complete_dag) == 1:
            return self.complete_dag
        idx = np.random.choice(range(len(self.paths)), size=self.max_parallel_paths)
        subgraph = self.get_dag(idx)
        return subgraph

    def get_dag(self, path_indices):
        assert len(path_indices) == self.max_parallel_paths
        chosen_paths = []
        for i in path_indices:
            chosen_paths.extend(self.paths[i])

        chosen_paths = [tuple(e) for e in chosen_paths]
        subgraph = nx.edge_subgraph(self.complete_dag, chosen_paths).copy()
        if self.share_dag and self.dag:
            subgraph = self.dag
        self.dag = subgraph

        return subgraph

    def reset_dag(self):
        self.dag = None

    def get_paths(self):
        return self.paths

    def get_path(self, i):
        return self.paths[i]

    def enumerate_path_combinations(self):
        return itertools.combinations_with_replacement(range(len(self.paths)), self.max_parallel_paths)

    # def insert_subgraph(self, connectivity_graph):
    #     graph = nx.DiGraph()
    #     node_names = [str(s) for s in self.subgraph.nodes]
    #     for n in connectivity_graph.nodes:

    #         new_nodes = [str(n) + '_' + s for s in node_names]
    #         new_edges = [(str(n) + '_' + str(u), str(n) + '_' + str(u))for u, v in self.subgraph.edges]
    #         graph.add_nodes_from(new_nodes)
    #         graph.add_edges_from(new_edges)

    #         incoming = connectivity_graph.in_edges(n)

    #         for i, edge in enumerate(incoming):
    #             pre = str(edge[0]) + '_' + node_names[-1]
    #             graph.add_edge(pre, new_nodes[0])

    #             if len(incoming) > 1:
    #                 graph.add_edge(pre, str(edge[1]) + '_add')
    #     return graph


# borrowed from NASLib
def get_dense_edges(g):
    """
    Returns the edge indices (i, j) that would make a fully connected
    DAG without circles such that i < j and i != j. Assumes nodes are
    already created.
    Returns:
        list: list of edge indices.
    """
    edges = []
    nodes = sorted(list(g.nodes()))
    for i in nodes:
        for j in nodes:
            if i != j and j > i:
                edges.append((i, j))
    return edges


def add_edges_densly(g):
    """
    Adds edges to get a fully connected DAG without cycles
    """
    g.add_edges_from(get_dense_edges(g))


def get_node_coord(g, first_node=0):
    positions = {first_node: [0, 0]}
    prev = 0
    d = 0
    for e in nx.edge_dfs(g):
        x = e[1] if isinstance(e[1], int) else int(e[1].split('_')[0])
        if x < prev:
            d += 1
        # else:
        #     d = min(0, d-1)
        prev = x
        positions[e[1]] = [x, d]

    cur_x = 0
    ct = 0.2
    step = 0.2
    for key, pos in positions.items():
        if pos[0] == cur_x:
            pos[0] = cur_x + ct
            ct += step
        else:
            cur_x = pos[0]
            ct = step

    return positions
