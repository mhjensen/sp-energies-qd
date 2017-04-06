#!/usr/bin/env python3
# Generates ../FigureFiles/fig-by-num-shells-*.svg from the data files.
import argparse, itertools, os, sys
import matplotlib
import matplotlib.ticker
import matplotlib.pyplot as plt
import pandas as pd
import utils

def plot(label, num_filled, freq,
         num_shells_range, interaction="normal"):
    d_dmc = utils.load_all_dmc()
    d_dmc = d_dmc[(d_dmc["interaction"] == interaction) &
                  (d_dmc["label"] == label) &
                  (d_dmc["num_filled"] == num_filled) &
                  (d_dmc["freq"] == freq)]
    d_dmc = d_dmc.set_index(["num_particles", "freq"])
    d = utils.load_all()
    d = utils.filter_preferred_ml(d)
    d = d[(d["method"] != "imsrg[f]+eom[n]") &
          (d["method"] != "magnus_quads+eom") &
          (d["interaction"] == interaction) &
          (d["label"] == label) &
          (d["num_filled"] == num_filled) &
          (d["num_shells"] >= num_shells_range[0]) &
          (d["num_shells"] <= num_shells_range[1]) &
          (d["freq"] == freq)]
    num_particles = num_filled * (num_filled + 1)
    energy_type = {"ground": "ground state",
                   "add": "addition",
                   "rm": "removal"}[label]
    fig, ax = plt.subplots()
    fig.set_size_inches((4, 3))
    for method, case in d.groupby("method"):
        case = case.sort_values("num_shells")
        xs = case["num_shells"].astype(int)
        ys = case["energy"]
        ax.plot(xs, ys, "-x", label=utils.METHOD_LABEL[method],
                color=utils.METHOD_COLOR[method])
        ax.get_xaxis().set_major_locator(
            matplotlib.ticker.MaxNLocator(integer=True))
    if len(d_dmc["energy"]):
        assert len(d_dmc["energy"]) == 1
        ax.axhline(d_dmc["energy"][0],
                   label=utils.METHOD_LABEL["dmc"],
                   color=utils.METHOD_COLOR["dmc"],
                   linestyle=utils.DMC_LINESTYLE)
    ax.set_xlabel("K (number of shells)")
    ax.set_ylabel("E (energy)")
    ax.legend()
    fig.tight_layout()
    utils.savefig(fig,
                  "by-num-shells-{num_particles}-{num_filled}-"
                  "{label}-{interaction}"
                  .format(**locals()))

with utils.plot(__file__, call=plot) as interactive:
    if not interactive:
        plot("ground", freq=1.0, num_filled=2, num_shells_range=[4, 15])
