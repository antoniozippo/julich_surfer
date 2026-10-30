import json

from napari_julich_surfer.__main__ import _load_names, build_parser


def test_labels_json_object(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"1": "Area hOc1", "2": "Area hOc2"}), encoding="utf-8")
    assert _load_names(str(path)) == {1: "Area hOc1", 2: "Area hOc2"}


def test_labels_json_list(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(["Background", "Area hOc1"]), encoding="utf-8")
    assert _load_names(str(path)) == ["Background", "Area hOc1"]


def test_labels_plain_text(tmp_path):
    path = tmp_path / "labels.txt"
    path.write_text("Area hOc1\nArea hOc2\n\n", encoding="utf-8")
    assert _load_names(str(path)) == ["Area hOc1", "Area hOc2"]


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.atlas == "maxprob-thr25-1mm"
    assert args.three_d is True
    assert args.keep_sides_together is False
    assert args.legacy_names is False
    assert build_parser().parse_args(["--2d"]).three_d is False
    assert build_parser().parse_args(["--legacy-names"]).legacy_names is True
