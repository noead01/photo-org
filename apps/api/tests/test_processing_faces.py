import json
from types import SimpleNamespace

import pytest

from app.processing.faces import (
    FaceDetection,
    OpenCvFaceDetector,
    OpenCvSFaceEmbeddingExtractor,
    _encode_jpeg,
    create_default_face_detector,
)


def test_face_detection_as_row_returns_plain_dict():
    detection = FaceDetection(
        face_id="face-1",
        bbox_x=1,
        bbox_y=2,
        bbox_w=3,
        bbox_h=4,
        bitmap=b"jpeg",
        embedding=[0.1, 0.2],
        provenance={"detector": "opencv"},
        person_id="person-1",
    )

    assert detection.as_row() == {
        "face_id": "face-1",
        "bbox_x": 1,
        "bbox_y": 2,
        "bbox_w": 3,
        "bbox_h": 4,
        "bitmap": b"jpeg",
        "embedding": [0.1, 0.2],
        "provenance": {"detector": "opencv"},
        "person_id": "person-1",
    }


class _FakeImage:
    def __init__(self):
        self.saved = []

    def save(self, buffer, *, format, quality):
        self.saved.append((format, quality))
        buffer.write(b"jpeg-bytes")


def test_encode_jpeg_serializes_image_to_jpeg_bytes():
    image = _FakeImage()

    result = _encode_jpeg(image)

    assert result == b"jpeg-bytes"
    assert image.saved == [("JPEG", 90)]


class _EmptyClassifier:
    def __init__(self, _path):
        pass

    def empty(self):
        return True


class _LoadedClassifier:
    def __init__(self, _path):
        self.calls = []

    def empty(self):
        return False

    def detectMultiScale(self, grayscale, *, scaleFactor, minNeighbors, minSize, maxSize=None):
        self.calls.append((grayscale, scaleFactor, minNeighbors, minSize, maxSize))
        return [(10, 20, 30, 40)]


def test_detector_init_raises_when_cascade_classifier_is_unavailable(monkeypatch):
    fake_cv2 = SimpleNamespace(
        data=SimpleNamespace(haarcascades="/fake/"),
        CascadeClassifier=_EmptyClassifier,
    )

    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)

    with pytest.raises(RuntimeError, match="unable to load cascade classifier"):
        OpenCvFaceDetector()


class _FakeRgbImage:
    size = (200, 100)

    def __init__(self):
        self.crops = []

    def convert(self, mode):
        assert mode == "RGB"
        return self

    def crop(self, box):
        self.crops.append(box)
        return _FakeImage()

    def __array__(self):
        return [[1, 2], [3, 4]]


class _FakeImageContext:
    def __init__(self, image):
        self._image = image

    def __enter__(self):
        return self._image

    def __exit__(self, exc_type, exc, tb):
        return False


def test_detector_detect_returns_serialized_face_rows(monkeypatch, tmp_path):
    classifier = _LoadedClassifier("/fake/haarcascade_frontalface_default.xml")
    fake_cv2 = SimpleNamespace(
        data=SimpleNamespace(haarcascades="/fake/"),
        COLOR_RGB2GRAY="gray",
        CascadeClassifier=lambda _path: classifier,
        cvtColor=lambda image, _mode: image,
    )
    fake_numpy = SimpleNamespace(array=lambda image: image.__array__())
    fake_rgb_image = _FakeRgbImage()
    fake_image_module = SimpleNamespace(open=lambda _path: _FakeImageContext(fake_rgb_image))
    fake_image_ops = SimpleNamespace(exif_transpose=lambda image: image)
    fake_pil = SimpleNamespace(Image=fake_image_module, ImageOps=fake_image_ops)
    register_calls = []
    fake_heif = SimpleNamespace(register_heif_opener=lambda: register_calls.append(True))

    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    monkeypatch.setitem(__import__("sys").modules, "numpy", fake_numpy)
    monkeypatch.setitem(__import__("sys").modules, "PIL", fake_pil)
    monkeypatch.setitem(__import__("sys").modules, "PIL.Image", fake_image_module)
    monkeypatch.setitem(__import__("sys").modules, "PIL.ImageOps", fake_image_ops)
    monkeypatch.setitem(__import__("sys").modules, "pillow_heif", fake_heif)

    detector = OpenCvFaceDetector(scale_factor=1.2, min_neighbors=7, min_size=(48, 48))

    result = detector.detect(tmp_path / "sample.jpg")

    assert register_calls == [True]
    assert classifier.calls == [([[1, 2], [3, 4]], 1.2, 7, (48, 48), None)]
    assert fake_rgb_image.crops == [(10, 20, 40, 60)]
    assert len(result) == 1
    assert result[0]["bbox_x"] == 10
    assert result[0]["bbox_y"] == 20
    assert result[0]["bbox_w"] == 30
    assert result[0]["bbox_h"] == 40
    assert result[0]["bitmap"] == b"jpeg-bytes"
    assert result[0]["embedding"] is None
    assert result[0]["provenance"] == {
        "detector": "opencv-haarcascade",
        "model": "haarcascade_frontalface_default",
        "scale_factor": 1.2,
        "min_neighbors": 7,
        "min_size": [48, 48],
        "max_size": None,
        "min_area_ratio": 0.0,
        "max_area_ratio": 1.0,
        "aspect_ratio_min": 0.0,
        "aspect_ratio_max": 100.0,
        "bbox_space_width": 200,
        "bbox_space_height": 100,
    }


class _FakeEmbeddingExtractor:
    def __init__(self):
        self.images = []

    def extract(self, image):
        self.images.append(image)
        return [1.0, 0.0]

    def provenance(self):
        return {"extractor": "fake-sface", "model": "fake.onnx"}


def test_detector_detect_uses_configured_embedding_extractor(monkeypatch, tmp_path):
    classifier = _LoadedClassifier("/fake/haarcascade_frontalface_default.xml")
    fake_cv2 = SimpleNamespace(
        data=SimpleNamespace(haarcascades="/fake/"),
        COLOR_RGB2GRAY="gray",
        CascadeClassifier=lambda _path: classifier,
        cvtColor=lambda image, _mode: image,
    )
    fake_numpy = SimpleNamespace(array=lambda image: image.__array__())
    fake_rgb_image = _FakeRgbImage()
    fake_image_module = SimpleNamespace(open=lambda _path: _FakeImageContext(fake_rgb_image))
    fake_image_ops = SimpleNamespace(exif_transpose=lambda image: image)
    fake_pil = SimpleNamespace(Image=fake_image_module, ImageOps=fake_image_ops)
    fake_heif = SimpleNamespace(register_heif_opener=lambda: None)
    embedding_extractor = _FakeEmbeddingExtractor()

    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    monkeypatch.setitem(__import__("sys").modules, "numpy", fake_numpy)
    monkeypatch.setitem(__import__("sys").modules, "PIL", fake_pil)
    monkeypatch.setitem(__import__("sys").modules, "PIL.Image", fake_image_module)
    monkeypatch.setitem(__import__("sys").modules, "PIL.ImageOps", fake_image_ops)
    monkeypatch.setitem(__import__("sys").modules, "pillow_heif", fake_heif)

    detector = OpenCvFaceDetector(embedding_extractor=embedding_extractor)

    result = detector.detect(tmp_path / "sample.jpg")

    assert fake_rgb_image.crops == [(10, 20, 40, 60)]
    assert len(embedding_extractor.images) == 1
    assert result[0]["embedding"] == [1.0, 0.0]
    assert result[0]["provenance"]["embedding"] == {
        "extractor": "fake-sface",
        "model": "fake.onnx",
    }


def test_sface_embedding_extractor_returns_normalized_feature(monkeypatch, tmp_path):
    model_file = tmp_path / "sface.onnx"
    model_file.write_bytes(b"model")
    feature = [[3.0, 4.0, *([0.0] * 126)]]
    recognizer = SimpleNamespace(feature=lambda _image: feature)
    fake_cv2 = SimpleNamespace(
        FaceRecognizerSF_create=lambda model, config: recognizer,
        COLOR_RGB2BGR="bgr",
        cvtColor=lambda image, _mode: image,
        resize=lambda image, size: (image, size),
    )
    fake_numpy = SimpleNamespace(array=lambda image: image.__array__())
    fake_image = _FakeRgbImage()

    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    monkeypatch.setitem(__import__("sys").modules, "numpy", fake_numpy)

    extractor = OpenCvSFaceEmbeddingExtractor(model_file)

    embedding = extractor.extract(fake_image)
    assert embedding is not None
    assert embedding[:2] == [0.6, 0.8]
    assert embedding[2:] == [0.0] * 126
    assert extractor.provenance() == {
        "extractor": "opencv-sface",
        "model": str(model_file),
        "input_size": [112, 112],
    }


def test_create_default_face_detector_reads_env_settings(monkeypatch):
    fake_cv2 = SimpleNamespace(
        data=SimpleNamespace(haarcascades="/fake/"),
        CascadeClassifier=lambda _path: _LoadedClassifier(_path),
    )
    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    monkeypatch.setenv("FACE_DETECT_SCALE_FACTOR", "1.2")
    monkeypatch.setenv("FACE_DETECT_MIN_NEIGHBORS", "9")
    monkeypatch.setenv("FACE_DETECT_MIN_SIZE", "96x96")
    monkeypatch.setenv("FACE_DETECT_MAX_SIZE", "420x420")
    monkeypatch.setenv("FACE_DETECT_MIN_AREA_RATIO", "0.01")
    monkeypatch.setenv("FACE_DETECT_MAX_AREA_RATIO", "0.45")
    monkeypatch.setenv("FACE_DETECT_ASPECT_RATIO_MIN", "0.75")
    monkeypatch.setenv("FACE_DETECT_ASPECT_RATIO_MAX", "1.35")

    detector = create_default_face_detector()

    assert detector._scale_factor == 1.2
    assert detector._min_neighbors == 9
    assert detector._min_size == (96, 96)
    assert detector._max_size == (420, 420)
    assert detector._min_area_ratio == 0.01
    assert detector._max_area_ratio == 0.45
    assert detector._aspect_ratio_min == 0.75
    assert detector._aspect_ratio_max == 1.35


def test_create_default_face_detector_reads_named_profile(monkeypatch):
    fake_cv2 = SimpleNamespace(
        data=SimpleNamespace(haarcascades="/fake/"),
        CascadeClassifier=lambda _path: _LoadedClassifier(_path),
    )
    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    monkeypatch.setenv("FACE_DETECT_PROFILE", "high_precision")

    detector = create_default_face_detector()

    assert detector._scale_factor == 1.15
    assert detector._min_neighbors == 9
    assert detector._min_size == (32, 32)
    assert detector._max_size is None
    assert detector._min_area_ratio == 0.001
    assert detector._max_area_ratio == 0.5
    assert detector._aspect_ratio_min == 0.75
    assert detector._aspect_ratio_max == 1.35


def test_create_default_face_detector_env_overrides_named_profile(monkeypatch):
    fake_cv2 = SimpleNamespace(
        data=SimpleNamespace(haarcascades="/fake/"),
        CascadeClassifier=lambda _path: _LoadedClassifier(_path),
    )
    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    monkeypatch.setenv("FACE_DETECT_PROFILE", "high_precision")
    monkeypatch.setenv("FACE_DETECT_MIN_NEIGHBORS", "11")
    monkeypatch.setenv("FACE_DETECT_MIN_SIZE", "40x40")

    detector = create_default_face_detector()

    assert detector._scale_factor == 1.15
    assert detector._min_neighbors == 11
    assert detector._min_size == (40, 40)
    assert detector._max_size is None


def test_create_default_face_detector_raises_for_unknown_profile(monkeypatch):
    fake_cv2 = SimpleNamespace(
        data=SimpleNamespace(haarcascades="/fake/"),
        CascadeClassifier=lambda _path: _LoadedClassifier(_path),
    )
    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    monkeypatch.setenv("FACE_DETECT_PROFILE", "not-a-real-profile")

    with pytest.raises(ValueError, match="FACE_DETECT_PROFILE must be one of"):
        create_default_face_detector()


def test_create_default_face_detector_reads_profile_values_from_custom_file(monkeypatch, tmp_path):
    profile_file = tmp_path / "profiles.json"
    profile_file.write_text(
        json.dumps(
            {
                "custom_profile": {
                    "scale_factor": 1.18,
                    "min_neighbors": 8,
                    "min_size": [44, 44],
                    "max_size": None,
                    "min_area_ratio": 0.003,
                    "max_area_ratio": 0.72,
                    "aspect_ratio_min": 0.8,
                    "aspect_ratio_max": 1.4,
                }
            }
        ),
        encoding="utf-8",
    )

    fake_cv2 = SimpleNamespace(
        data=SimpleNamespace(haarcascades="/fake/"),
        CascadeClassifier=lambda _path: _LoadedClassifier(_path),
    )
    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    monkeypatch.setenv("FACE_DETECT_PROFILE_FILE", str(profile_file))
    monkeypatch.setenv("FACE_DETECT_PROFILE", "custom_profile")

    detector = create_default_face_detector()

    assert detector._scale_factor == 1.18
    assert detector._min_neighbors == 8
    assert detector._min_size == (44, 44)
    assert detector._max_size is None
    assert detector._min_area_ratio == 0.003
    assert detector._max_area_ratio == 0.72
    assert detector._aspect_ratio_min == 0.8
    assert detector._aspect_ratio_max == 1.4


def test_detector_detect_filters_false_positive_boxes(monkeypatch, tmp_path):
    class _MultiBoxClassifier(_LoadedClassifier):
        def detectMultiScale(self, grayscale, *, scaleFactor, minNeighbors, minSize, maxSize=None):
            self.calls.append((grayscale, scaleFactor, minNeighbors, minSize, maxSize))
            return [
                (0, 0, 20, 20),   # too small by area ratio
                (0, 0, 80, 20),   # too wide by aspect ratio
                (10, 20, 30, 40), # valid
            ]

    classifier = _MultiBoxClassifier("/fake/haarcascade_frontalface_default.xml")
    fake_cv2 = SimpleNamespace(
        data=SimpleNamespace(haarcascades="/fake/"),
        COLOR_RGB2GRAY="gray",
        CascadeClassifier=lambda _path: classifier,
        cvtColor=lambda image, _mode: image,
    )
    fake_numpy = SimpleNamespace(array=lambda image: image.__array__())
    fake_rgb_image = _FakeRgbImage()
    fake_image_module = SimpleNamespace(open=lambda _path: _FakeImageContext(fake_rgb_image))
    fake_image_ops = SimpleNamespace(exif_transpose=lambda image: image)
    fake_pil = SimpleNamespace(Image=fake_image_module, ImageOps=fake_image_ops)
    fake_heif = SimpleNamespace(register_heif_opener=lambda: None)

    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    monkeypatch.setitem(__import__("sys").modules, "numpy", fake_numpy)
    monkeypatch.setitem(__import__("sys").modules, "PIL", fake_pil)
    monkeypatch.setitem(__import__("sys").modules, "PIL.Image", fake_image_module)
    monkeypatch.setitem(__import__("sys").modules, "PIL.ImageOps", fake_image_ops)
    monkeypatch.setitem(__import__("sys").modules, "pillow_heif", fake_heif)

    detector = OpenCvFaceDetector(
        min_area_ratio=0.05,
        max_area_ratio=0.7,
        aspect_ratio_min=0.7,
        aspect_ratio_max=1.4,
    )
    result = detector.detect(tmp_path / "sample.jpg")

    assert len(result) == 1
    assert result[0]["bbox_x"] == 10
    assert result[0]["bbox_y"] == 20
    assert result[0]["bbox_w"] == 30
    assert result[0]["bbox_h"] == 40
