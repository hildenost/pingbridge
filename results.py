from io import StringIO
from requests import get
import re

import numpy as np
import pandas as pd

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)


import matplotlib.pyplot as plt
import matplotlib as mpl

import streamlit as st

print(
    """PINGBRIDGE

  Results and charts on your favourite bridge partnership!

  How it works?

  Paste a link to the live results (pbn)
  Select the couple to scrutinize. 
  Enjoy!

  """
)
st.header("PINGBRIDGE")

"""
Følg favorittparet ditt underveis i turneringa!

Hvordan bruker du dette?

Lim inn link til live-resultatet du følger. Deretter velger du hvilket par
du vil framheve.
"""

# Results and charts on your favourite bridge partnership!

# How it works?

# Paste a link to the live results (pbn)
# Select the couple to scrutinize.
# Enjoy!

# """


url = "https://www.bridge.no/var/ruter/html/9901/2021-08-04.pbn"
url = "https://www.bridge.no/var/ruter/html/9901/2022-08-10.pbn"
pair_number = 35

if "key" not in st.session_state:
    st.session_state["url"] = st.text_input("Lim inn link til arrangementets pbn-fil")


@st.cache_data
def get_pbn():
    return st.session_state["url"]


url = get_pbn()

if st.button("Hent nye resultater"):
    url = get_pbn()


response = get(url)
response.encoding = "ISO-8859-1"
response = response.text

# First, collect all boards into one dataframe

# How to find a board?

search_string = r"\[Board \"(?P<board>\d+)\"((.|\n)*?)\[ScoreTable (?P<headers>.*?)\](?P<scoretable>(.|\n)*?)\["
pattern = re.compile(search_string)


# Data model participating person
# number name club gender pairid
# Data model pairid
# pairid rank scoreMP score%
def collect_pairs(response):
    search_pairs = r'\[TotalScoreTable "(?P<headers>.*?)"\](?P<scoretable>(.|\n)*?)\['
    pattern = re.compile(search_pairs)
    scoretable = pattern.search(response)

    columns = re.split(r"\\[0-9]+[RL];?", scoretable.group("headers"))

    pair_df = pd.read_fwf(StringIO(scoretable.group("scoretable")), names=columns)
    return pair_df


pairs = collect_pairs(response)

print()
dfs = []
while True:
    board = pattern.search(response)

    # If no more matches, exit
    if board is None:
        break

    board_no = int(board.group("board"))

    board_headers = board.group("headers")

    scoretable = [
        [col for col in row.split()]
        for row in board.group("scoretable").strip().splitlines()
    ]
    score_df = pd.DataFrame(scoretable)
    score_df["Board"] = board_no

    dfs.append(score_df)

    # Moving the pointer
    response = response[board.end() :]

headers = re.split(r"\\\d+[LR];?", board_headers.strip('"'))[:-1]

all_the_boards = pd.concat(dfs).reset_index(drop=True)
all_the_boards.columns = headers + ["Board"]

all_the_boards[["MP_NS", "MP_EW"]] = (
    all_the_boards[["MP_NS", "MP_EW"]].replace("-", "0").astype(float)
)

all_the_boards[["Percentage_NS", "Percentage_EW"]] = (
    all_the_boards[["Percentage_NS", "Percentage_EW"]].replace("-", "0").astype(int)
)

no_boards = all_the_boards["Board"].max()

# Aggregated MP sum
NS = all_the_boards[["PairId_NS", "MP_NS", "Board", "Round"]]
EW = all_the_boards[["PairId_EW", "MP_EW", "Board", "Round"]]

NS.columns = ["PairId", "MP", "Board", "Round"]
EW.columns = ["PairId", "MP", "Board", "Round"]

NS = NS[NS["PairId"] != "-"]
EW = EW[EW["PairId"] != "-"]

all_scores = pd.concat([NS, EW]).apply(pd.to_numeric).sort_values(["PairId", "Board"])
all_scores = all_scores[all_scores["PairId"] != "-"]
all_scores["cumsum"] = all_scores.groupby("PairId")["MP"].cumsum()
round_scores = all_scores.groupby(["PairId", "Round"])["MP"].sum()

cum_round_scores = round_scores.groupby("PairId").cumsum()


def plot_spaghetti(data, selected=None, colors=["m"]):
    fig, ax = plt.subplots()
    highlights = {pid: c for pid, c in zip(selected, colors)}
    for pairid, cum_scores in data.groupby("PairId"):
        color = highlights.get(pairid, "0.8")
        zorder = 1000 if pairid in selected else 1
        cum_scores.plot(color=color, zorder=zorder)
    return fig


def plot_slope(data, selected=None, colors=["m"]):
    # Transform to position instead of score
    df = data.unstack()

    poses = pd.DataFrame(index=df.index)
    for col in df.columns:
        tmp = df[col].sort_values(ascending=False)
        poses[col] = {pair: i + 1 for i, pair in enumerate(tmp.index)}

    fig, ax = plt.subplots()
    highlights = {pid: c for pid, c in zip(selected, colors)}
    for pairid, row in poses.iterrows():
        color = highlights.get(pairid, "0.8")
        zorder = 1000 if pairid in selected else 1
        row.plot(color=color, zorder=zorder, marker="o")
    plt.gca().invert_yaxis()

    return fig


# plot_slope(cum_round_scores, SELECTED)
all_pairids = np.unique(cum_round_scores.index.droplevel(1))

# create pairlist
temp = pairs[["PairId", "Names"]].sort_values(by="PairId")
pairlist = temp["PairId"].astype(str) + " " + temp["Names"].str.strip('"')

pairs = st.multiselect("Velg par", pairlist)

pairids = [int(p.split(maxsplit=1)[0]) for p in pairs]

colors = plt.cm.viridis(np.linspace(0, 1, len(pairids)))


with st.sidebar:
    # Create legend
    from matplotlib.patches import Patch

    legend_elements = [Patch(facecolor=c, label=pair) for c, pair in zip(colors, pairs)]

    fig, ax = plt.subplots(layout="constrained")
    ax.legend(handles=legend_elements, loc="center")
    ax.axis("off")
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    st.pyplot(fig, clear_figure=True)


col1, col2 = st.columns(2)
with col1:
    st.pyplot(plot_slope(cum_round_scores, pairids, colors=colors))
with col2:
    st.pyplot(plot_spaghetti(cum_round_scores, pairids, colors=colors))
