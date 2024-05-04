

import pandas as pd



df = pd.read_csv("test_set.csv")


def cognee_add_wrapper(column_value):
    pass


def cognee_cognify_wrapper(column_value):
    pass

def cognee_search_wrapper(column_value):
    pass





for index, row in df.iterrows():
    # Iterate over each column in the row
    for column_name, column_value in row.items():
        # Pass each column value to cognee_add_wrapper function
        cognee_add_wrapper(column_value)


