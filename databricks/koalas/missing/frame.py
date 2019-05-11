#
# Copyright (C) 2019 Databricks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from databricks.koalas.missing import _unsupported_function, _unsupported_property


def unsupported_function(method_name):
    return _unsupported_function(class_name='pd.DataFrame', method_name=method_name)


def unsupported_property(property_name):
    return _unsupported_property(class_name='pd.DataFrame', property_name=property_name)


class _MissingPandasLikeDataFrame(object):

    # Properties
    T = unsupported_property('T')
    at = unsupported_property('at')
    axes = unsupported_property('axes')
    blocks = unsupported_property('blocks')
    empty = unsupported_property('empty')
    ftypes = unsupported_property('ftypes')
    iat = unsupported_property('iat')
    iloc = unsupported_property('iloc')
    is_copy = unsupported_property('is_copy')
    ix = unsupported_property('ix')
    ndim = unsupported_property('ndim')
    size = unsupported_property('size')
    style = unsupported_property('style')
    values = unsupported_property('values')

    # Functions
    add = unsupported_function('add')
    add_prefix = unsupported_function('add_prefix')
    add_suffix = unsupported_function('add_suffix')
    align = unsupported_function('align')
    all = unsupported_function('all')
    any = unsupported_function('any')
    append = unsupported_function('append')
    apply = unsupported_function('apply')
    applymap = unsupported_function('applymap')
    as_blocks = unsupported_function('as_blocks')
    as_matrix = unsupported_function('as_matrix')
    asfreq = unsupported_function('asfreq')
    asof = unsupported_function('asof')
    astype = unsupported_function('astype')
    at_time = unsupported_function('at_time')
    between_time = unsupported_function('between_time')
    bfill = unsupported_function('bfill')
    bool = unsupported_function('bool')
    boxplot = unsupported_function('boxplot')
    clip = unsupported_function('clip')
    clip_lower = unsupported_function('clip_lower')
    clip_upper = unsupported_function('clip_upper')
    combine = unsupported_function('combine')
    combine_first = unsupported_function('combine_first')
    compound = unsupported_function('compound')
    convert_objects = unsupported_function('convert_objects')
    corrwith = unsupported_function('corrwith')
    cov = unsupported_function('cov')
    cummax = unsupported_function('cummax')
    cummin = unsupported_function('cummin')
    cumprod = unsupported_function('cumprod')
    cumsum = unsupported_function('cumsum')
    describe = unsupported_function('describe')
    diff = unsupported_function('diff')
    div = unsupported_function('div')
    divide = unsupported_function('divide')
    dot = unsupported_function('dot')
    drop_duplicates = unsupported_function('drop_duplicates')
    droplevel = unsupported_function('droplevel')
    duplicated = unsupported_function('duplicated')
    eq = unsupported_function('eq')
    equals = unsupported_function('equals')
    eval = unsupported_function('eval')
    ewm = unsupported_function('ewm')
    expanding = unsupported_function('expanding')
    ffill = unsupported_function('ffill')
    filter = unsupported_function('filter')
    first = unsupported_function('first')
    first_valid_index = unsupported_function('first_valid_index')
    floordiv = unsupported_function('floordiv')
    ge = unsupported_function('ge')
    get_dtype_counts = unsupported_function('get_dtype_counts')
    get_ftype_counts = unsupported_function('get_ftype_counts')
    get_value = unsupported_function('get_value')
    get_values = unsupported_function('get_values')
    gt = unsupported_function('gt')
    hist = unsupported_function('hist')
    idxmax = unsupported_function('idxmax')
    idxmin = unsupported_function('idxmin')
    infer_objects = unsupported_function('infer_objects')
    info = unsupported_function('info')
    insert = unsupported_function('insert')
    interpolate = unsupported_function('interpolate')
    items = unsupported_function('items')
    iterrows = unsupported_function('iterrows')
    itertuples = unsupported_function('itertuples')
    join = unsupported_function('join')
    keys = unsupported_function('keys')
    last = unsupported_function('last')
    last_valid_index = unsupported_function('last_valid_index')
    le = unsupported_function('le')
    lookup = unsupported_function('lookup')
    lt = unsupported_function('lt')
    mad = unsupported_function('mad')
    mask = unsupported_function('mask')
    median = unsupported_function('median')
    melt = unsupported_function('melt')
    memory_usage = unsupported_function('memory_usage')
    mod = unsupported_function('mod')
    mode = unsupported_function('mode')
    mul = unsupported_function('mul')
    multiply = unsupported_function('multiply')
    ne = unsupported_function('ne')
    nlargest = unsupported_function('nlargest')
    nsmallest = unsupported_function('nsmallest')
    nunique = unsupported_function('nunique')
    pct_change = unsupported_function('pct_change')
    pivot = unsupported_function('pivot')
    pivot_table = unsupported_function('pivot_table')
    pop = unsupported_function('pop')
    pow = unsupported_function('pow')
    prod = unsupported_function('prod')
    product = unsupported_function('product')
    quantile = unsupported_function('quantile')
    query = unsupported_function('query')
    radd = unsupported_function('radd')
    rank = unsupported_function('rank')
    rdiv = unsupported_function('rdiv')
    reindex = unsupported_function('reindex')
    reindex_axis = unsupported_function('reindex_axis')
    reindex_like = unsupported_function('reindex_like')
    rename = unsupported_function('rename')
    rename_axis = unsupported_function('rename_axis')
    reorder_levels = unsupported_function('reorder_levels')
    replace = unsupported_function('replace')
    resample = unsupported_function('resample')
    rfloordiv = unsupported_function('rfloordiv')
    rmod = unsupported_function('rmod')
    rmul = unsupported_function('rmul')
    rolling = unsupported_function('rolling')
    round = unsupported_function('round')
    rpow = unsupported_function('rpow')
    rsub = unsupported_function('rsub')
    rtruediv = unsupported_function('rtruediv')
    sample = unsupported_function('sample')
    select = unsupported_function('select')
    select_dtypes = unsupported_function('select_dtypes')
    sem = unsupported_function('sem')
    set_axis = unsupported_function('set_axis')
    set_value = unsupported_function('set_value')
    shift = unsupported_function('shift')
    slice_shift = unsupported_function('slice_shift')
    sort_index = unsupported_function('sort_index')
    squeeze = unsupported_function('squeeze')
    stack = unsupported_function('stack')
    sub = unsupported_function('sub')
    subtract = unsupported_function('subtract')
    swapaxes = unsupported_function('swapaxes')
    swaplevel = unsupported_function('swaplevel')
    tail = unsupported_function('tail')
    take = unsupported_function('take')
    to_clipboard = unsupported_function('to_clipboard')
    to_csv = unsupported_function('to_csv')
    to_dense = unsupported_function('to_dense')
    to_feather = unsupported_function('to_feather')
    to_gbq = unsupported_function('to_gbq')
    to_hdf = unsupported_function('to_hdf')
    to_json = unsupported_function('to_json')
    to_latex = unsupported_function('to_latex')
    to_msgpack = unsupported_function('to_msgpack')
    to_panel = unsupported_function('to_panel')
    to_parquet = unsupported_function('to_parquet')
    to_period = unsupported_function('to_period')
    to_pickle = unsupported_function('to_pickle')
    to_records = unsupported_function('to_records')
    to_sparse = unsupported_function('to_sparse')
    to_sql = unsupported_function('to_sql')
    to_stata = unsupported_function('to_stata')
    to_timestamp = unsupported_function('to_timestamp')
    to_xarray = unsupported_function('to_xarray')
    transform = unsupported_function('transform')
    transpose = unsupported_function('transpose')
    truediv = unsupported_function('truediv')
    truncate = unsupported_function('truncate')
    tshift = unsupported_function('tshift')
    tz_convert = unsupported_function('tz_convert')
    tz_localize = unsupported_function('tz_localize')
    unstack = unsupported_function('unstack')
    update = unsupported_function('update')
    where = unsupported_function('where')
    xs = unsupported_function('xs')
