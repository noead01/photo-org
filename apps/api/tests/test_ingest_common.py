from app.processing.ingest_common import iter_photo_files


def test_iter_photo_files_streams_supported_files_in_stable_directory_order(tmp_path):
    root = tmp_path / "root"
    nested = root / "b" / "nested"
    sibling = root / "a"
    nested.mkdir(parents=True)
    sibling.mkdir(parents=True)

    (root / "ignore.txt").write_text("ignore")
    (sibling / "img-02.jpg").write_text("jpg")
    (sibling / "img-01.jpeg").write_text("jpeg")
    (nested / "img-03.heic").write_text("heic")
    (nested / "img-04.png").write_text("png")

    observed = [path.relative_to(root).as_posix() for path in iter_photo_files(root)]

    assert observed == [
        "a/img-01.jpeg",
        "a/img-02.jpg",
        "b/nested/img-03.heic",
        "b/nested/img-04.png",
    ]
