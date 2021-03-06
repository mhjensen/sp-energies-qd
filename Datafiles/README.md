Data files
==========

Abbreviation for observables:

  - **addrm** = addition and removal energies
  - **ground** = ground state energy

Abbreviation for methods:

  - **CCSD** = coupled-cluster method with singles and doubles
  - **DMC** = diffusion Monte Carlo method
  - **EOM** = equation of motion method
  - **FCI** = full configuration interaction method
  - **HF** = Hartree-Fock method *only* (most methods implicitly use HF as the
    starting point, so this just means no post-HF method was used)
  - **IMSRG** = in-medium similarity renormalization group method truncated to
    two-body level (so-called “IM-SRG(2)”) using White generator with
    Epstein-Nesbet denominators
  - **MagnusQuads** = Magnus method with quadruples.
  - **QDPT⟨n⟩** = quasidegenerate perturbation theory of level `⟨n⟩` (if `⟨n⟩`
    is omitted, it defaults to 3)

## Directory contents

  - `addrm-dmc-pedersen.txt`: addrm (DMC) by Pedersen Lohne

  - `ground-sarah.txt`: ground (CCSD, FCI, HF, IMSRG) by Sarah Reimann

  - `EOM_CCSD_qd_*.dat`: ground (CCSD) + addrm (CC+EOM) by Sam

  - `EOM_IMSRG_qd_*.dat`, `EOM-IMSRG_freq_sweep_*.dat`, `freq_sweep_*.dat`:
    ground (IMSRG) + addrm (IMSRG+EOM) by Nathan

  - `EOM_IMSRG_FEI_HAM_particle_*.dat`: similar to `EOM_IMSRG_qd_*.dat`.  EOM
    was calculated using Nathan's code with matrix elements from Fei's IM-SRG
    code.  This was to see if there was any discrepancies between Fei's and
    Nathan's IM-SRG code.  The difference was insignificant and could be
    attributed to differences in ODE solver precision.

  - `EOM_magnus_quads_*.dat`: ground (MagnusQuad) + addrm(MagnusQuad+EOM) by
    Nathan

  - `imsrg-qdpt/`: ground (IMSRG) + addrm (IMSRG+QDPT) data contributed by Fei

  - `plot_*.py`: various plotting scripts

  - `plot_settings/`: fine tuning configuration for the plots (like zoom
    level).  You don't have to modify these: just run the plot scripts in
    `--interactive` mode and then adjust the plots.

  - `README.md`: what you're reading right now

  - `utils.py`: contains code shared by many of the scripts here.

  - `fits.txt`: extrapolation fit results used by `plot_fit_badness.py`.  Note
    that this is from an earlier fitting experiment.  Not really used anymore.

  - `compare_rel_slopes.txt`: relative slopes, generated by `plot_compare.py`
    and read by `plot_compare_rel_slope.py`.
