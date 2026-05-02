from types import SimpleNamespace

import pytest

from app.processing.faces import FaceDetection, OpenCvFaceDetector, _encode_jpeg


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

    def detectMultiScale(self, grayscale, *, scaleFactor, minNeighbors, minSize):
        self.calls.append((grayscale, scaleFactor, minNeighbors, minSize))
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
    assert classifier.calls == [([[1, 2], [3, 4]], 1.2, 7, (48, 48))]
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
        "bbox_space_width": 200,
        "bbox_space_height": 100,
    }
