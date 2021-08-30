import os
from dgl import data
from tvm.auto_scheduler import measure
from search_space import space
import numpy as np

from search_space.space import NetworkSpace, NetworkEntity

from tvm import relay
import tvm
import os
from features import graph_conversion
import csv
import pandas as pd

from pathlib import Path

wd = os.getcwd()  #'/home/moritz/Dokumente/Hiwi/code/nas/subgraph_generator/'
net_name = "test_net"
# data_name = net_name            # in case we want different data for the same net
data_name = "test_net_tuned_2000"

Path(wd + "/data/{}/graph_defs/".format(data_name)).mkdir(parents=True, exist_ok=True)
Path(wd + "/data/{}/logs/".format(data_name)).mkdir(parents=True, exist_ok=True)


cfg_space = NetworkSpace()
cfg_space.from_yaml(wd + "/configs/{}.yaml".format(net_name))
prop_file = wd + "/data/{}/graph_defs/graph_properties.csv".format(data_name)
print(prop_file)
if os.path.exists(prop_file):
    properties = pd.read_csv(prop_file)
    ids = list(properties["graph_id"])
else:
    ids = []
available = np.arange(np.prod(cfg_space.dims()) - 1, dtype=int)
available = [
    6,
    9,
    56,
    70,
    82,
    89,
    90,
    117,
    124,
    158,
    181,
    200,
    212,
    215,
    222,
    287,
    290,
    308,
    317,
    335,
    348,
    350,
    353,
    373,
    376,
    382,
    397,
    407,
    409,
    431,
    466,
    474,
    486,
    500,
    534,
    575,
    602,
    627,
    631,
    632,
    645,
    655,
    725,
    728,
    759,
    811,
    828,
    841,
    845,
    849,
    896,
    897,
    917,
    930,
    969,
    984,
    996,
    999,
    1004,
    1006,
    1020,
    1032,
    1050,
    1057,
    1078,
    1099,
    1112,
    1120,
    1127,
    1142,
    1147,
    1190,
    1205,
    1211,
    1246,
    1260,
    1266,
    1295,
    1298,
    1314,
    1323,
    1329,
    1339,
    1342,
    1389,
    1392,
    1396,
    1419,
    1421,
    1438,
    1466,
    1479,
    1513,
    1533,
    1546,
    1574,
    1587,
    1601,
    1607,
    1648,
    1653,
    1655,
    1659,
    1687,
    1718,
    1743,
    1756,
    1778,
    1784,
    1792,
    1835,
    1839,
    1842,
    1847,
    1848,
    1855,
    1862,
    1863,
    1884,
    1924,
    1956,
    1980,
    2024,
    2049,
    2059,
    2062,
    2097,
    2101,
    2112,
    2116,
    2121,
    2131,
    2168,
    2195,
    2208,
    2215,
    2233,
    2234,
    2289,
    2323,
    2328,
    2359,
    2371,
    2393,
    2402,
    2439,
    2461,
    2498,
    2532,
    2549,
    2617,
    2634,
    2666,
    2669,
    2683,
    2686,
    2706,
    2721,
    2724,
    2754,
    2763,
    2780,
    2804,
    2822,
    2826,
    2834,
    2838,
    2851,
    2852,
    2872,
    2874,
    2913,
    2916,
    2931,
    2937,
    2943,
    2953,
    2954,
    2957,
    2973,
    2974,
    2983,
    2987,
    2995,
    3043,
    3047,
    3052,
    3084,
    3103,
    3112,
    3116,
    3131,
    3138,
    3139,
    3152,
    3166,
    3174,
    3177,
    3191,
    3192,
    3207,
    3223,
    3251,
    3252,
    3263,
    3282,
    3285,
    3292,
    3298,
    3308,
    3318,
    3320,
    3325,
    3332,
    3336,
    3339,
    3346,
    3367,
    3369,
    3380,
    3385,
    3389,
    3398,
    3411,
    3414,
    3434,
    3441,
    3450,
    3466,
    3472,
    3476,
    3477,
    3490,
    3515,
    3532,
    3535,
    3538,
    3576,
    3597,
    3601,
    3604,
    3644,
    3663,
    3669,
    3674,
    3682,
    3717,
    3730,
    3749,
    3751,
    3767,
    3775,
    3776,
    3781,
    3791,
    3820,
    3826,
    3883,
    3886,
    3889,
    3912,
    3926,
    3932,
    3943,
    3985,
    3991,
    3992,
    4032,
    4064,
    4073,
    4077,
    4079,
    4080,
    4103,
    4115,
    4125,
    4149,
    4181,
    4206,
    4222,
    4231,
    4243,
    4261,
    4285,
    4313,
    4314,
    4316,
    4334,
    4335,
    4348,
    4351,
    4391,
    4402,
    4423,
    4429,
    4481,
    4482,
    4490,
    4520,
    4540,
    4562,
    4565,
    4572,
    4605,
    4625,
    4627,
    4672,
    4673,
    4725,
    4733,
    4735,
    4736,
    4754,
    4762,
    4764,
    4778,
    4801,
    4822,
    4830,
    4874,
    4885,
    4914,
    4933,
    4948,
    4949,
    4950,
    4954,
    4963,
    4985,
    5039,
    5044,
    5052,
    5072,
    5096,
    5097,
    5117,
    5121,
    5155,
    5156,
    5173,
    5182,
    5186,
    5198,
    5202,
    5207,
    5228,
    5239,
    5255,
    5279,
    5288,
    5291,
    5292,
    5300,
    5304,
    5307,
    5309,
    5327,
    5342,
    5350,
    5355,
    5385,
    5415,
    5466,
    5467,
    5479,
    5506,
    5509,
    5522,
    5549,
    5569,
    5587,
    5612,
    5617,
    5619,
    5647,
    5664,
    5687,
    5688,
    5713,
    5737,
    5746,
    5747,
    5751,
    5770,
    5772,
    5776,
    5779,
    5796,
    5821,
    5840,
    5843,
    5855,
    5858,
    5904,
    5909,
    5910,
    5947,
    5950,
    6009,
    6020,
    6029,
    6046,
    6053,
    6067,
    6092,
    6098,
    6114,
    6118,
    6127,
    6141,
    6148,
    6167,
    6183,
    6202,
    6228,
    6258,
    6261,
    6311,
    6315,
    6318,
    6346,
    6362,
    6373,
    6376,
    6386,
    6387,
    6390,
    6404,
    6440,
    6492,
    6515,
    6576,
    6586,
    6588,
    6618,
    6621,
    6633,
    6635,
    6653,
    6665,
    6666,
    6671,
    6689,
    6710,
    6713,
    6725,
    6728,
    6729,
    6764,
    6771,
    6773,
    6780,
    6784,
    6791,
    6800,
    6832,
    6851,
    6905,
    6920,
    6938,
    6950,
    6953,
    6976,
    6978,
    6991,
    7027,
    7030,
    7033,
    7066,
    7074,
    7087,
    7097,
    7123,
    7155,
    7165,
    7185,
    7187,
    7196,
    7212,
    7231,
    7296,
    7300,
    7310,
    7318,
    7371,
    7391,
    7397,
    7398,
    7404,
    7440,
    7446,
    7447,
    7469,
    7482,
    7515,
    7551,
    7567,
    7586,
    7605,
    7610,
    7626,
    7632,
    7637,
    7638,
    7667,
    7674,
    7720,
    7730,
    7743,
    7753,
    7804,
    7810,
    7811,
    7865,
    7866,
    7869,
    7893,
    7919,
    7931,
    7935,
    7963,
    7976,
    7979,
    7985,
    8039,
    8046,
    8052,
    8078,
    8089,
    8106,
    8119,
    8144,
    8153,
    8160,
    8162,
    8163,
    8185,
    8188,
    8198,
    8202,
    8216,
    8239,
    8243,
    8277,
    8291,
    8298,
    8341,
    8359,
    8367,
    8369,
    8386,
    8432,
    8433,
    8449,
    8451,
    8452,
    8468,
    8479,
    8490,
    8499,
    8507,
    8554,
    8578,
    8593,
    8660,
    8668,
    8669,
    8684,
    8738,
    8768,
    8774,
    8775,
    8787,
    8819,
    8830,
    8866,
    8896,
    8903,
    8921,
    8928,
    8947,
    8957,
    8962,
    9008,
    9012,
    9035,
    9063,
    9069,
    9075,
    9076,
    9087,
    9088,
    9121,
    9131,
    9132,
    9140,
    9151,
    9162,
    9173,
    9210,
    9211,
    9225,
    9232,
    9258,
    9299,
    9325,
    9327,
    9345,
    9380,
    9393,
    9437,
    9471,
    9514,
    9523,
    9557,
    9560,
    9566,
    9570,
    9631,
    9634,
    9647,
    9659,
    9678,
    9708,
    9733,
    9743,
    9766,
    9797,
    9801,
    9802,
    9825,
    9829,
    9859,
    9862,
    9872,
    9901,
    9904,
    9908,
    9916,
    9925,
    9929,
    9950,
    9997,
    10019,
    10028,
    10030,
    10036,
    10048,
    10072,
    10083,
    10103,
    10108,
    10141,
    10150,
    10173,
    10189,
    10197,
    10219,
    10239,
    10282,
    10285,
    10295,
    10302,
    10326,
    10327,
    10328,
    10329,
    10368,
    10389,
    10395,
    10405,
    10407,
    10417,
    10483,
    10522,
    10526,
    10534,
    10568,
    10604,
    10624,
    10634,
    10648,
    10652,
    10678,
    10742,
    10743,
    10767,
    10780,
    10804,
    10870,
    10878,
    10883,
    10895,
    10931,
    10937,
    10951,
    10979,
    10983,
    11013,
    11020,
    11023,
    11032,
    11075,
    11076,
    11083,
    11137,
    11148,
    11163,
    11192,
    11202,
    11208,
    11218,
    11243,
    11257,
    11294,
    11329,
    11364,
    11369,
    11370,
    11376,
    11379,
    11384,
    11401,
    11414,
    11452,
    11458,
    11517,
    11529,
    11551,
    11557,
    11567,
    11575,
    11583,
    11605,
    11620,
    11649,
    11659,
    11667,
    11670,
    11682,
    11684,
    11689,
    11694,
    11737,
    11742,
    11789,
    11793,
    11811,
    11830,
    11836,
    11842,
    11843,
    11867,
    11870,
    11876,
    11890,
    11905,
    11925,
    11926,
    12016,
    12079,
    12099,
    12103,
    12108,
    12119,
    12148,
    12184,
    12195,
    12201,
    12204,
    12225,
    12246,
    12247,
    12268,
    12283,
    12290,
    12342,
    12358,
    12365,
    12400,
    12402,
    12408,
    12422,
    12423,
    12494,
    12497,
    12546,
    12621,
    12622,
    12636,
    12661,
    12675,
    12692,
    12696,
    12731,
    12737,
    12739,
    12808,
    12820,
    12831,
    12848,
    12854,
    12866,
    12871,
    12887,
    12889,
    12903,
    12914,
    12924,
    12932,
    12952,
    12955,
    12959,
    12961,
    12966,
    12994,
    12997,
    13001,
    13016,
    13019,
    13020,
    13029,
    13061,
    13072,
    13096,
    13099,
    13113,
    13115,
    13133,
    13139,
    13147,
    13156,
    13180,
    13197,
    13200,
    13231,
    13251,
    13256,
    13257,
    13282,
    13314,
    13318,
    13325,
    13339,
    13343,
    13370,
    13374,
    13449,
    13453,
    13468,
    13520,
    13530,
    13531,
    13534,
    13557,
    13566,
    13572,
    13573,
    13609,
    13627,
    13634,
    13660,
    13690,
    13700,
    13710,
    13733,
    13757,
    13773,
    13801,
    13809,
    13836,
    13846,
    13851,
    13881,
    13915,
    13925,
    13928,
    13943,
    13946,
    13951,
    13994,
    14045,
    14058,
    14097,
    14117,
    14136,
    14154,
    14160,
    14180,
    14226,
    14256,
    14266,
    14280,
    14358,
    14385,
    14398,
    14433,
    14455,
    14469,
    14476,
    14513,
    14519,
    14524,
    14554,
    14563,
    14577,
    14599,
    14606,
    14607,
    14611,
    14612,
    14622,
    14631,
    14645,
    14666,
    14676,
    14685,
    14690,
    14703,
    14708,
    14725,
    14731,
    14737,
    14743,
    14767,
    14783,
    14797,
    14798,
    14852,
    14918,
    14946,
    14960,
    14961,
    14974,
    14977,
    14987,
    14997,
    15018,
    15034,
    15052,
    15053,
    15057,
    15058,
    15060,
    15069,
    15071,
    15094,
    15103,
    15117,
    15135,
    15142,
    15162,
    15168,
    15177,
    15189,
    15194,
    15201,
    15244,
    15247,
    15268,
    15299,
    15304,
    15309,
    15311,
    15316,
    15328,
    15333,
    15349,
    15351,
    15356,
    15362,
    15385,
    15407,
    15464,
    15470,
    15508,
    15532,
    15540,
    15580,
    15588,
    15610,
    15620,
    15630,
    15688,
    15696,
    15714,
    15715,
    15739,
    15767,
    15782,
    15804,
    15807,
    15809,
    15819,
    15824,
    15826,
    15896,
    15904,
    15910,
    15948,
    15951,
    15957,
    15991,
    15995,
    16007,
    16036,
    16040,
    16052,
    16056,
    16062,
    16067,
    16075,
    16128,
    16135,
    16177,
    16185,
    16216,
    16219,
    16224,
    16230,
    16233,
    16254,
    16259,
    16267,
    16289,
    16291,
    16315,
    16319,
    16363,
    16367,
    16378,
    16383,
    16393,
    16410,
    16412,
    16450,
    16508,
    16518,
    16532,
    16543,
    16545,
    16546,
    16564,
    16570,
    16584,
    16596,
    16625,
    16637,
    16650,
    16659,
    16660,
    16676,
    16699,
    16728,
    16769,
    16802,
    16814,
    16817,
    16830,
    16852,
    16892,
    16894,
    16914,
    16923,
    16961,
    16981,
    16995,
    17052,
    17077,
    17097,
    17109,
    17141,
    17143,
    17180,
    17186,
    17207,
    17210,
    17218,
    17236,
    17252,
    17265,
    17271,
    17276,
    17290,
    17313,
    17316,
    17334,
    17347,
    17378,
    17404,
    17414,
    17420,
    17461,
    17485,
    17507,
    17572,
    17583,
    17592,
    17613,
    17633,
    17645,
    17647,
    17666,
    17697,
    17744,
    17764,
    17777,
    17790,
    17801,
    17806,
    17809,
    17827,
    17834,
    17835,
    17842,
    17858,
    17871,
    17887,
    17897,
    17901,
    17902,
    17905,
    17911,
    17916,
    17919,
    17921,
    17935,
    17943,
    17961,
    17975,
    18075,
    18082,
    18099,
    18130,
    18194,
    18200,
    18207,
    18237,
    18255,
    18262,
    18278,
    18279,
    18299,
    18310,
    18329,
    18338,
    18352,
    18358,
    18388,
    18396,
    18398,
    18416,
    18418,
    18437,
    18455,
    18459,
    18477,
    18478,
    18503,
    18518,
    18532,
    18567,
    18598,
    18606,
    18623,
    18641,
    18650,
    18669,
    18670,
    18724,
    18727,
    18743,
    18788,
    18793,
    18806,
    18810,
    18822,
    18838,
    18846,
    18881,
    18925,
    18942,
    18953,
    18963,
    18966,
    18979,
    18984,
    18986,
    18988,
    18990,
    18993,
    18994,
    19044,
    19046,
    19048,
    19058,
    19073,
    19077,
    19078,
    19084,
    19089,
    19093,
    19119,
    19124,
    19140,
    19142,
    19143,
    19160,
    19197,
    19212,
    19223,
    19234,
    19244,
    19281,
    19286,
    19303,
    19307,
    19314,
    19317,
    19349,
    19361,
    19369,
    19499,
    19518,
    19538,
    19552,
    19567,
    19612,
    19617,
    19644,
    19666,
    19678,
    19681,
    19699,
    19705,
    19724,
    19727,
    19746,
    19749,
    19760,
    19784,
    19787,
    19794,
    19795,
    19799,
    19802,
    19817,
    19818,
    19823,
    19842,
    19866,
    19885,
    19888,
    19898,
    19908,
    19923,
    19924,
    19931,
    19932,
    19938,
    19939,
    19987,
    20001,
    20045,
    20057,
    20063,
    20085,
    20112,
    20118,
    20128,
    20130,
    20144,
    20151,
    20155,
    20161,
    20164,
    20186,
    20189,
    20196,
    20209,
    20223,
    20247,
    20271,
    20272,
    20320,
    20332,
    20341,
    20347,
    20354,
    20370,
    20377,
    20428,
    20459,
    20478,
]

available = [x for x in available if x not in ids]
idxes = np.random.choice(available, size=len(available))


for idx in idxes:
    print("{}|{}".format(idx, np.prod(cfg_space.collapsed_dims())))
    cfg = space.point2knob(idx, cfg_space.collapsed_dims())
    print("CFG:", cfg)

    # cfg = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1]
    # idx = space.knob2point(cfg, cfg_space.collapsed_dims())

    try:
        net = NetworkEntity(cfg_space, cfg_space.expand_config(cfg))
        graph = graph_conversion.to_dgl_graph(net)
        edges_src = [edge.item() for edge in graph.edges()[0]]
        edges_dst = [edge.item() for edge in graph.edges()[1]]
        rows = [[idx, s, d] for s, d in zip(edges_src, edges_dst)]
        header = ["graph_id", "src", "dst"]
        edge_file = wd + "data/{}/graph_defs/graph_edges.csv".format(data_name)
        file_exists = os.path.exists(edge_file)
        with open(edge_file, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(header)
            writer.writerows(rows)

        print("Saved graph data ...")

        inp = relay.var("input", shape=(1, 40, 101))
        quant_seq = net.quantization_sequence(inp)
        quant_params = space.generate_quant_params(quant_seq)

        kwargs = {"quant_params": quant_params}
        mod = net.to_relay(inp, **kwargs)
        print(mod)

        input, params = space.generate_random_params(mod)

        # target = tvm.target.Target("cuda")
        target = tvm.target.Target("llvm")

        tasks, task_weights = tvm.auto_scheduler.extract_tasks(
            mod["main"], params, target
        )

        network = "test"
        dtype = "float32"
        batch_size = 1
        input_shape = input.shape
        # log_file = "%s-B%d-%s.json" % (network, batch_size, target.kind.name)
        log_file = wd + "/data/{}/logs/log.json".format(data_name)
        conf_log = wd + "/data/{}/logs/{}.yaml".format(data_name, idx)
        task_log = wd + "/data/{}/logs/tasks.yaml".format(data_name)

        def run_tuning():
            print("Begin tuning...")
            # if os.path.exists(log_file):  # Remove existing log
            #     os.remove(log_file)
            # if os.path.exists(conf_log):
            #     os.remove(conf_log)
            cost_mean, cost_std = net.tune_and_run(
                mod,
                params,
                input,
                target,
                log_file,
                config_log=conf_log,
                task_log=task_log,
            )
            print("Cost (mean|std): {:.3f}|{:.3f}".format(cost_mean, cost_std))

            return cost_mean

        cost = run_tuning()
        row = [idx, cost, len(graph.nodes())]
        header = ["graph_id", "label", "num_nodes"]
        file_exists = os.path.exists(prop_file)
        with open(prop_file, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(header)
            writer.writerow(row)
    except Exception as e:

        row = [idx, 1000000, len(graph.nodes())]
        header = ["graph_id", "label", "num_nodes"]
        file_exists = os.path.exists(prop_file)
        with open(prop_file, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(header)
            writer.writerow(row)

        print(str(e))
