import pandas as pd
from pandas.api.types import is_numeric_dtype


class ExcelModifier:
    """
    Template for an object that can modify an Excel workbook.

    Attributes:
    - workbook_writer: the XlsxWriter of the workbook you want to modify
    - sheets_to_modify: a dictionary which has key-value pairs of format {<sheet
      name>: <sheet data>}, where sheet_name is the name of a sheet you want to
      modify and sheet_data is the pandas DataFrame that contains the data in
      that sheet
    """

    def __init__(self, writer):
        self.workbook_writer = writer
        self.sheets_to_modify = {}

    def close(self):
        """
        Closes the writer associated with this ExcelModifier.
        """
        self.workbook_writer.close()

    def set_sheets_to_modify(self, sheet_names: list[str]):
        """
        Setter for self.sheets_to_modify. Sets the sheet names that the any
        modifying function in this class will use.

        Args:
        - sheet_names: A list of strings that contain the names of the sheets
          to modify.
        """
        self.sheets_to_modify = sheet_names

    def _get_indices_to_edit(self, sheet_data: pd.DataFrame, columns: list[str] | list[tuple],
                             multi_index: bool) -> list[int]:
        """
        Given a dataframe sheet_data, the columns within the dataframe that should
        be colourized, and whether or not the dataframe is multi-indexed, return
        the indices of the columns that should be coloured.

        Args:
        - sheet_data: the DataFrame in which to find the columns
        - columns: a list of columns to colourize. If multi_index is False,
        then this is a list of strings. If multi_index is True, then this is
        a list of tuples, each one representing a multi-indexed column name
        (e.g. ('A', 'a')).
        - multi_index: a boolean flag specifying if the dataframe is multi-indexed
        or not
        """
        list_of_columns = sheet_data.columns.tolist()
        return [i for i in range(len(list_of_columns)) if list_of_columns[i] in
                columns and is_numeric_dtype(sheet_data[list_of_columns[i]])]

    def _calculate_bounds(self, series: pd.Series, upper_bound: float,
                          lower_bound: float) -> tuple[float, float]:
        """
        Returns a tuple of the form (X, Y) where  X is the value at the upper_bound
        percentile and Y is the value of the lower_bound percentile of the data.
        In other words, X is the number such that all numbers in the column > X are
        in the top upper_bound percentage of data, and Y is the number such that
        all numbers in the column < Y are in the bottom lower_bound percentage of
        data. In other words,

        Args:
        - series: the pandas Series for which to calculate X and Y
        - upper_bound: the desired upper bound. For example, if this is 5.0, X
          will be the smallest number in the column such that the next largest
          number after X is part of the top 5% of data in the column.
        - lower_bound: the desired lower bound. For example, if this is 5.0, Y
          will be the largest number in the column such that the next largest
          number after Y is part of the bottom 5% of data in the column.
        - lower_bound: the desired lower bound. For example, if this is 5.0, Y
          will be the largest number in the column such that the next largest
          number after Y is part of the bottom 5% of data in the column.
        """
        sorted_series = series.sort_values()

        # adjusting user inputs for the series.quantile function
        upper_bound_quantile = 1.0 - (upper_bound / 100.0)
        lower_bound_quantile = lower_bound / 100.0

        # calculating X and Y using the series.quantile function
        x = sorted_series.quantile(upper_bound_quantile)
        y = sorted_series.quantile(lower_bound_quantile)

        return (x, y)

    def _parse_instructions(self, instructions: str) -> dict[str, str]:
        """
        Given an instruction string of the format described in the docstring of
        self.colourize_columns, returned a dictionary of options to pass into
        self._colourize_columns.
        """
        instruction_split = instructions.split()
        POSSIBLE_INSTRUCTIONS = 'MmCcpsoO'

        params_to_pass = {}

        # going through each element in the split instructions
        for i in range(len(instruction_split)):
            current_elem = instruction_split[i]

            # if this is indeed a new instruction
            if current_elem in POSSIBLE_INSTRUCTIONS:
                next_item = instruction_split[i + 1]
                match current_elem:
                    case 'M':
                        params_to_pass['margin_upper'] = float(next_item)
                    case 'm':
                        params_to_pass['margin_lower'] = float(next_item)
                    case 'C':
                        params_to_pass['colour_upper'] = 'red' if next_item == 'r' else 'green'
                    case 'c':
                        params_to_pass['colour_lower'] = 'red' if next_item == 'r' else 'green'
                    case 'p':
                        params_to_pass['majority_percentage'] = float(
                            next_item)
                    case 's':
                        match next_item:
                            case 'u':
                                params_to_pass['formatting_option'] = 'colour_upper'
                            case 'l':
                                params_to_pass['formatting_option'] = 'colour_lower'
                            case 'b':
                                params_to_pass['formatting_option'] = 'colour_both'
                    case 'o':
                        params_to_pass['row_offset'] = int(next_item)
                    case 'O':
                        params_to_pass['column_offset'] = int(next_item)

        return params_to_pass

    def colourize_all(self, instructions: str, exclude_columns: list[str] = [], multi_index: bool = False) -> None:
        """
        Applies the instructions string to every column in every sheet in
        self.set_sheets_to_modify.

        Args:
        - instructions: the instructions string to apply to each column in every sheet
        - exclude_columns: a list of columns to EXCLUDE from colourization in
          each sheet (e.g. ID columns). If multi_index is False, then this should be
          a list of strings (because columns are single-indexed). Else, it should
          be a lits of tuples, where each tuple is a multi-indexed column name.
          Default value is [] (i.e. ignore no columns).
        - multi_index: a flag representing whether or not the the sheets in
          self.sheets_to_modify are multi-indexed or not. Note that, at one
          time, the sheets in self.sheets_to_modify may only be exclusively
          single-indexed or multi-indexed.
        """
        # parse the instruction string
        parsed_instructions = self._parse_instructions(instructions)

        # extract the parameters from the parsed instructions
        formatting_option = parsed_instructions['formatting_option']
        margin_options = (
            parsed_instructions['margin_upper'], parsed_instructions['margin_lower'])
        colour_options = (
            parsed_instructions['colour_upper'], parsed_instructions['colour_lower'])
        majority_percentage = parsed_instructions['majority_percentage']
        write_offsets = (
            parsed_instructions['row_offset'], parsed_instructions['column_offset'])

        for sheet_name, sheet_data in self.sheets_to_modify.items():
            columns = [column_name for column_name in sheet_data.columns.tolist(
            ) if column_name not in exclude_columns]
            # call the helper function
            self._colourize_columns(sheet_name, sheet_data, columns,
                                    formatting_option, margin_options,
                                    colour_options, majority_percentage,
                                    write_offsets, multi_index)

    def colourize_columns(self, columns: list[str] | list[tuple], instructions: str, multi_index: bool = False) -> None:
        """
        Given a string of instructions (specification below), colorize columns
        of all sheets in self.sheets_to_modify based on the instructions.

        Args:
        - columns: Signifies the columns to which the instructions passed to this
          function should be applied (for every sheet in self.sheets_to_modify).
          If multi_index is False, then this should be a list of strings for
          single-indexed dataframes. Else, it should be a list of tuples for
          multi-indexed dataframes.
        - instructions: a string of instructions that specify how each column
          should be modified. The specification for this instructions string is
          found below:
        - multi_index: a flag representing whether or not the the sheets in
          self.sheets_to_modify are multi-indexed or not. Note that, at one time,
          the sheets in self.sheets_to_modify may only be exclusively
          single-indexed or multi-indexed.

        Specification for Instructions String (note: order in which these options are specified
        does not matter but all of them must be present in an instructions string):
        - M is used to specify the upper margin percentage, which is the percentage
        of the data in a column to consider as an UPPER margin. It is followed by
        a space and an float to 0.0 to 100.0 (e.g. M 35.0).
        - m is used to specify the upper margin percentage, which is the percentage
        of the data in a column to consider as an LOWER margin. It is followed by
        a space and an float from 0.0 to 100.0 (e.g. m 35.0).
        - C is used to specify the upper margin colour, which is the colour that
        any data within the upper margin will have. It is followed by a space
        and one of {'r', 'g'} (e.g. C g).
        - c is used to specify the lower margin colour, which is the colour that
        any data within the lower margin will have. It is followed by a space
        and one of {'r', 'g'} (e.g. c r).
        - p is used to specify the majority percentage, which is the percentage
        either the smallest or largest element in a column will have to take
        up to be a "majority", which will exclude it from being colorized. It
        is followed by a space and a float from 0.0 to 100.0 (e.g. p 10.0).
        - s is used to specify the sections of the columns that must be colorized.
        It is followed by a space and one of {'u', 'l', 'b'}. 'u' stands for upper,
        meaning elements within the upper margin will be colorized, and similarly
        for lower and both.
        - o is used to specify the row offset, which is the row number from
        which to start writing. It is followed by a space and an integer that
        is greater than or equal to 0. This option is helpful in cases where
        the data to colourize does not start from row 0 (or row 1 in practice).
        - o is used to specify the column offset, which is the column number from
        which to start writing. It is followed by a space and an integer that
        is greater than or equal to 0. This option is helpful in cases where
        the data to colourize does not start from column 0 (or column 1 in practice).

        EXAMPLE USAGE:
        Here are two example calls:

        1. colourize_columns(['mean', 'missing'], 'M 5.0 m 10.0 C g c r p 10.0
                             s b o 1 O 0', multi_index=False)

        This will colourize the 'mean' and 'missing' columns in every sheet in
        self.set_sheets_to_modify, considering the upper margin as 5% and colouring
        it green, the lower margin as 10% and colouring it red, considering the "majority
        percentage" as 10%, colourizing both the upper and lower margins, and
        starting colourization and overwriting from row 1 (to account for the title
        row) and column 0. Note that even if integers are used in place of the floats,
        this function still works.

        2. colourize_columns([('A', 'mean'), ('B', 'missing')], 'M 5.0 m 10.0 C
                             g c r p 10.0 s b o 1 O 0', multi_index=True)

        This does the same thing as the last function call, except the columns are
        tuples because they are multi-indexed.

        For any further clarification on options, view the docstring of
        self._colourize_columns.
        """
        # parse the instruction string
        parsed_instructions = self._parse_instructions(instructions)

        # extract the parameters from the parsed instructions
        formatting_option = parsed_instructions['formatting_option']
        margin_options = (
            parsed_instructions['margin_upper'], parsed_instructions['margin_lower'])
        colour_options = (
            parsed_instructions['colour_upper'], parsed_instructions['colour_lower'])
        majority_percentage = parsed_instructions['majority_percentage']
        write_offsets = (
            parsed_instructions['row_offset'], parsed_instructions['column_offset'])

        for sheet_name, sheet_data in self.sheets_to_modify.items():
            # call the helper function
            self._colourize_columns(sheet_name, sheet_data, columns,
                                    formatting_option, margin_options,
                                    colour_options, majority_percentage,
                                    write_offsets, multi_index)

    def _colourize_columns(self, sheet_name: str, sheet_data: pd.DataFrame,
                           columns_to_format: list[str] | list[tuple], formatting_option: str,
                           margin_options: tuple[float, float],
                           colour_options: tuple[str, str] = ('green', 'red'),
                           majority_percentage: float = 10.0,
                           write_offsets: tuple[int, int] = (0, 0), multi_index: bool = False) -> None:
        """
        Applies all options to the columns in columns_to_format in the sheet
        with the name sheet_name.

        Args:
        - sheet_name: the name of the sheet where changes should be applied
        - sheet_data: the pandas dataframe associated with the sheet sheet_name
        - columns_to_format: a list containing the names of the columns in
          self.sheets_to_modify to colourize. If multi_index is True, this should
          be a list of strings. Else, this should be a list of tuples, with each
          tuple representing the multi-indexed column to be colourized.
        - formatting_option: a string from the set { 'colour_both', 'colour_upper', 'colour_lower' }
          which describes whether to colour only the upper margin, lower margin,
          or both
        - margin_options: a tuple of the form (X, Y) where X and Y are floats from
          0.0 to 100.0 (inclusive). X is the percent of the data to consider as the UPPER margin.
          Y is the percent of the data to consider as the LOWER margin.
        - colour_options: a tuple of the form (A, B) where A and B are strings
          from the set {'red', 'green'}. A is the colour to apply to the UPPER margin of
          the data in a given column. B is the colour to apply to the LOWER margin of the data
          in a given column.
        - majority_percentage: a float from 0.0 to 100.0 which signifies the
          percentage that a specific data point must take up in a column to be
          considered a "majority". If the smallest or largest element in a
          column takes up at least majority_percentage% of the column, then it
          will not be included in the bound. Default value is 10.
        - write_offsets: a tuple of the form (M, N) where M is the row number
          from which to start overwriting and N is the column number from which
          to start overwriting. This is necessary for correct formatting if the
          data you want to colourize in initial sheet(s) do not start at row
          and column 0 and 0. Default value is (0, 0).
        - multi_index: whether or not sheet_data is a multi-index Pandas dataframe.
          Default is False.

        EXAMPLE USAGE:

        If the following inputs were given to the function:
        - sheet_name = 'Sheet1' (assuming Sheet1 exists in the workbook this ExcelModifier is modifying)
        - sheet_data is the dataframe associated with Sheet1
        - columns_to_format = ['mean', 'missing']
        - formatting_option = 'colour_upper'
        - margin_options = (5, 10)
        - colour_options = ('green', 'red')
        - majority_percentage = 10
        - write_offsets = (1, 1)
        - multi_index = False

        Then the following would happen:
        - For the columns in the single-indexed Sheet1 called 'mean' and
          'missing', the upper 5 percent of the data would be coloured green.
            - If the largest element in each column takes up at least
              majority_percentage% of the column, it will not be included in
              the colorization.
            - Colorized cells will be written starting from row 1 (which is the
              second row in practice) and column 1 (which is the second column
              in practice)

        If the same inputs were given to the function but multi_index is True, then
        the same thing would happen but columns_to_format would have to be
        something like [('A', 'mean'), ('B', 'missing')] to account for
        multi-indexing.
        """
        # extracting margins
        upper_bound, lower_bound = margin_options

        # exctracting the colours
        upper_colour, lower_colour = colour_options

        # creating reusable formats
        # TODO: custom colours
        upper_colour_format = self.workbook_writer.book.add_format(
            {'bg_color': ('#FFC7CE' if upper_colour == 'red' else '#C6EFCE')})
        lower_colour_format = self.workbook_writer.book.add_format(
            {'bg_color': ('#FFC7CE' if lower_colour == 'red' else '#C6EFCE')})

        row_offset, column_offset = write_offsets

        column_indices_to_format = self._get_indices_to_edit(
            sheet_data, columns_to_format, multi_index)
        sheet_data_columns = sheet_data.columns.tolist()

        # using the helper function to calculate bounds for each column
        bounds = {column_index: self._calculate_bounds(
            sheet_data[sheet_data_columns[column_index]], upper_bound,
            lower_bound) for column_index in column_indices_to_format}

        # applying conditional formatting based on the bounds and column
        # formatting
        worksheet = self.workbook_writer.sheets[sheet_name]
        num_rows = sheet_data.shape[0]

        for column_pos in column_indices_to_format:
            # which column are we in
            # column_pos = sheet_data.columns.get_loc(column_index)
            current_column = sheet_data[sheet_data_columns[
                column_pos]]

            # if the biggest and lowest data points take up this much percentage
            # of the upper and lower bounds, respectively, they will not be
            # colorized
            ignore_bound_percentage = majority_percentage / 100

            # find the largest item in the column
            largest = current_column.max()
            # this will contain whether or not the largest element appeas
            # in more than majority_percentage% of this column
            upper_bound_majority_exists = (
                current_column == largest).mean() >= ignore_bound_percentage
            # find the smallest item in the column
            smallest = current_column.min()
            # this will contain whether or not the smallest element appears
            # in more than majority_percentage% of this column
            lower_bound_majority_exists = (
                current_column == smallest).mean() >= ignore_bound_percentage

            # for each row in the column
            for row_pos in range(0, num_rows):
                current_data = sheet_data.iat[row_pos, column_pos]

                if current_data != 'nan':
                    # if the upper bound must be coloured
                    if formatting_option in {'colour_upper', 'colour_both'}:
                        if upper_bound_majority_exists:  # if this is true, we don't want to include the largest element
                            if largest > current_data >= bounds[column_pos][0]:
                                # overwriting the cell with the original data and new formatting
                                worksheet.write(row_offset + row_pos, column_offset + column_pos,
                                                current_data, upper_colour_format)
                        else:
                            if largest >= current_data >= bounds[column_pos][0]:
                                # overwriting the cell with the original data and new formatting
                                worksheet.write(row_offset + row_pos, column_offset + column_pos,
                                                current_data, upper_colour_format)

                    if formatting_option in {'colour_lower', 'colour_both'}:
                        if lower_bound_majority_exists:  # if this is true, we don't want to include the smallest element
                            if smallest < current_data <= bounds[column_pos][1]:
                                # overwriting the cell with the original data and new formatting
                                worksheet.write(row_offset + row_pos, column_offset + column_pos,
                                                current_data, lower_colour_format)
                        else:
                            if smallest <= current_data <= bounds[column_pos][1]:
                                # overwriting the cell with the original data and new formatting
                                worksheet.write(row_offset + row_pos, column_offset + column_pos,
                                                current_data, lower_colour_format)

    def autofit_sheets(self) -> None:
        """
        Autofits all sheets in self.set_sheets_to_modify.
        """
        for sheet_name in self.sheets_to_modify:
            worksheet = self.workbook_writer.sheets[sheet_name]
            worksheet.autofit()
