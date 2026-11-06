import pytest

from core.utils import parallel_execute


def test_parallel_execute_without_args_list():
    """Test parallel_execute without args_list parameter"""
    # Define a simple function that returns its invocation count
    counter = [0]

    def increment_counter():
        counter[0] += 1
        return counter[0]

    # Call parallel_execute without args_list
    results = parallel_execute(increment_counter, 5)

    # Check that the function was called the correct number of times
    assert len(results) == 5
    # Each invocation returns a unique counter value
    assert sorted(results) == [1, 2, 3, 4, 5]


def test_parallel_execute_with_args_list():
    """Test parallel_execute with args_list parameter"""

    # Define a function that returns the sum of its arguments
    def add_numbers(*args):
        return sum(args)

    # Create an args_list
    args_list = [(1, 2), (3, 4), (5, 6)]

    # Call parallel_execute with args_list
    results = parallel_execute(add_numbers, len(args_list), args_list=args_list)

    # Check that the results contain the expected sums
    assert sorted(results) == [3, 7, 11]


def test_parallel_execute_args_list_length_mismatch():
    """Test that parallel_execute raises an error if args_list length doesn't match n_times"""

    # Define a simple function
    def dummy_func(x):
        return x

    # Create an args_list with different length than n_times
    args_list = [(1,), (2,)]

    # Check that calling parallel_execute raises a ValueError
    with pytest.raises(ValueError) as excinfo:
        parallel_execute(dummy_func, 3, args_list=args_list)

    # Check the error message
    assert "args_list length" in str(excinfo.value)
