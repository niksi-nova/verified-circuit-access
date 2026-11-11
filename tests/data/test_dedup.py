from vca.data.dedup import find_overlaps, group_near_duplicates


def test_exact_and_reencoded_copies_are_found(tmp_path, pattern):
    ref = pattern(tmp_path / "ref.png", 1)
    exact = tmp_path / "exact.png"
    exact.write_bytes(ref.read_bytes())
    rescaled = pattern(tmp_path / "rescaled.jpg", 1, size=(240, 160), fmt="JPEG")
    other = pattern(tmp_path / "other.png", 2)

    overlaps = find_overlaps([exact, rescaled, other], [ref])

    assert overlaps[exact] == (ref, 0)
    assert overlaps[rescaled][0] == ref
    assert other not in overlaps


def test_near_duplicates_share_a_group(tmp_path, pattern):
    a = pattern(tmp_path / "a.png", 1)
    b = pattern(tmp_path / "b.jpg", 1, size=(200, 140), fmt="JPEG")
    c = pattern(tmp_path / "c.png", 3)

    groups = group_near_duplicates([a, b, c])

    assert groups[0] == groups[1] != groups[2]
