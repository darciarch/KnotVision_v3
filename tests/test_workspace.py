"""data/<name>/ handling: the source is moved once, after the run; outputs never overwrite."""

from PIL import Image

from img2texcelle.workspace import discard_run, finish_run, prepare_run


def make_jpg(path):
    Image.new("RGB", (8, 12), (200, 100, 50)).save(path)


def test_source_is_moved_into_run_dir_after_the_run(tmp_path):
    data = tmp_path / "data"
    src = tmp_path / "somewhere" / "design.jpeg"
    src.parent.mkdir()
    make_jpg(src)

    paths = prepare_run(src, "tiff", root=data)
    assert paths.run_dir == data / "design"
    assert paths.run_dir.is_dir()
    assert paths.source == src and src.exists()  # not moved yet
    assert paths.image == data / "design" / "design.tiff"
    assert paths.palette_txt == data / "design" / "design_palette.txt"

    assert finish_run(paths)
    assert not src.exists()
    assert paths.source_target == data / "design" / "design.jpeg"
    assert paths.source_target.is_file()


def test_failed_run_leaves_the_source_and_no_empty_folder(tmp_path):
    data = tmp_path / "data"
    src = tmp_path / "design.jpeg"
    make_jpg(src)
    paths = prepare_run(src, "tiff", root=data)
    discard_run(paths)
    assert src.exists() and not paths.run_dir.exists()


def test_repeated_runs_get_new_names(tmp_path):
    data = tmp_path / "data"
    src = tmp_path / "design.jpeg"
    make_jpg(src)
    first = prepare_run(src, "bmp", root=data)
    first.image.write_bytes(b"x")
    first.palette_txt.write_text("1\t0\t0\t0\t#000000\n")
    finish_run(first)
    inside = first.source_target

    second = prepare_run(inside, "bmp", root=data)  # source already inside
    assert second.image == data / "design" / "design_2.bmp"
    assert second.palette_txt == data / "design" / "design_2_palette.txt"
    assert not finish_run(second) and inside.is_file()
    second.image.write_bytes(b"y")

    third = prepare_run(inside, "bmp", root=data)
    assert third.image == data / "design" / "design_3.bmp"
    assert first.image.read_bytes() == b"x"


def test_other_format_in_same_folder(tmp_path):
    data = tmp_path / "data"
    src = tmp_path / "design.jpeg"
    make_jpg(src)
    a = prepare_run(src, "tiff", root=data)
    a.image.write_bytes(b"x")
    b = prepare_run(src, "bmp", root=data)
    assert b.image == data / "design" / "design.bmp"


def test_name_clash_with_a_different_file_is_an_error(tmp_path):
    import pytest
    data = tmp_path / "data"
    src = tmp_path / "design.jpeg"
    make_jpg(src)
    (data / "design").mkdir(parents=True)
    make_jpg(data / "design" / "design.jpeg")
    with pytest.raises(SystemExit, match="already exists"):
        prepare_run(src, "tiff", root=data)


def test_part_output_names(tmp_path):
    from img2texcelle.workspace import next_free_name
    image, txt = next_free_name(tmp_path, "design", "part")
    assert (image.name, txt.name) == ("design_part.png", "design_palette.txt")
    image.touch()
    image, txt = next_free_name(tmp_path, "design", "part")
    assert (image.name, txt.name) == ("design_2_part.png", "design_2_palette.txt")
    src = tmp_path / "design.jpg"
    make_jpg(src)
    paths = prepare_run(src, "part", root=tmp_path / "data")
    assert paths.image.name == "design_part.png" and paths.part_json.name == "design_part.json"
