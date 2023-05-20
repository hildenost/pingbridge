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
with st.sidebar:
    st.header("PINGBRIDGE")

    """
    Følg favorittparet ditt underveis i turneringa!

    Hvordan bruker du dette?

    Lim inn link til live-resultatet du følger. Deretter velger du hvilket par
    du vil framheve.
    """
    if "key" not in st.session_state:
        st.session_state["url"] = st.text_input(
            "Lim inn link til arrangementets pbn-fil",
            value="https://www.bridge.no/var/ruter/html/9901/2023-05-20.pbn",
        )

    def get_pbn():
        return st.session_state["url"]

    if st.button("Hent nye resultater"):
        url = get_pbn()


# Results and charts on your favourite bridge partnership!

# How it works?

# Paste a link to the live results (pbn)
# Select the couple to scrutinize.
# Enjoy!

# """


# url = "https://www.bridge.no/var/ruter/html/9901/2021-08-04.pbn"
# url = "https://www.bridge.no/var/ruter/html/9901/2022-08-10.pbn"

url = get_pbn()

response = get(url)
response.encoding = "ISO-8859-1"
response = response.text

# First, collect all boards into one dataframe

# How to find a board?
eventname = re.search(r'\[Event "(.*?)"', response)
if eventname is None:
    st.write("Beklager, det er ikke kommet resultater ennå. Prøv igjen senere.")

if eventname is not None:
    st.title(eventname.group(1))

eventdate = re.search(r'\[Date "(\d{4})\.(\d\d).(\d\d)"', response)
if eventdate is not None:
    year, month, day = eventdate.groups()
    st.write(f"{day}.{month}.{year}")


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
results = pairs
pairlist = temp["PairId"].astype(str) + " " + temp["Names"].str.strip('"')

pairs = st.multiselect("Velg par", pairlist)

temp = round_scores.reset_index()
curr_round = int(temp["Round"].max())

st.metric("Siste runde", curr_round)


df = cum_round_scores.unstack()
poses = pd.DataFrame(index=df.index)
for col in df.columns:
    tmp = df[col].sort_values(ascending=False)
    poses[col] = {pair: i + 1 for i, pair in enumerate(tmp.index)}

import streamlit.components.v1 as components

for pair in pairs:
    st.header(pair)

    pairid, name = pair.split(maxsplit=1)

    selected_pair = results[results["PairId"] == int(pairid)]
    idx = selected_pair.index.values[0]
    res = selected_pair.loc[idx]

    places = poses.loc[int(pairid)]

    if "ScoreCarryOver" in res.index:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            delta = int(places[curr_round])
            if curr_round > 1:
                delta -= places[curr_round - 1]
            st.metric("Plassering", res["Rank"], -delta)
        with col2:
            st.metric(
                "Poeng", res["TotalScoreMP"], round_scores[(int(pairid), curr_round)]
            )
        with col3:
            st.metric("Prosent", res["TotalPercentage"])
        with col4:
            st.metric("Carry over", res["ScoreCarryOver"])
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            delta = int(places[curr_round])
            if curr_round > 1:
                delta -= places[curr_round - 1]
            st.metric("Plassering", res["Rank"], -delta)
        with col2:
            st.metric(
                "Poeng", res["TotalScoreMP"], round_scores[(int(pairid), curr_round)]
            )
        with col3:
            st.metric("Prosent", res["TotalPercentage"])

pairids = [int(p.split(maxsplit=1)[0]) for p in pairs]

colors = plt.cm.viridis(np.linspace(0, 1, len(pairids)))


# with st.sidebar:
#    # Create legend
#    from matplotlib.patches import Patch
#
#    legend_elements = [Patch(facecolor=c, label=pair) for c, pair in zip(colors, pairs)]
#
#    fig, ax = plt.subplots(layout="constrained")
#    ax.legend(handles=legend_elements, loc="center")
#    ax.axis("off")
#    ax.xaxis.set_visible(False)
#    ax.yaxis.set_visible(False)
#    st.pyplot(fig, clear_figure=True)
#

col1, col2 = st.columns(2)
with col1:
    st.pyplot(plot_slope(cum_round_scores, pairids, colors=colors))
with col2:
    st.pyplot(plot_spaghetti(cum_round_scores, pairids, colors=colors))
