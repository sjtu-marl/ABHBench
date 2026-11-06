import itertools
import math
import random

import pytest

from DBHLLM.prompts.utils import get_choices_text


# Fixtures
@pytest.fixture
def choices_dict():
    """Standard choices dictionary for tests"""
    return {"A": "Option A", "B": "Option B", "C": "Option C"}


@pytest.fixture
def small_choices_dict():
    """Smaller choices dictionary for permutation tests"""
    return {"A": "Option A", "B": "Option B"}


# Tests for get_choices_text function
class TestGetChoicesText:
    def test_random_shuffle(self, choices_dict, monkeypatch):
        """Test random shuffle when perm_index=0 with deterministic mock"""

        # Mock random.shuffle to make the test deterministic
        def mock_shuffle(items):
            # Reverse the list as a predictable "shuffle"
            items.reverse()

        monkeypatch.setattr(random, "shuffle", mock_shuffle)

        # Call the function with perm_index=0
        result = get_choices_text(choices_dict, perm_index=0)

        # Expected result based on our mock (reversed sorted items)
        expected = "- Option C\n- Option B\n- Option A"
        assert result == expected

    def test_first_permutation(self, choices_dict):
        """Test that perm_index=1 returns the first permutation (sorted order)"""
        result = get_choices_text(choices_dict, perm_index=1)
        expected = "- Option A\n- Option B\n- Option C"  # Sorted by key
        assert result == expected

    def test_second_permutation(self, choices_dict):
        """Test that perm_index=2 returns the second permutation"""
        # Get second permutation of sorted items
        items = sorted(list(choices_dict.items()), key=lambda x: x[0])
        perms = list(itertools.permutations(range(len(items))))
        perm_idx = perms[1]  # Second permutation (0-indexed)
        expected_items = [items[i] for i in perm_idx]
        expected = "\n".join([f"- {value}" for key, value in expected_items])

        # Call function with perm_index=2
        result = get_choices_text(choices_dict, perm_index=2)

        assert result == expected

    def test_all_permutations(self, small_choices_dict):
        """Test that all permutations work correctly"""
        # For a dict with 2 items, there are 2! = 2 permutations
        perm1 = get_choices_text(small_choices_dict, perm_index=1)
        perm2 = get_choices_text(small_choices_dict, perm_index=2)

        # The two permutations should be different
        assert perm1 != perm2

        # Each permutation should contain all values
        for value in small_choices_dict.values():
            assert f"- {value}" in perm1
            assert f"- {value}" in perm2

    def test_exceeds_total_permutations(self, small_choices_dict):
        """Test that ValueError is raised when perm_index exceeds total permutations"""
        # small_choices_dict has 2 items, so only 2! = 2 possible permutations
        with pytest.raises(ValueError) as excinfo:
            get_choices_text(small_choices_dict, perm_index=3)

        # Check exception message
        assert "exceeds total possible permutations" in str(excinfo.value)

    def test_empty_choices(self):
        """Test that empty choices dictionary works correctly"""
        result = get_choices_text({})
        assert result == ""

    def test_single_choice(self):
        """Test that single choice dictionary works correctly"""
        result = get_choices_text({"A": "Option A"})
        assert result == "- Option A"

    @pytest.mark.parametrize("perm_index", [0, 1])
    def test_preserve_key_value_pairs(self, choices_dict, perm_index):
        """Test that key-value pairs are preserved in output"""
        result = get_choices_text(choices_dict, perm_index=perm_index)

        # Each value from the original dict should be present in the output
        for value in choices_dict.values():
            assert f"- {value}" in result

        # Total number of items should match
        assert len(result.split("\n")) == len(choices_dict)
