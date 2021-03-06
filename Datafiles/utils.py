import argparse, base64, collections, contextlib, decimal, functools
import hashlib, inspect, io, json, logging, math, os, pickle, re, sys
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.optimize

def parse_version_digits(ver):
    return tuple(map(int, re.match("(\d+)\.(\d+)\.(\d+)", ver).groups()))

# used for the 'float_precision' argument in pandas.read_csv
# "round_trip" is preferable but it segfaults on some versions of Pandas:
# https://github.com/pandas-dev/pandas/issues/15140
if "+" in pd.__version__ or parse_version_digits(pd.__version__) >= (0, 20, 0):
    PRECISION = "round_trip"
else:
    PRECISION = "high"
    sys.stderr.write("Warning: Your Pandas is too old. "
                     "Data read from files may lose accuracy.\n")
    sys.stderr.flush()

# we want deterministic PDFs, but this isn't supported until matplotlib 2.1+
os.environ["SOURCE_DATE_EPOCH"] = "0"
if not ("+" in matplotlib.__version__ or
        parse_version_digits(matplotlib.__version__) > (2, 1, 0)):
    sys.stderr.write("Warning: Your Matplotlib is too old. "
                     "PDF output may be nondeterministic.\n")
    sys.stderr.flush()

JSON_PRETTY = {
    "ensure_ascii": False,
    "indent": 4,
    "separators": (",", ": "),
    "sort_keys": True,
}

METHOD_COLOR = {
    "ccsd": "#428ff4",
    "ccsd+eom": "#1351c4",
    "dmc": "#666666",
    "fci": "#2e2360",
    "hf": "#b7ac12",
    "hf+qdpt3": "#e28522",
    "imsrg": "#3ec61b",
    "imsrg+eom": "#841a0b",
    "imsrg+qdpt3": "#286d17",
    "imsrg[f]+eom[n]": "#8e2544",
    "magnus_quads+eom": "#a825bc",
    "mp2": "#a81e4c",
}

METHOD_LABEL = {
    "ccsd": "CCSD",
    "ccsd+eom": "CCSD + EOM2",
    "dmc": "DMC",
    "fci": "FCI",
    "hf": "HF only",
    "hf+qdpt2": "HF only + QDPT2",
    "hf+qdpt3": "HF only + QDPT3",
    "imsrg": "IM-SRG(2)",
    "imsrg+eom": "IM-SRG(2) + EOM2",
    "imsrg+qdpt2": "IM-SRG(2) + QDPT2",
    "imsrg+qdpt3": "IM-SRG(2) + QDPT3",
    "imsrg[f]+eom[f]": "IM-SRG(2)[F] + EOM2[N]",
    "magnus_quads+eom": "Magnus(2*) + EOM2",
    "mp2": "MP2",
}

METHOD_MARKER = {
    "ccsd": "o",
    "ccsd+eom": ".",
    "fci": "D",
    "hf": "^",
    "hf+qdpt3": "s",
    "imsrg": "x",
    "imsrg+eom": "*",
    "imsrg+qdpt3": "+",
    "mp2": "p",
}

MARKERSIZE_CORRECTION = {
    "D": 0.7,
    "2": 1.5,
}

ENERGY_SYMBOL = {
    "ground": r"E",
    "add": r"\varepsilon^{(+)}",
    "rm": r"\varepsilon^{(-)}",
}

DMC_LINESTYLE = "--"

def parse_color(color):
    '''Accepts either (r, g, b[, a]) or "#rrggbb[aa]".'''
    if isinstance(color, str):
        assert color[0] == "#"
        cs = []
        cs.append(int(color[1:3], 16) / 255.0)
        cs.append(int(color[3:5], 16) / 255.0)
        cs.append(int(color[5:7], 16) / 255.0)
        if len(color) > 7:
            cs.append(int(hexcolor[7:9], 16) / 255.0)
        color = cs
    return np.array(color)

def colormap(name, colors):
    n = len(colors)
    rgba = np.array([parse_color(color) for color in colors]) # [_; k, n]
    rgba = rgba.transpose()                                   # [_; k, n]
    k = rgba.shape[0]
    t = np.linspace(0.0, 1.0, n)              # [_; n]
    t = np.broadcast_to(t, (k, n))            # [_; k, n]
    tccs = np.stack([t, rgba, rgba], axis=-1) # [_; k, n, 3]
    cdict = dict(zip(["red", "green", "blue", "alpha"], tccs))
    return matplotlib.colors.LinearSegmentedColormap(name, cdict)

def split_alpha_colormap(name, hexcolor):
    return colormap(name, [hexcolor + "00", hexcolor + "ff", hexcolor + "00"])

# Rainbow (J', C') = (71.0, 26.0)
CMAP_RAINBOW = colormap("rainbow", [
    "#ec7ca3", "#ee7c9a", "#ef7c8f", "#f07d85",
    "#f07e7b", "#f08071", "#ef8168", "#ed845e",
    "#ea8656", "#e7894e", "#e48c46", "#df9040",
    "#da933a", "#d59736", "#ce9b33", "#c79f32",
    "#c0a233", "#b8a635", "#afa939", "#a6ad3e",
    "#9db044", "#93b34b", "#89b553", "#7eb85b",
    "#73ba63", "#67bc6c", "#5bbd75", "#4fbf7e",
    "#42bf87", "#35c08f", "#28c098", "#1ac0a1",
    "#0bc0a9", "#01c0b1", "#05bfb9", "#12bec1",
    "#20bcc8", "#2dbbcf", "#3ab9d5", "#45b7db",
    "#51b5e0", "#5cb3e5", "#66b0e9", "#70aded",
    "#7aabf0", "#83a8f3", "#8ca5f4", "#95a1f5",
    "#9d9ef6", "#a59bf5", "#ac98f4", "#b495f2",
    "#bb92f0", "#c18fec", "#c78ce8", "#cd89e3",
    "#d287dd", "#d784d7", "#dc82d0", "#e080c8",
    "#e47fbf", "#e77eb7", "#ea7dad", "#ec7ca3",
])

def matplotlib_try_enable_deterministic_svgs():
    # we want deterministic SVGs, but this isn't supported until matplotlib 2.0
    try:
        matplotlib.rcParams["svg.hashsalt"] = ""
    except KeyError:
        sys.stderr.write("Warning: Your matplotlib is too old. "
                         "SVG output may be nondeterministic.\n")
        sys.stderr.flush()

def init(filename):
    '''(Obsolete)'''
    plot(filename).__enter__()

def parse_arg(s):
    s = s.strip()
    try:
        return json.loads(s)
    except ValueError:
        pass
    if "," in s:
        return [parse_arg(s) for s in s.split(",")]
    if s.lower() == 'false':
        return False
    if s.lower() == 'true':
        return True
    return s

def parse_kwarg(s):
    key = ""
    s = s.strip()
    m = re.match(r"(\w+)\s*[=]\s*(.*)$", s)
    if m:
        key, s = m.groups()
    s = re.match(r"(.*?),?$", s).group(1)
    return key, parse_arg(s)

@contextlib.contextmanager
def plot(filename, call=None, block=True, main_name="main"):
    if call:
        call_name = call.__qualname__
        p = argparse.ArgumentParser(
            description=("The plotting script may be run without "
                         f"arguments, in which case it runs the '{main_name}' "
                         "function (which usually saves a set of predefined "
                         "plots to disk).  Otherwise, if the script is called "
                         "with arguments in Python syntax, they will be "
                         f"passed to '{call_name}'."))
        p.add_argument("cmd_args", metavar="interactive_arg", nargs="*",
                       help=(f"arguments passed to the '{call_name}' function "
                             "(in Python function call syntax; "
                             "just the part inside the parentheses)"))
        p.add_argument("-v", "--verbose", action="store_true")
        args = p.parse_args()
        if args.verbose:
            logging.basicConfig(format="[%(levelname)s] %(message)s",
                                level=logging.INFO)
        cmd_args = args.cmd_args
        matplotlib.rcParams["interactive"] = bool(cmd_args)
    else:
        cmd_args = []
    os.chdir(os.path.dirname(filename))
    matplotlib_try_enable_deterministic_svgs()
    matplotlib.style.use("seaborn-deep")
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["mathtext.fontset"] = "stixsans"
    if cmd_args:
        args = []
        kwargs = {}
        for cmd_arg in cmd_args:
            key, value = parse_kwarg(cmd_arg)
            if key:
                kwargs[key] = value
            else:
                args.append(value)
        sys.stderr.write("{}({})\n".format(
            call.__name__,
            ", ".join(["{!r}".format(arg) for arg in args] +
                      ["{}={!r}".format(k, v)
                       for k, v in sorted(kwargs.items())])))
        sys.stderr.flush()
        call(*args, **kwargs)
        yield True
    else:
        yield False
    if matplotlib.rcParams["interactive"]:
        plt.show(block=block)

def plot_main(filename, call, main):
    '''Run 'call' if interactive arguments are provided, or just call 'main'
    if the script is run in non-interactive mode.'''
    main_name = main.__qualname__
    with plot(__file__, call=call, main_name=main_name) as interactive:
        if not interactive:
            main()

def savefig(fig, name=None, fn=None):
    if (name is None) == (fn is None):
        raise TypeError("either name or fn must be given, but not both")
    if not matplotlib.rcParams["interactive"]:
        if fn is None:
            fn = "../FigureFiles/fig-{name}.svg".format(**locals())
        fig.savefig(fn)
        plt.close(fig)
        sys.stderr.write("Figure saved to: {}\n".format(fn))
        sys.stderr.flush()

def filter_eq(d, keys, check_unused_kwargs=True):
    empty = d.head(0)
    gs = d.groupby(keys)
    def filter_eq_inner(**kwargs):
        args = tuple(kwargs.pop(key) for key in keys)
        if check_unused_kwargs and kwargs:
            raise TypeError("unused keyword argument: {!r}".
                            format(next(iter(kwargs))))
        try:
            return gs.get_group(args)
        except KeyError:
            return empty
    return filter_eq_inner

def groupby(d, cols):
    '''Like DataFrame.groupby but converts the key into an OrderedDict.'''
    for key, g in d.groupby(cols):
        # pandas inconsistently returns either a tuple or the object itself
        # depending on how many cols were used
        if len(cols) == 1:
            yield collections.OrderedDict([(cols[0], key)]), g
        else:
            yield collections.OrderedDict(zip(cols, key)), g

def update_range(r, x):
    for x in np.array(x).flatten():
        # make sure NaN gets handled correctly
        if r[0] == None or not (x >= r[0]):
            r[0] = x
        if r[1] == None or not (x <= r[1]):
            r[1] = x

def expand_range(r, factor):
    return np.array([
        r[0] - factor * (r[1] - r[0]),
        r[1] + factor * (r[1] - r[0]),
    ])

def intersperse(sep, xs):
    first = True
    for x in xs:
        if first:
            first = False
        else:
            yield sep
        yield x

def merge_dicts(d, *ds):
    d = type(d)(d)
    for di in ds:
        d.update(di)
    return d

def num_dec_digits(x):
    x = abs(x)
    e = int(math.log10(x))
    if 10 ** e > x: # prevent overshooting due to round off errors
        e -= 1
    assert 10 ** e <= x < 10 ** (e + 1)
    return e

def render_with_err(value, err, digits=1):
    if err <= 0.0:
        raise Exception("uncertainty must be positive")
    if not (math.isfinite(value) and math.isfinite(err)):
        raise Exception("value and err must be finite")
    e_err = num_dec_digits(err)
    modified_err = int(round(err * 10.0 ** -e_err))
    if modified_err == 10:
        modified_err = 1
        e_err -= 1
    if e_err > 0:
        e_value = num_dec_digits(value)
        e_diff = e_value - e_err
        if e_diff >= 0:
            s = "{{:.{}e}}".format(e_diff).format(value)
            return s.replace("e", "({})e".format(modified_err))
        else:
            return "{}0({})e{}".format("" if value >= 0.0 else "-",
                                       modified_err, e_err)
    else:
        s = "{{:.{}f}}({{}})".format(-e_err)
        return s.format(value, modified_err)

def load_json_records(fn):
    with open(fn) as f:
        return pd.DataFrame.from_records([
            json.loads(s) for s in f.read().split("\n\n") if s])

sanitize_json_handlers = [
    (pd.DataFrame, lambda self: sanitize_json(self.to_dict())),
    (pd.Series, lambda self: sanitize_json(self.to_dict())),
    (dict, lambda self: dict((k, sanitize_json(v)) for k, v in self.items())),
    (list, lambda self: [sanitize_json(x) for x in self]),
    (tuple, lambda self: [sanitize_json(x) for x in self]),
    (np.ndarray, lambda self: [sanitize_json(x) for x in self]),
    (float, lambda self: self),
    (int, lambda self: self),
    (str, lambda self: self),
    (type(None), lambda self: self),
    (np.float64, float),
    (np.int64, int),
]

def sanitize_json(j):
    for type, handler in sanitize_json_handlers:
        if isinstance(j, type):
            return handler(j)
    raise TypeError("no known conversion to JSON: {!r} ({})"
                    .format(j, type(j)))

def json_pretty(j):
    f = io.StringIO()
    write_json(f, j)
    return f.getvalue()

def read_json(f):
    return json.load(f)

def write_json(f, j):
    json.dump(sanitize_json(j), f, **JSON_PRETTY)

def load_json(fn, fallback=None):
    if os.path.exists(fn):
        with open(fn) as f:
            return read_json(f)
    return fallback

def save_json(fn, j):
    with open(fn + ".tmp", "w") as f:
        write_json(f, j)
    os.rename(fn + ".tmp", fn)

def to_json_bytes(x):
    return json_pretty(x).encode("utf-8")

class FileDeps:
    '''Represents a set of existing, read-only files, used as an argument for
    cacheable functions.'''

    def __init__(self, *paths):
        self._paths = frozenset(paths)

    def __getitem__(self, path):
        if path not in self._paths:
            raise ValueError("undeclared dependency: {}".format(path))
        return path

    def _hash(self):
        '''The hash is computed on demand so that the file is only checked in
        the correct context (e.g. if the working directory needs to be changed
        before calling a function)..'''
        return [(path, os.path.getmtime(path))
                for path in sorted(self._paths)]

sanitize_json_handlers.append((FileDeps, lambda self: self._hash()))

def cached(dir=".cache", hash=hashlib.sha1,
           to_bytes=to_json_bytes, dump=pickle.dump, load=pickle.load):
    def make_cached(func):
        h0_in = [func.__qualname__]
        h0 = hash(to_bytes(h0_in)).hexdigest()
        name = "".join(re.findall(r"[-_.a-zA-Z0-9]+", func.__qualname__))
        signature = inspect.signature(func)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # inspect.Signature is needed to obtain the default arguments
            bound_arguments = signature.bind(*args, **kwargs)
            bound_arguments.apply_defaults()
            h_in = to_bytes((h0, dict(bound_arguments.arguments)))
            h = base64.urlsafe_b64encode(hash(h_in).digest()).decode("ascii")
            path = os.path.join(dir, "{}_{}.cache~".format(name, h.strip("=")))
            try:
                with open(path, "rb") as f:
                    return load(f)
            except (OSError, pickle.UnpicklingError):
                pass
            result = func(*args, **kwargs)
            os.makedirs(dir, exist_ok=True)
            with open(path, "wb") as f:
                dump(result, f)
            return result
        return wrapper
    return make_cached

def sync_axes_lims(ax, settings, save):
    setting = settings.get("xlim")
    if setting:
        ax.set_xlim(setting)
    setting = settings.get("ylim")
    if setting:
        ax.set_ylim(setting)
    def on_xlims_changed(ax):
        settings["xlim"] = ax.get_xlim()
        save()
    def on_ylims_changed(ax):
        settings["ylim"] = ax.get_ylim()
        save()
    ax.callbacks.connect("xlim_changed", on_xlims_changed)
    ax.callbacks.connect("ylim_changed", on_ylims_changed)

def parse_uncertainty(s):
    '''Parse a numeric string of the form "<number>(<uncertainty>)".'''
    value, uncertainty = re.match(r"([^(]+)\((\d+)\)$", s).groups()
    exponent = decimal.Decimal(value).as_tuple().exponent
    uncertainty =  decimal.Decimal((0, list(map(int, uncertainty)), exponent))
    return value, uncertainty

def load_table(f, sep=r"\s+", names=None, skiprows=0, na_filter=None):
    kwargs = {
        "sep": sep,
        "names": names,
        "quotechar": "'",
        "comment": "#",
        "float_precision": PRECISION,
        "skiprows": skiprows,
        "na_filter": na_filter,
    }
    if names is not None:
        kwargs["header"] = None
    return pd.read_csv(f, **kwargs)

def save_table(f, df):
    df.to_csv(f, sep=" ", index=False, na_rep="nan")

def parse_nathan_like_data(d, label):
    if label == "add":
        d["energy"] = d["E(N+1)-E(N)"]
    elif label == "rm":
        d["energy"] = -d["E(N-1)-E(N)"]
    else:
        raise ValueError("invalid value for label parameter")
    d = d[["shells", "filled", "ML", "omega", "energy"]]
    d = d.rename(columns={
        "shells": "num_shells",
        "filled": "num_filled",
        "ML": "ml",
        "omega": "freq",
    })
    d["label"] = label
    return d

@np.vectorize
def get_num_filled(num_particles, max_shells=100):
    for k in range(max_shells):
        if num_particles == k * (k + 1):
            return k
    raise ValueError("could not find num_filled for num_particles={}"
                     .format(num_particles))

class FunDepViolationError(Exception):
    def __init__(self, in_cols, out_cols, violations, *args):
        self.in_cols = in_cols
        self.out_cols = out_cols
        self.violations = violations
        super().__init__(self, in_cols, out_cols, violations, *args)

    def __str__(self):
        return "Functional dependency does not hold: {!r} -> {!r}\n{!r}".format(
            self.in_cols, self.out_cols, self.violations)

def check_fun_dep(d, cols, tolers, combiner=None):
    '''Check if a functional dependency constraint holds in the data.  That
    is, check if the output columns are unique (up to some tolerance) for each
    combination of input columns.  Then, a combined version is returned based
    on the `combiner` function, which by default is the identity function and
    therefore does nothing.  Raises `FunDepViolationError` when violations are
    found.

    For example, `check_fundep(d, ["x", "y"], {"z": 0.1, "w": 0.2}, combiner)`
    checks whether each `(z, w)` pair is uniquely determined by `(x, y)` with
    an allowable tolerance of `0.1` for `z` and `0.2` for `w`.

    `combiner` is a function `(DataFrame) -> DataFrame` that is fed to
    `GroupBy.apply` to combine duplicated data.
    '''

    tolers = collections.OrderedDict(tolers)
    cols = list(cols)
    out_cols = list(tolers.keys())
    gs = d.groupby(cols)

    if len(d) == 0:
        return d
    if d[cols + out_cols].isnull().any().any():
        # sanity check to prevent confusing errors later on
        # (or worse: it could lead to false positives)
        raise ValueError("input columns must not contain NaN")

    # TODO: can we reuse the same d.groupby from earlier?
    std = d.groupby(cols).std(ddof=0)
    mask = functools.reduce(
        lambda x, y: x | y,
        (std[out_col] > tolers[out_col] for out_col in out_cols))
    if mask.any():
        violations = pd.concat([gs.get_group(k)
                                for k, v in mask.iteritems() if v])
        raise FunDepViolationError(cols, out_cols, violations)

    if combiner is None:
        return d
    else:
        return gs.apply(combiner).reset_index(drop=True)

def n_ml_tms_to_p(n, ml, tms):
    assert n >= 0
    assert tms in [-1, 1]
    k = 2 * n + abs(ml)
    # the convention of tms here uses 0 for +1/2 and 1 for -1/2
    # of course, it's completely arbitrary
    return (1 - tms) // 2 + k * (k + 2) + ml

def p_to_n_ml_tms(p):
    assert p >= 0
    # the convention of tms here uses 0 for +1/2 and 1 for -1/2
    # of course, it's completely arbitrary
    tms = 1 - p % 2 * 2
    k = int((4 * p + 1) ** 0.5 - 1) // 2
    ml = p // 2 * 2 - k * (k + 2)
    n = (k - abs(ml)) // 2
    return n, ml, tms

def p_to_ml(p):
    _, ml, _ = p_to_n_ml_tms(p)
    return ml

def p_num_filled_to_label(p, num_filled):
    if p >= num_filled * (num_filled + 1):
        return "add"
    else:
        return "rm"

def preferred_ml(label, num_filled):
    '''Use the ml closest to shell closure, closest to zero.'''
    return 0 if label == "ground" else (num_filled + (label != "add")) % 2

def filter_preferred_ml(d):
    return d[d.apply(lambda r:
                     r["ml"] == preferred_ml(r["label"], r["num_filled"]),
                     axis=1)]

def canonicalize_p(p):
    '''The addition/removal energies use p to label the state that is being
    added or removed.  However it does so inconsistently since some states are
    equivalent to others (e.g. states that only differ by spin).'''
    # k = 2 n + abs(ml)
    n, ml, _ = p_to_n_ml_tms(p)
    return n_ml_tms_to_p(n, abs(ml), 1)

def leftmost_combiner(d):
    return d.iloc[[0]]

def rightmost_combiner(d):
    return d.iloc[[-1]]

def unique_combiner(d):
    if len(d) != 1:
        raise Exception("this group is not unique:\n{}".format(d))
    return d

def priority_combiner(d):
    d = d.drop_duplicates()
    d = d[d["priority"] == d["priority"].max()]
    if len(d) > 1:
        raise Exception("cannot resolve data with equal priority")
    return d

def superset_combiner(d):
    '''Used as the combiner function for check_fun_dep.  The purpose of this
    function is to detect if there is at least one row where 'origin' is
    'NEW'.  If not, it will simply fail with an error.  This can be used to
    check if two datasets ('OLD' and 'NEW') are consistent and whether the
    'NEW' dataset is a superset of the 'OLD' one.'''
    if (d["origin"] != "NEW").all():
        raise Exception("Not a superset:", d)
    return d

NATHAN_ATTACHED_COLS = ["shells", "filled", "ML", "MS", "omega", "E(N)",
                        "E(N+1)-E(N)", "E(N+1)", "partialnorm(1p)"]

NATHAN_REMOVED_COLS = ["shells", "filled", "ML", "MS", "omega", "E(N)",
                       "E(N-1)-E(N)", "E(N+1)", "partialnorm(1p)"]

def load_ground_dmc():
    '''Similar to load_ground, but without num_shells nor priority and has
    extra columns: energy_err, energy_per_particle_err.'''
    d = load_table("ground-dmc-joergen.txt")
    d["interaction"] = "normal"
    d["label"] = "ground"
    d["ml"] = 0
    d["num_filled"] = get_num_filled(d["num_particles"])
    d["energy_per_particle"] = d["energy"] / d["num_particles"]
    d["energy_per_particle_err"] = d["energy_err"] / d["num_particles"]
    return d

@cached()
def load_ground(with_priority=False, toler=6e-4,
                files=FileDeps(
                    "ground-sarah.txt",
                    "imsrg-qdpt/ground.txt",
                    "EOM_IMSRG_qd_attached.dat",
                    "EOMIMSRG_up_to_16_attached.dat",
                    "QD_CCSD_PA.dat",
                    "QD_CCSD_PA_10_2_010-100.dat",
                )):
    '''
    Read ground state energy data from various sources.  Columns (order is
    unspecified):

        [priority,] interaction, label, ml, freq, num_particles, num_filled,
        num_shells, method, energy, energy_per_particle

    If 'with_priority' is specified, then there is an additional column
    "priority", and the data is *not* deduplicated.  'toler' specifies the
    threshold below which the functional dependency check would not fail.

    The data satisfies the following functional dependencies:

        ([priority,] freq, num_filled, num_shells, method) -> energy
        num_particles = num_particles * (num_particles + 1)
        energy_per_particle = energy / num_particles

    '''
    ds = []

    # agreement between Fei's IMSRG and Sarah's IMSRG ~ 1e-3
    # agreement between Nathan's IMSRG and Sarah's IMSRG ~ 1e-3
    d = load_table(files["ground-sarah.txt"])
    # this data point does not agree with Fei's results and just seems wrong
    # (it breaks the monotonically decreasing behavior of HF)
    d = d[~((d["freq"] == 0.1) &
            (d["num_particles"] == 30) &
            (d["num_shells"] == 16) &
            (d["method"] == "hf"))]
    # this data point disagrees with both Fei and Nathan's results
    d = d[~((d["freq"] == 0.5) &
            (d["num_particles"] == 30) &
            (d["num_shells"] == 11) &
            (d["method"] == "imsrg"))]
    d["num_filled"] = get_num_filled(d["num_particles"])
    del d["num_particles"]
    d["priority"] = -2
    d = d.dropna()
    ds.append(d)

    d = load_table(files["imsrg-qdpt/ground.txt"])
    d = d[d["interaction"] == "normal"]
    del d["interaction"]
    d["priority"] = 0
    ds.append(d)

    # agreement between Fei's IMSRG and Nathan's IMSRG ~ 1e-4
    d = pd.concat([
        load_table(files["EOM_IMSRG_qd_attached.dat"]),
        load_table(files["EOMIMSRG_up_to_16_attached.dat"],
                   names=NATHAN_ATTACHED_COLS),
    ], ignore_index=True)
    d = d.rename(columns={
        "shells": "num_shells",
        "filled": "num_filled",
        "omega": "freq",
        "E(N)": "energy",
    })[["num_shells", "num_filled", "freq", "energy"]]
    d = d.drop_duplicates()
    d["method"] = "imsrg"
    d["priority"] = -1
    ds.append(d)

    d = pd.concat([
        load_table(files["QD_CCSD_PA.dat"], skiprows=1),
        load_table(files["QD_CCSD_PA_10_2_010-100.dat"], skiprows=1),
    ], ignore_index=True)
    d = d.rename(columns={
        "shells": "num_shells",
        "filled": "num_filled",
        "hw": "freq",
        "E0": "energy",
    })[["num_shells", "num_filled", "freq", "energy"]]
    d = d.drop_duplicates()
    d["method"] = "ccsd"
    d["priority"] = 0
    ds.append(d)

    d = pd.concat(ds, ignore_index=True)
    if with_priority:
        combiner = lambda x: x
    else:
        combiner = priority_combiner
    d = check_fun_dep(d, ["freq", "num_filled", "num_shells", "method"],
                      {"energy": toler}, combiner=combiner)
    if not with_priority:
        del d["priority"]
    d["interaction"] = "normal"
    d["label"] = "ground"
    d["ml"] = 0
    d["num_particles"] = d["num_filled"] * (d["num_filled"] + 1)
    d["energy_per_particle"] = d["energy"] / d["num_particles"]
    return d

def load_addrm_dmc():
    '''Similar to load_addrm, but without num_shells and has an
    extra column: energy_err.'''
    d = load_table("addrm-dmc-pedersen.txt")
    d["interaction"] = "normal"
    d["label"] = d["is_hole"].map(lambda is_hole: "rm" if is_hole else "add")
    del d["is_hole"]
    d["num_particles"] = d["num_filled"] * (d["num_filled"] + 1)
    return d

@cached()
def load_addrm(toler=3e-7,
               files=FileDeps(
                   "imsrg-qdpt/addrm.txt",
                   "EOM_IMSRG_qd_attached.dat",
                   "EOM_IMSRG_qd_removed.dat",
                   "freq_sweep_N6_R10_attached.dat",
                   "freq_sweep_N6_R10_removed.dat",
                   "EOM-IMSRG_freq_sweep_6part_ml1_attached.dat",
                   "EOM-IMSRG_freq_sweep_6part_ml1_removed.dat",
                   "EOM_IMSRG_softened_attached.dat",
                   "EOM_IMSRG_softened_removed.dat",
                   "EOM_IMSRG_FEI_HAM_particle_attached.dat",
                   "EOM_IMSRG_FEI_HAM_particle_removed.dat",
                   "EOMIMSRG_up_to_16_attached.dat",
                   "EOMIMSRG_up_to_16_removed.dat",
                   "EOM_particle_attached.dat",
                   "EOM_particle_removed.dat",
                   "missing_EOM_particle_attached.dat",
                   "EOM_magnus_quads_attached.dat",
                   "EOM_magnus_quads_removed.dat",
                   "EOM_CCSD_qd_attached.dat",
                   "EOM_CCSD_qd_removed.dat",
               )):
    '''
    Get the addition and removal energies.  Columns:

        label, ml, interaction, freq, num_particles, num_filled,
        method, num_shells, energy

    '''
    ds = []

    # Fei's QDPT on Fei's IMSRG matrix elements
    d = load_table(files["imsrg-qdpt/addrm.txt"])
    d["method"] += d["iter"].map(lambda iter: "+qdpt3" if iter else "")
    del d["iter"]
    d["label"] = d[["p", "num_filled"]].apply(
        lambda r: p_num_filled_to_label(**r), axis=1)
    d["ml"] = d["p"].map(p_to_ml)
    del d["p"]
    ds.append(d)

    # Nathan's EOM on Nathan's IMSRG matrix elements
    d = pd.concat([
        parse_nathan_like_data(
            load_table(files["EOM_IMSRG_qd_attached.dat"]), "add"),
        parse_nathan_like_data(
            load_table(files["EOM_IMSRG_qd_removed.dat"]), "rm"),
        parse_nathan_like_data(
            load_table(files["freq_sweep_N6_R10_attached.dat"]), "add"),
        parse_nathan_like_data(
            load_table(files["freq_sweep_N6_R10_removed.dat"]), "rm"),
        parse_nathan_like_data(
            load_table(files["EOM-IMSRG_freq_sweep_6part_ml1_attached.dat"],
                       names=NATHAN_ATTACHED_COLS), "add"),
        parse_nathan_like_data(
            load_table(files["EOM-IMSRG_freq_sweep_6part_ml1_removed.dat"],
                       names=NATHAN_REMOVED_COLS), "rm"),
        parse_nathan_like_data(
            load_table(files["EOMIMSRG_up_to_16_attached.dat"],
                       names=NATHAN_ATTACHED_COLS), "add"),
        parse_nathan_like_data(
            load_table(files["EOMIMSRG_up_to_16_removed.dat"],
                       names=NATHAN_REMOVED_COLS), "rm"),
        parse_nathan_like_data(
            load_table(files["EOM_particle_attached.dat"],
                       names=NATHAN_ATTACHED_COLS), "add"),
        parse_nathan_like_data(
            load_table(files["EOM_particle_removed.dat"],
                       names=NATHAN_REMOVED_COLS), "rm"),
        parse_nathan_like_data(
            load_table(files["missing_EOM_particle_attached.dat"],
                       names=NATHAN_ATTACHED_COLS), "add"),
    ], ignore_index=True)
    d["method"] = "imsrg+eom"
    d["interaction"] = "normal"
    ds.append(d)

    d = pd.concat([
        parse_nathan_like_data(
            load_table(files["EOM_IMSRG_softened_attached.dat"]), "add"),
        parse_nathan_like_data(
            load_table(files["EOM_IMSRG_softened_removed.dat"]), "rm"),
    ], ignore_index=True)
    d["method"] = "imsrg+eom"
    d["interaction"] = "sigmaA=0.5,sigmaB=4.0"
    ds.append(d)

    # Nathan's EOM on Fei's IMSRG matrix elements
    d = load_table(files["EOM_IMSRG_FEI_HAM_particle_attached.dat"])
    d = parse_nathan_like_data(d, "add")
    d["method"] = "imsrg[f]+eom[n]"
    d["energy"] *= d["freq"] ** 0.5
    d["interaction"] = "normal"
    ds.append(d)
    d = load_table(files["EOM_IMSRG_FEI_HAM_particle_removed.dat"])
    d = parse_nathan_like_data(d, "rm")
    d["method"] = "imsrg[f]+eom[n]"
    d["energy"] *= d["freq"] ** 0.5
    d["interaction"] = "normal"
    ds.append(d)

    # Nathan's EOM using Magnus method with quadruples
    d = load_table(files["EOM_magnus_quads_attached.dat"])
    d = parse_nathan_like_data(d, "add")
    d["method"] = "magnus_quads+eom"
    d["interaction"] = "normal"
    ds.append(d)
    d = load_table(files["EOM_magnus_quads_removed.dat"])
    d = parse_nathan_like_data(d, "rm")
    d["method"] = "magnus_quads+eom"
    d["interaction"] = "normal"
    ds.append(d)

    # Sam's coupled cluster singles and doubles
    d1 = pd.concat([
        load_table("QD_CCSD_PA.dat", skiprows=1),
        load_table("QD_CCSD_PA_10_2_010-100.dat", skiprows=1),
    ], ignore_index=True)
    d1["label"] = "add"
    d2 = pd.concat([
        load_table("QD_CCSD_PR.dat", skiprows=1),
        load_table("QD_CCSD_PR_10_2_010-100.dat", skiprows=1),
    ], ignore_index=True)
    d2["label"] = "rm"
    d2["dE"] = -d2["dE"]
    d = pd.concat([d1, d2], ignore_index=True)
    d = d.rename(columns={
        "shells": "num_shells",
        "filled": "num_filled",
        "hw": "freq",
        "ML": "ml",
        "dE": "energy",
    })[["label", "num_shells", "num_filled", "freq", "ml", "energy"]]
    d["method"] = "ccsd+eom"
    d["interaction"] = "normal"
    ds.append(d)

    d = pd.concat(ds, ignore_index=True)
    d = check_fun_dep(d, ["label", "ml", "interaction", "freq", "num_filled",
                          "num_shells", "method"],
                      {"energy": toler}, combiner=leftmost_combiner)
    d["num_particles"] = d["num_filled"] * (d["num_filled"] + 1)
    return d

def load_all_dmc():
    ds = []

    d = load_ground_dmc()
    del d["energy_per_particle"]
    del d["energy_per_particle_err"]
    ds.append(d)

    ds.append(load_addrm_dmc())

    return pd.concat(ds, ignore_index=True)

def load_all():
    ds = []

    d = load_ground()
    del d["energy_per_particle"]
    ds.append(d)

    ds.append(load_addrm())

    return pd.concat(ds, ignore_index=True)

def fit_change(fit_type, fit_points, x, y, **params):
    # note: y here is the derivative
    x_in = x[-fit_points:]
    y_in = y[-fit_points:]
    sign = np.sign(np.mean(y_in))
    if fit_type == "loglog":
        def f(x, b, a):
            return a * b * x ** (b - 1)
        mc0 = np.polyfit(np.log(x_in), np.log(abs(y_in)), 1)
        ba0 = [mc0[0] + 1.0, sign * np.exp(mc0[1]) / (mc0[0] + 1.0)]
        names = ["exponent", "coefficient"]
    elif fit_type == "semilog":
        def f(x, b, a):
            return -a * np.exp(-x / b) / b
        mc0 = np.polyfit(x_in, np.log(abs(y_in)), 1)
        ba0 = [-1.0 / mc0[0], sign * -np.exp(mc0[1]) / mc0[0]]
        names = ["lifetime", "coefficient"]
    else:
        assert False
    r0 = {
        "fit_type": fit_type + "0",
        "loglog_params": mc0,
    }
    for i, name in enumerate(names):
        r0[name] = ba0[i]

    # now try to do a nonlinear fit
    try:
        ba, var_ba = scipy.optimize.curve_fit(f, x_in, y_in, p0=ba0)
    except RuntimeError: # minimization failure
        return {"extra0": r0}
    # chi-squared value per degree of freedom (using weight = 1)
    badness = (np.sum((f(x_in, *ba) - y_in) ** 2) / (len(x_in) - len(ba)))
    r = {
        "fit_type": fit_type,
        "badness": badness,
    }
    r.update(params)
    for i, name in enumerate(names):
        r[name] = ba[i]
        r[name + "_err"] = var_ba[i, i] ** 0.5
        for j, name2 in enumerate(names[(i + 1):]):
            r["cov_{}_{}".format(name, name2)] = var_ba[i, j]

    return {"x": x, "y": f(x, *ba), "extra0": r0, "extra": r}
