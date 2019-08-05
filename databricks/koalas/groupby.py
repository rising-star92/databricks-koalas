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

"""
A wrapper for GroupedData to behave similar to pandas GroupBy.
"""

import inspect
from collections import Callable
from functools import partial
from typing import Any, List

import numpy as np
import pandas as pd
from pandas._libs.parsers import is_datetime64_dtype
from pandas.core.dtypes.common import is_datetime64tz_dtype

from pyspark.sql import functions as F, Window
from pyspark.sql.types import FloatType, DoubleType, NumericType, StructField, StructType
from pyspark.sql.functions import PandasUDFType, pandas_udf

from databricks import koalas as ks  # For running doctests and reference resolution in PyCharm.
from databricks.koalas.typedef import _infer_return_type
from databricks.koalas.frame import DataFrame
from databricks.koalas.internal import _InternalFrame
from databricks.koalas.missing.groupby import _MissingPandasLikeDataFrameGroupBy, \
    _MissingPandasLikeSeriesGroupBy
from databricks.koalas.series import Series, _col


class GroupBy(object):
    """
    :ivar _kdf: The parent dataframe that is used to perform the groupby
    :type _kdf: DataFrame
    :ivar _groupkeys: The list of keys that will be used to perform the grouping
    :type _groupkeys: List[Series]
    """

    # TODO: Series support is not implemented yet.
    # TODO: not all arguments are implemented comparing to Pandas' for now.
    def aggregate(self, func_or_funcs, *args, **kwargs):
        """Aggregate using one or more operations over the specified axis.

        Parameters
        ----------
        func : dict
             a dict mapping from column name (string) to
             aggregate functions (string or list of strings).

        Returns
        -------
        Series or DataFrame

            The return can be:

            * Series : when DataFrame.agg is called with a single function
            * DataFrame : when DataFrame.agg is called with several functions

            Return Series or DataFrame.

        Notes
        -----
        `agg` is an alias for `aggregate`. Use the alias.

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby

        Examples
        --------
        >>> df = ks.DataFrame({'A': [1, 1, 2, 2],
        ...                    'B': [1, 2, 3, 4],
        ...                    'C': [0.362, 0.227, 1.267, -0.562]},
        ...                   columns=['A', 'B', 'C'])

        >>> df
           A  B      C
        0  1  1  0.362
        1  1  2  0.227
        2  2  3  1.267
        3  2  4 -0.562

        Different aggregations per column

        >>> aggregated = df.groupby('A').agg({'B': 'min', 'C': 'sum'})
        >>> aggregated[['B', 'C']]  # doctest: +NORMALIZE_WHITESPACE
           B      C
        A
        1  1  0.589
        2  3  0.705

        >>> aggregated = df.groupby('A').agg({'B': ['min', 'max']})
        >>> aggregated  # doctest: +NORMALIZE_WHITESPACE
             B
           min  max
        A
        1    1    2
        2    3    4

        """
        if not isinstance(func_or_funcs, dict) or \
                not all(isinstance(key, str) and
                        (isinstance(value, str) or
                         isinstance(value, list) and all(isinstance(v, str) for v in value))
                        for key, value in func_or_funcs.items()):
            raise ValueError("aggs must be a dict mapping from column name (string) to aggregate "
                             "functions (string or list of strings).")

        sdf = self._kdf._sdf
        groupkeys = self._groupkeys
        groupkey_cols = [s._scol.alias('__index_level_{}__'.format(i))
                         for i, s in enumerate(groupkeys)]
        multi_aggs = any(isinstance(v, list) for v in func_or_funcs.values())
        reordered = []
        data_columns = []
        column_index = []
        for key, value in func_or_funcs.items():
            for aggfunc in [value] if isinstance(value, str) else value:
                data_col = "('{0}', '{1}')".format(key, aggfunc) if multi_aggs else key
                data_columns.append(data_col)
                column_index.append((key, aggfunc))
                if aggfunc == "nunique":
                    reordered.append(F.expr('count(DISTINCT `{0}`) as `{1}`'.format(key, data_col)))
                else:
                    reordered.append(F.expr('{1}(`{0}`) as `{2}`'.format(key, aggfunc, data_col)))
        sdf = sdf.groupby(*groupkey_cols).agg(*reordered)
        internal = _InternalFrame(sdf=sdf,
                                  data_columns=data_columns,
                                  column_index=column_index if multi_aggs else None,
                                  index_map=[('__index_level_{}__'.format(i), s.name)
                                             for i, s in enumerate(groupkeys)])
        return DataFrame(internal)

    agg = aggregate

    def count(self):
        """
        Compute count of group, excluding missing values.

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby

        Examples
        --------
        >>> df = ks.DataFrame({'A': [1, 1, 2, 1, 2],
        ...                    'B': [np.nan, 2, 3, 4, 5],
        ...                    'C': [1, 2, 1, 1, 2]}, columns=['A', 'B', 'C'])
        >>> df.groupby('A').count()  # doctest: +NORMALIZE_WHITESPACE
            B  C
        A
        1  2  3
        2  2  2
        """
        return self._reduce_for_stat_function(F.count, only_numeric=False)

    # TODO: We should fix See Also when Series implementation is finished.
    def first(self):
        """
        Compute first of group values.

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby
        """
        return self._reduce_for_stat_function(F.first, only_numeric=False)

    def last(self):
        """
        Compute last of group values.

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby
        """
        return self._reduce_for_stat_function(lambda col: F.last(col, ignorenulls=True),
                                              only_numeric=False)

    def max(self):
        """
        Compute max of group values.

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby
        """
        return self._reduce_for_stat_function(F.max, only_numeric=False)

    # TODO: examples should be updated.
    def mean(self):
        """
        Compute mean of groups, excluding missing values.

        Returns
        -------
        koalas.Series or koalas.DataFrame

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby

        Examples
        --------
        >>> df = ks.DataFrame({'A': [1, 1, 2, 1, 2],
        ...                    'B': [np.nan, 2, 3, 4, 5],
        ...                    'C': [1, 2, 1, 1, 2]}, columns=['A', 'B', 'C'])

        Groupby one column and return the mean of the remaining columns in
        each group.

        >>> df.groupby('A').mean()  # doctest: +NORMALIZE_WHITESPACE
             B         C
        A
        1  3.0  1.333333
        2  4.0  1.500000
        """

        return self._reduce_for_stat_function(F.mean, only_numeric=True)

    def min(self):
        """
        Compute min of group values.

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby
        """
        return self._reduce_for_stat_function(F.min, only_numeric=False)

    # TODO: sync the doc and implement `ddof`.
    def std(self):
        """
        Compute standard deviation of groups, excluding missing values.

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby
        """

        return self._reduce_for_stat_function(F.stddev, only_numeric=True)

    def sum(self):
        """
        Compute sum of group values

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby
        """
        return self._reduce_for_stat_function(F.sum, only_numeric=True)

    # TODO: sync the doc and implement `ddof`.
    def var(self):
        """
        Compute variance of groups, excluding missing values.

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby
        """
        return self._reduce_for_stat_function(F.variance, only_numeric=True)

    # TODO: skipna should be implemented.
    def all(self):
        """
        Returns True if all values in the group are truthful, else False.

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby

        Examples
        --------
        >>> df = ks.DataFrame({'A': [1, 1, 2, 2, 3, 3, 4, 4, 5, 5],
        ...                    'B': [True, True, True, False, False,
        ...                          False, None, True, None, False]},
        ...                   columns=['A', 'B'])
        >>> df
           A      B
        0  1   True
        1  1   True
        2  2   True
        3  2  False
        4  3  False
        5  3  False
        6  4   None
        7  4   True
        8  5   None
        9  5  False

        >>> df.groupby('A').all()  # doctest: +NORMALIZE_WHITESPACE
               B
        A
        1   True
        2  False
        3  False
        4   True
        5  False
        """
        return self._reduce_for_stat_function(
            lambda col: F.min(F.coalesce(col.cast('boolean'), F.lit(True))),
            only_numeric=False)

    # TODO: skipna should be implemented.
    def any(self):
        """
        Returns True if any value in the group is truthful, else False.

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby

        Examples
        --------
        >>> df = ks.DataFrame({'A': [1, 1, 2, 2, 3, 3, 4, 4, 5, 5],
        ...                    'B': [True, True, True, False, False,
        ...                          False, None, True, None, False]},
        ...                   columns=['A', 'B'])
        >>> df
           A      B
        0  1   True
        1  1   True
        2  2   True
        3  2  False
        4  3  False
        5  3  False
        6  4   None
        7  4   True
        8  5   None
        9  5  False

        >>> df.groupby('A').any()  # doctest: +NORMALIZE_WHITESPACE
               B
        A
        1   True
        2   True
        3  False
        4   True
        5  False
        """
        return self._reduce_for_stat_function(
            lambda col: F.max(F.coalesce(col.cast('boolean'), F.lit(False))),
            only_numeric=False)

    # TODO: groupby multiply columuns should be implemented.
    def size(self):
        """
        Compute group sizes.

        See Also
        --------
        databricks.koalas.Series.groupby
        databricks.koalas.DataFrame.groupby

        Examples
        --------
        >>> df = ks.DataFrame({'A': [1, 2, 2, 3, 3, 3],
        ...                    'B': [1, 1, 2, 3, 3, 3]},
        ...                   columns=['A', 'B'])
        >>> df
           A  B
        0  1  1
        1  2  1
        2  2  2
        3  3  3
        4  3  3
        5  3  3

        >>> df.groupby('A').size().sort_index()  # doctest: +NORMALIZE_WHITESPACE
        A
        1  1
        2  2
        3  3
        Name: count, dtype: int64

        >>> df.groupby(['A', 'B']).size().sort_index()  # doctest: +NORMALIZE_WHITESPACE
        A  B
        1  1    1
        2  1    1
           2    1
        3  3    3
        Name: count, dtype: int64
        """
        groupkeys = self._groupkeys
        groupkey_cols = [s._scol.alias('__index_level_{}__'.format(i))
                         for i, s in enumerate(groupkeys)]
        sdf = self._kdf._sdf
        sdf = sdf.groupby(*groupkey_cols).count()
        if (len(self._agg_columns) > 0) and (self._have_agg_columns):
            name = self._agg_columns[0].name
            sdf = sdf.withColumnRenamed('count', name)
        else:
            name = 'count'
        internal = _InternalFrame(sdf=sdf,
                                  data_columns=[name],
                                  index_map=[('__index_level_{}__'.format(i), s.name)
                                             for i, s in enumerate(groupkeys)])
        return _col(DataFrame(internal))

    def cummax(self):
        """
        Cumulative max for each group.

        Returns
        -------
        Series or DataFrame

        See Also
        --------
        Series.cummax
        DataFrame.cummax

        Examples
        --------
        >>> df = ks.DataFrame(
        ...     [[1, None, 4], [1, 0.1, 3], [1, 20.0, 2], [4, 10.0, 1]],
        ...     columns=list('ABC'))
        >>> df
           A     B  C
        0  1   NaN  4
        1  1   0.1  3
        2  1  20.0  2
        3  4  10.0  1

        By default, iterates over rows and finds the sum in each column.

        >>> df.groupby("A").cummax()
              B  C
        0   NaN  4
        1   0.1  4
        2  20.0  4
        3  10.0  1

        It works as below in Series.

        >>> df.C.groupby(df.A).cummax()
        0    4
        1    4
        2    4
        3    1
        Name: C, dtype: int64

        """

        return self._cum(F.max)

    def cummin(self):
        """
        Cumulative min for each group.

        Returns
        -------
        Series or DataFrame

        See Also
        --------
        Series.cummin
        DataFrame.cummin

        Examples
        --------
        >>> df = ks.DataFrame(
        ...     [[1, None, 4], [1, 0.1, 3], [1, 20.0, 2], [4, 10.0, 1]],
        ...     columns=list('ABC'))
        >>> df
           A     B  C
        0  1   NaN  4
        1  1   0.1  3
        2  1  20.0  2
        3  4  10.0  1

        By default, iterates over rows and finds the sum in each column.

        >>> df.groupby("A").cummin()
              B  C
        0   NaN  4
        1   0.1  3
        2   0.1  2
        3  10.0  1

        It works as below in Series.

        >>> df.B.groupby(df.A).cummin()
        0     NaN
        1     0.1
        2     0.1
        3    10.0
        Name: B, dtype: float64
        """
        return self._cum(F.min)

    def cumprod(self):
        """
        Cumulative product for each group.

        Returns
        -------
        Series or DataFrame

        See Also
        --------
        Series.cumprod
        DataFrame.cumprod

        Examples
        --------
        >>> df = ks.DataFrame(
        ...     [[1, None, 4], [1, 0.1, 3], [1, 20.0, 2], [4, 10.0, 1]],
        ...     columns=list('ABC'))
        >>> df
           A     B  C
        0  1   NaN  4
        1  1   0.1  3
        2  1  20.0  2
        3  4  10.0  1

        By default, iterates over rows and finds the sum in each column.

        >>> df.groupby("A").cumprod()
              B     C
        0   NaN   4.0
        1   0.1  12.0
        2   2.0  24.0
        3  10.0   1.0

        It works as below in Series.

        >>> df.B.groupby(df.A).cumprod()
        0     NaN
        1     0.1
        2     2.0
        3    10.0
        Name: B, dtype: float64

        """
        from pyspark.sql.functions import pandas_udf

        def cumprod(scol):
            # Note that this function will always actually called via `SeriesGroupBy._cum`,
            # and `Series._cum`.
            # In case of `DataFrameGroupBy`, it gose through `DataFrameGroupBy._cum`,
            # `SeriesGroupBy.comprod`, `SeriesGroupBy._cum` and `Series._cum`
            #
            # This is a bit hacky. Maybe we should fix it.
            @pandas_udf(returnType=self._ks._kdf._internal.spark_type_for(self._ks.name))
            def negative_check(s):
                assert len(s) == 0 or ((s > 0) | (s.isnull())).all(), \
                    "values should be bigger than 0: %s" % s
                return s

            return F.sum(F.log(negative_check(scol)))

        return self._cum(cumprod)

    def cumsum(self):
        """
        Cumulative sum for each group.

        Returns
        -------
        Series or DataFrame

        See Also
        --------
        Series.cumsum
        DataFrame.cumsum

        Examples
        --------
        >>> df = ks.DataFrame(
        ...     [[1, None, 4], [1, 0.1, 3], [1, 20.0, 2], [4, 10.0, 1]],
        ...     columns=list('ABC'))
        >>> df
           A     B  C
        0  1   NaN  4
        1  1   0.1  3
        2  1  20.0  2
        3  4  10.0  1

        By default, iterates over rows and finds the sum in each column.

        >>> df.groupby("A").cumsum()
              B  C
        0   NaN  4
        1   0.1  7
        2  20.1  9
        3  10.0  1

        It works as below in Series.

        >>> df.B.groupby(df.A).cumsum()
        0     NaN
        1     0.1
        2    20.1
        3    10.0
        Name: B, dtype: float64

        """
        return self._cum(F.sum)

    # TODO: Series support is not implemented yet.
    def apply(self, func):
        """
        Apply function `func` group-wise and combine the results together.

        The function passed to `apply` must take a DataFrame as its first
        argument and return a DataFrame. `apply` will
        then take care of combining the results back together into a single
        dataframe. `apply` is therefore a highly flexible
        grouping method.

        While `apply` is a very flexible method, its downside is that
        using it can be quite a bit slower than using more specific methods
        like `agg` or `transform`. Koalas offers a wide range of method that will
        be much faster than using `apply` for their specific purposes, so try to
        use them before reaching for `apply`.

        .. note:: unlike pandas, it is required for ``func`` to specify return type hint.

        .. note:: the output column names are `c0, c1, c2 ... cn`. These names
            are positionally mapped to the returned DataFrame in ``func``. See examples below.

        .. note:: the dataframe within ``func`` is actually a pandas dataframe. Therefore,
            any pandas APIs within this function is allowed.

        Parameters
        ----------
        func : callable
            A callable that takes a DataFrame as its first argument, and
            returns a dataframe.

        Returns
        -------
        applied : DataFrame

        See Also
        --------
        aggregate : Apply aggregate function to the GroupBy object.
        Series.apply : Apply a function to a Series.

        Examples
        --------
        >>> df = ks.DataFrame({'A': 'a a b'.split(),
        ...                    'B': [1, 2, 3],
        ...                    'C': [4, 6, 5]}, columns=['A', 'B', 'C'])
        >>> g = df.groupby('A')

        Notice that ``g`` has two groups, ``a`` and ``b``.
        Calling `apply` in various ways, we can get different grouping results:

        Below the functions passed to `apply` takes a DataFrame as
        its argument and returns a DataFrame. `apply` combines the result for
        each group together into a new DataFrame:

        >>> def pandas_div_sum(x) -> ks.DataFrame[float, float]:
        ...    return x[['B', 'C']] / x[['B', 'C']].sum()
        >>> g.apply(pandas_div_sum)  # doctest: +NORMALIZE_WHITESPACE
                 c0   c1
        0  1.000000  1.0
        1  0.333333  0.4
        2  0.666667  0.6

        >>> def plus_max(x) -> ks.DataFrame[str, np.int, np.int]:
        ...    return x + x.max()
        >>> g.apply(plus_max)  # doctest: +NORMALIZE_WHITESPACE
           c0  c1  c2
        0  bb   6  10
        1  aa   3  10
        2  aa   4  12

        In case of Series, it works as below.

        >>> def plus_max(x) -> ks.Series[np.int]:
        ...    return x + x.max()
        >>> df.B.groupby(df.A).apply(plus_max)
        0    6
        1    3
        2    4
        Name: B, dtype: int32
        """
        if not isinstance(func, Callable):
            raise TypeError("%s object is not callable" % type(func))

        assert callable(func), "the first argument should be a callable function."
        spec = inspect.getfullargspec(func)
        return_sig = spec.annotations.get("return", None)
        if return_sig is None:
            raise ValueError("Given function must have return type hint; however, not found.")

        return_schema = _infer_return_type(func).tpe
        return self._apply(func, return_schema)

    # TODO: implement 'dropna' parameter
    def filter(self, func):
        """
        Return a copy of a DataFrame excluding elements from groups that
        do not satisfy the boolean criterion specified by func.

        Parameters
        ----------
        f : function
            Function to apply to each subframe. Should return True or False.
        dropna : Drop groups that do not pass the filter. True by default;
            if False, groups that evaluate False are filled with NaNs.

        Returns
        -------
        filtered : DataFrame

        Notes
        -----
        Each subframe is endowed the attribute 'name' in case you need to know
        which group you are working on.

        Examples
        --------
        >>> df = ks.DataFrame({'A' : ['foo', 'bar', 'foo', 'bar',
        ...                           'foo', 'bar'],
        ...                    'B' : [1, 2, 3, 4, 5, 6],
        ...                    'C' : [2.0, 5., 8., 1., 2., 9.]}, columns=['A', 'B', 'C'])
        >>> grouped = df.groupby('A')
        >>> grouped.filter(lambda x: x['B'].mean() > 3.)
             A  B    C
        1  bar  2  5.0
        3  bar  4  1.0
        5  bar  6  9.0
        """
        if not isinstance(func, Callable):
            raise TypeError("%s object is not callable" % type(func))

        data_schema = self._kdf._sdf.schema
        groupby_names = [s.name for s in self._groupkeys]

        def pandas_filter(pdf):
            pdf = pdf.groupby(*groupby_names).filter(func)

            # Here, we restore the index column back in Spark DataFrame
            # so that Koalas can understand it as an index.

            # TODO: deduplicate this logic with _InternalFrame.from_pandas
            columns = pdf.columns
            data_columns = [str(col) for col in columns]

            index = pdf.index

            index_map = []
            if isinstance(index, pd.MultiIndex):
                if index.names is None:
                    index_map = [('__index_level_{}__'.format(i), None)
                                 for i in range(len(index.levels))]
                else:
                    index_map = [('__index_level_{}__'.format(i) if name is None else name, name)
                                 for i, name in enumerate(index.names)]
            else:
                index_map = [(index.name
                              if index.name is not None else '__index_level_0__', index.name)]

            index_columns = [index_column for index_column, _ in index_map]

            reset_index = pdf.reset_index()
            reset_index.columns = index_columns + data_columns
            for name, col in reset_index.iteritems():
                dt = col.dtype
                if is_datetime64_dtype(dt) or is_datetime64tz_dtype(dt):
                    continue
                reset_index[name] = col.replace({np.nan: None})
            return reset_index

        # DataFrame.apply loses the index. We should restore the original index column information
        # below.
        no_index_df = self._apply(pandas_filter, data_schema)
        return DataFrame(self._kdf._internal.copy(sdf=no_index_df._sdf))

    def _apply(self, func, return_schema):
        index_columns = self._kdf._internal.index_columns
        index_names = self._kdf._internal.index_names
        data_columns = self._kdf._internal.data_columns

        def rename_output(pdf):
            # TODO: This logic below was borrowed from `DataFrame.pandas_df` to set the index
            #   within each pdf properly. we might have to deduplicate it.
            import pandas as pd

            if len(index_columns) > 0:
                append = False
                for index_field in index_columns:
                    drop = index_field not in data_columns
                    pdf = pdf.set_index(index_field, drop=drop, append=append)
                    append = True
                pdf = pdf[data_columns]

            if len(index_names) > 0:
                if isinstance(pdf.index, pd.MultiIndex):
                    pdf.index.names = index_names
                else:
                    pdf.index.name = index_names[0]

            pdf = func(pdf)
            # For now, just positionally map the column names to given schema's.
            pdf = pdf.rename(columns=dict(zip(pdf.columns, return_schema.fieldNames())))
            return pdf

        grouped_map_func = pandas_udf(return_schema, PandasUDFType.GROUPED_MAP)(rename_output)

        sdf = self._kdf._sdf
        input_groupkeys = [s._scol for s in self._groupkeys]
        sdf = sdf.groupby(*input_groupkeys).apply(grouped_map_func)
        internal = _InternalFrame(
            sdf=sdf, data_columns=return_schema.fieldNames(), index_map=[])  # index is lost.
        return DataFrame(internal)

    # TODO: Series support is not implemented yet.
    def transform(self, func):
        """
        Apply function column-by-column to the GroupBy object.

        The function passed to `transform` must take a Series as its first
        argument and return a Series. The given function is executed for
        each series in each grouped data.

        While `transform` is a very flexible method, its downside is that
        using it can be quite a bit slower than using more specific methods
        like `agg` or `transform`. Koalas offers a wide range of method that will
        be much faster than using `transform` for their specific purposes, so try to
        use them before reaching for `transform`.

        .. note:: unlike pandas, it is required for ``func`` to specify return type hint.

        .. note:: the series within ``func`` is actually a pandas series. Therefore,
            any pandas APIs within this function is allowed.

        Parameters
        ----------
        func : callable
            A callable that takes a Series as its first argument, and
            returns a Series.

        Returns
        -------
        applied : DataFrame

        See Also
        --------
        aggregate : Apply aggregate function to the GroupBy object.
        Series.apply : Apply a function to a Series.

        Examples
        --------

        >>> df = ks.DataFrame({'A': [0, 0, 1],
        ...                    'B': [1, 2, 3],
        ...                    'C': [4, 6, 5]}, columns=['A', 'B', 'C'])

        >>> g = df.groupby('A')

        Notice that ``g`` has two groups, ``0`` and ``1``.
        Calling `transform` in various ways, we can get different grouping results:
        Below the functions passed to `transform` takes a Series as
        its argument and returns a Series. `transform` applies the function on each series
        in each grouped data, and combine them into a new DataFrame:

        >>> def convert_to_string(x) -> ks.Series[str]:
        ...    return x.apply("a string {}".format)
        >>> g.transform(convert_to_string)  # doctest: +NORMALIZE_WHITESPACE
                    B           C
        0  a string 1  a string 4
        1  a string 2  a string 6
        2  a string 3  a string 5

        >>> def plus_max(x) -> ks.Series[np.int]:
        ...    return x + x.max()
        >>> g.transform(plus_max)  # doctest: +NORMALIZE_WHITESPACE
           B   C
        0  3  10
        1  4  12
        2  6  10

        In case of Series, it works as below.

        >>> df.B.groupby(df.A).transform(plus_max)
        0    3
        1    4
        2    6
        Name: B, dtype: int32
        """
        # TODO: codes here are similar with GroupBy.apply. Needs to deduplicate.
        if not isinstance(func, Callable):
            raise TypeError("%s object is not callable" % type(func))

        assert callable(func), "the first argument should be a callable function."
        spec = inspect.getfullargspec(func)
        return_sig = spec.annotations.get("return", None)
        if return_sig is None:
            raise ValueError("Given function must have return type hint; however, not found.")

        return_type = _infer_return_type(func).tpe
        input_groupnames = [s.name for s in self._groupkeys]
        data_columns = self._kdf._internal.data_columns
        return_schema = StructType([
            StructField(c, return_type) for c in data_columns if c not in input_groupnames])

        index_columns = self._kdf._internal.index_columns
        index_names = self._kdf._internal.index_names
        data_columns = self._kdf._internal.data_columns

        def rename_output(pdf):
            # TODO: This logic below was borrowed from `DataFrame.pandas_df` to set the index
            #   within each pdf properly. we might have to deduplicate it.
            import pandas as pd

            if len(index_columns) > 0:
                append = False
                for index_field in index_columns:
                    drop = index_field not in data_columns
                    pdf = pdf.set_index(index_field, drop=drop, append=append)
                    append = True
                pdf = pdf[data_columns]

            if len(index_names) > 0:
                if isinstance(pdf.index, pd.MultiIndex):
                    pdf.index.names = index_names
                else:
                    pdf.index.name = index_names[0]

            # pandas GroupBy.transform drops grouping columns.
            pdf = pdf.drop(columns=input_groupnames)
            pdf = pdf.transform(func)
            # Remaps to the original name, positionally.
            pdf = pdf.rename(columns=dict(zip(pdf.columns, return_schema.fieldNames())))
            return pdf

        grouped_map_func = pandas_udf(return_schema, PandasUDFType.GROUPED_MAP)(rename_output)

        sdf = self._kdf._sdf
        input_groupkeys = [s._scol for s in self._groupkeys]
        sdf = sdf.groupby(*input_groupkeys).apply(grouped_map_func)
        internal = _InternalFrame(
            sdf=sdf, data_columns=return_schema.fieldNames(), index_map=[])  # index is lost.
        return DataFrame(internal)

    def _reduce_for_stat_function(self, sfun, only_numeric):
        groupkeys = self._groupkeys
        groupkey_cols = [s._scol.alias('__index_level_{}__'.format(i))
                         for i, s in enumerate(groupkeys)]
        sdf = self._kdf._sdf

        data_columns = []
        if len(self._agg_columns) > 0:
            stat_exprs = []
            for ks in self._agg_columns:
                spark_type = ks.spark_type
                # TODO: we should have a function that takes dataframes and converts the numeric
                # types. Converting the NaNs is used in a few places, it should be in utils.
                # Special handle floating point types because Spark's count treats nan as a valid
                # value, whereas Pandas count doesn't include nan.
                if isinstance(spark_type, DoubleType) or isinstance(spark_type, FloatType):
                    stat_exprs.append(sfun(F.nanvl(ks._scol, F.lit(None))).alias(ks.name))
                    data_columns.append(ks.name)
                elif isinstance(spark_type, NumericType) or not only_numeric:
                    stat_exprs.append(sfun(ks._scol).alias(ks.name))
                    data_columns.append(ks.name)
            sdf = sdf.groupby(*groupkey_cols).agg(*stat_exprs)
        else:
            sdf = sdf.select(*groupkey_cols).distinct()
        sdf = sdf.sort(*groupkey_cols)
        internal = _InternalFrame(sdf=sdf,
                                  data_columns=data_columns,
                                  index_map=[('__index_level_{}__'.format(i), s.name)
                                             for i, s in enumerate(groupkeys)])
        return DataFrame(internal)


class DataFrameGroupBy(GroupBy):

    def __init__(self, kdf: DataFrame, by: List[Series], agg_columns: List[str] = None):
        self._kdf = kdf
        self._groupkeys = by
        self._have_agg_columns = True

        if agg_columns is None:
            groupkey_names = set(s.name for s in self._groupkeys)
            agg_columns = [col for col in self._kdf._internal.data_columns
                           if col not in groupkey_names]
            self._have_agg_columns = False
        self._agg_columns = [kdf[col] for col in agg_columns]

    def __getattr__(self, item: str) -> Any:
        if hasattr(_MissingPandasLikeDataFrameGroupBy, item):
            property_or_func = getattr(_MissingPandasLikeDataFrameGroupBy, item)
            if isinstance(property_or_func, property):
                return property_or_func.fget(self)  # type: ignore
            else:
                return partial(property_or_func, self)
        return self.__getitem__(item)

    def __getitem__(self, item):
        if isinstance(item, str):
            return SeriesGroupBy(self._kdf[item], self._groupkeys)
        else:
            # TODO: check that item is a list of strings
            return DataFrameGroupBy(self._kdf, self._groupkeys, item)

    def _cum(self, func):
        # This is used for cummin, cummax, cumxum, etc.
        if func == F.min:
            func = "cummin"
        elif func == F.max:
            func = "cummax"
        elif func == F.sum:
            func = "cumsum"
        elif func.__name__ == "cumprod":
            func = "cumprod"

        if len(self._kdf._internal.index_columns) == 0:
            raise ValueError("Index must be set.")

        applied = []
        kdf = self._kdf
        groupkey_columns = [s.name for s in self._groupkeys]
        for column in kdf._internal.data_columns:
            # pandas groupby.cumxxx ignores the grouping key itself.
            if column not in groupkey_columns:
                applied.append(getattr(kdf[column].groupby(self._groupkeys), func)())

        sdf = kdf._sdf.select(
            kdf._internal.index_scols + [c._scol for c in applied])
        internal = kdf._internal.copy(sdf=sdf, data_columns=[c.name for c in applied])
        return DataFrame(internal)


class SeriesGroupBy(GroupBy):

    def __init__(self, ks: Series, by: List[Series]):
        self._ks = ks
        self._groupkeys = by
        self._have_agg_columns = True

    def __getattr__(self, item: str) -> Any:
        if hasattr(_MissingPandasLikeSeriesGroupBy, item):
            property_or_func = getattr(_MissingPandasLikeSeriesGroupBy, item)
            if isinstance(property_or_func, property):
                return property_or_func.fget(self)  # type: ignore
            else:
                return partial(property_or_func, self)
        raise AttributeError(item)

    def _cum(self, func):
        groupkey_scols = [s._scol for s in self._groupkeys]
        return Series._cum(self._ks, func, True, part_cols=groupkey_scols)

    @property
    def _kdf(self) -> DataFrame:
        return self._ks._kdf

    @property
    def _agg_columns(self):
        return [self._ks]

    def _reduce_for_stat_function(self, sfun, only_numeric):
        return _col(super(SeriesGroupBy, self)._reduce_for_stat_function(sfun, only_numeric))

    def agg(self, func_or_funcs, *args, **kwargs):
        raise NotImplementedError()

    def aggregate(self, func_or_funcs, *args, **kwargs):
        raise NotImplementedError()

    def apply(self, func):
        return _col(super(SeriesGroupBy, self).transform(func))

    apply.__doc__ = GroupBy.transform.__doc__

    def transform(self, func):
        return _col(super(SeriesGroupBy, self).transform(func))

    transform.__doc__ = GroupBy.transform.__doc__

    def filter(self, func):
        raise NotImplementedError()
